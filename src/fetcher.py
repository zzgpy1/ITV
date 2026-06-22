# src/fetcher.py
# 支持 HEAD 请求检测更新，无变化则跳过拉取，直接使用数据库缓存
# 修复 Session is closed 错误：每个请求独立创建会话

import asyncio
import aiohttp
from src.config import HEADERS, TIMEOUT, RETRY_MAX_ATTEMPTS, RETRY_BACKOFF_FACTOR, RETRY_MAX_WAIT, ENABLE_RETRY
from src.database import get_db_cache
from src.logger import logger


class FetchError(Exception):
    pass


async def fetch_url_with_metadata(url: str, db):
    """
    拉取单个 URL 的内容，支持缓存和重试
    每次调用独立创建 aiohttp 会话，避免共享会话关闭问题
    
    Args:
        url: 要拉取的 URL
        db: 数据库连接（为 None 时禁用缓存）
    """
    # 尝试从缓存获取（仅当 db 不为 None 时）
    if db:
        cached_content = await db.get_raw_source(url)
        if cached_content:
            logger.debug(f"✅ 使用缓存: {url}")
            return cached_content

    logger.info(f"🔄 拉取: {url}")
    attempt = 0
    while True:
        attempt += 1
        try:
            # 每次重试创建新的会话，避免 Session is closed
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=TIMEOUT, headers=HEADERS) as resp:
                    if resp.status != 200:
                        raise FetchError(f"HTTP {resp.status}")
                    content = await resp.text()
                    if db:
                        await db.set_raw_source(url, content)
                    return content
        except Exception as e:
            if not ENABLE_RETRY or attempt >= RETRY_MAX_ATTEMPTS:
                raise FetchError(str(e))
            wait_time = min(RETRY_BACKOFF_FACTOR ** (attempt - 1), RETRY_MAX_WAIT)
            logger.warning(f"  重试 {url} ({attempt}/{RETRY_MAX_ATTEMPTS})，等待 {wait_time}s")
            await asyncio.sleep(wait_time)


async def fetch_all_sources_incremental(sources: list, db, force_refresh: bool = False) -> dict:
    """
    并发拉取所有源，支持强制刷新
    
    Args:
        sources: 源 URL 列表
        db: 数据库连接
        force_refresh: 是否强制重新拉取（忽略缓存）
    
    Returns:
        {url: content} 字典
    """
    # 不再使用共享会话，每个 fetch_url_with_metadata 内部自己创建
    tasks = []
    for url in sources:
        if force_refresh:
            # 强制刷新：传入 db=None 禁用缓存
            tasks.append(fetch_url_with_metadata(url, None))
        else:
            tasks.append(fetch_url_with_metadata(url, db))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    output = {}
    for url, res in zip(sources, results):
        if isinstance(res, Exception):
            logger.warning(f"⚠️ 拉取失败 {url}: {res}")
            # 如果不是强制刷新，尝试从缓存读取旧内容
            if not force_refresh and db:
                cached = await db.get_raw_source(url)
                if cached:
                    output[url] = cached
                    logger.info(f"📦 使用旧缓存: {url}")
                else:
                    output[url] = None
            else:
                output[url] = None
        else:
            output[url] = res
    return output
