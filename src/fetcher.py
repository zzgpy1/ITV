# src/fetcher.py
import asyncio
import aiohttp
from src.config import (
    HEADERS, TIMEOUT, RETRY_MAX_ATTEMPTS, RETRY_BACKOFF_FACTOR,
    RETRY_MAX_WAIT, ENABLE_RETRY,
    CDN_PROXY_ENABLE, CDN_PROXY_URL, CDN_PROXY_DOMAINS
)
from src.database import get_db_cache
from src.logger import logger

class FetchError(Exception):
    pass

def apply_cdn_proxy(url: str) -> str:
    """如果启用CDN且域名匹配，则返回代理URL，否则原样返回"""
    if not CDN_PROXY_ENABLE:
        return url
    proxy_base = CDN_PROXY_URL.rstrip('/') + '/'
    for domain in CDN_PROXY_DOMAINS:
        if domain in url:
            return proxy_base + url
    return url

async def check_source_modified(session: aiohttp.ClientSession, url: str, db):
    # 使用原始URL查缓存，但请求时使用代理URL
    proxy_url = apply_cdn_proxy(url)
    cached_etag = None
    cached_last_modified = None
    if db and db._conn:
        cursor = await db._conn.execute(
            "SELECT etag, last_modified, content FROM channel_cache_raw WHERE url = ?",
            (url,)
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row:
            cached_etag, cached_last_modified, cached_content = row
            if not cached_etag and not cached_last_modified:
                return True, None, None, None
            headers = HEADERS.copy()
            if cached_etag:
                headers["If-None-Match"] = cached_etag
            if cached_last_modified:
                headers["If-Modified-Since"] = cached_last_modified
            try:
                async with session.head(proxy_url, timeout=10, headers=headers) as resp:
                    if resp.status == 304:
                        return False, cached_content, cached_etag, cached_last_modified
                    else:
                        new_etag = resp.headers.get("ETag", "")
                        new_last_modified = resp.headers.get("Last-Modified", "")
                        return True, None, new_etag, new_last_modified
            except Exception:
                return True, None, None, None
    return True, None, None, None

async def fetch_url_with_metadata(session: aiohttp.ClientSession, url: str, db):
    proxy_url = apply_cdn_proxy(url)
    is_modified, cached_content, new_etag, new_last_modified = await check_source_modified(session, url, db)
    if not is_modified and cached_content:
        logger.debug(f"✅ 源无变化，使用缓存: {url}")
        return cached_content

    logger.info(f"🔄 拉取: {url} (代理: {proxy_url if proxy_url != url else '无'})")
    attempt = 0
    while True:
        attempt += 1
        try:
            # 使用代理URL发起GET请求
            async with session.get(proxy_url, timeout=TIMEOUT, headers=HEADERS) as resp:
                if resp.status != 200:
                    raise FetchError(f"HTTP {resp.status}")
                content = await resp.text()
                resp_etag = resp.headers.get("ETag", "")
                resp_last_modified = resp.headers.get("Last-Modified", "")
                if db and db._conn:
                    final_etag = resp_etag or new_etag
                    final_last_modified = resp_last_modified or new_last_modified
                    await db._conn.execute(
                        """INSERT OR REPLACE INTO channel_cache_raw 
                           (url, content, etag, last_modified, updated_at) 
                           VALUES (?, ?, ?, ?, ?)""",
                        (url, content, final_etag, final_last_modified, asyncio.get_event_loop().time())
                    )
                    await db._conn.commit()
                return content
        except Exception as e:
            if not ENABLE_RETRY or attempt >= RETRY_MAX_ATTEMPTS:
                raise FetchError(str(e))
            wait_time = min(RETRY_BACKOFF_FACTOR ** (attempt - 1), RETRY_MAX_WAIT)
            logger.warning(f"  重试 {url} ({attempt}/{RETRY_MAX_ATTEMPTS})，等待 {wait_time}s")
            await asyncio.sleep(wait_time)

async def fetch_all_sources_incremental(sources: list, db) -> dict:
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_url_with_metadata(session, url, db) for url in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        output = {}
        for url, res in zip(sources, results):
            if isinstance(res, Exception):
                logger.warning(f"⚠️ 拉取失败 {url}: {res}")
                # 尝试从数据库取缓存
                if db and db._conn:
                    cursor = await db._conn.execute(
                        "SELECT content FROM channel_cache_raw WHERE url = ?",
                        (url,)
                    )
                    row = await cursor.fetchone()
                    await cursor.close()
                    if row:
                        output[url] = row[0]
                        logger.info(f"📦 使用数据库缓存的旧内容: {url}")
                    else:
                        output[url] = None
                else:
                    output[url] = None
            else:
                output[url] = res
        return output
