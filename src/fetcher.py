# src/fetcher.py
import asyncio
import aiohttp
from src.settings import settings
from src.logger import logger
from src.repositories import repo_factory


async def fetch_url_with_cache(session: aiohttp.ClientSession, url: str, force_refresh: bool = False):
    cache_repo = repo_factory.cache

    if not force_refresh:
        cached = await cache_repo.get(url, "raw")
        if cached:
            logger.debug(f"✅ 使用缓存: {url}")
            return cached

    logger.info(f"🔄 拉取: {url}")
    try:
        async with session.get(url, timeout=settings.timeout) as resp:
            if resp.status == 200:
                content = await resp.text()
                await cache_repo.set(url, content, "raw", settings.cache_raw_hours)
                return content
            else:
                logger.warning(f"⚠️ {url} 返回 {resp.status}")
                return None
    except Exception as e:
        logger.warning(f"⚠️ 拉取失败 {url}: {e}")
        return None


async def fetch_all_sources(sources: list, force_refresh: bool = False) -> dict:
    connector = aiohttp.TCPConnector(limit=50, limit_per_host=10)
    timeout = aiohttp.ClientTimeout(total=settings.http_timeout + 5)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [fetch_url_with_cache(session, url, force_refresh) for url in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = {}
        for url, res in zip(sources, results):
            if isinstance(res, Exception):
                logger.warning(f"⚠️ 拉取失败 {url}: {res}")
                # 尝试从缓存获取旧数据
                cached = await repo_factory.cache.get(url, "raw")
                output[url] = cached
            else:
                output[url] = res
        return output
