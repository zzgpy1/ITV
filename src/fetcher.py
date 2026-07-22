# src/fetcher.py
import asyncio
import aiohttp
from src.settings import settings
from src.logger import logger
from src.repositories import repo_factory
from tenacity import retry, stop_after_attempt, wait_exponential

class FetchError(Exception):
    pass

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
async def fetch_url(session: aiohttp.ClientSession, url: str, use_cache=True):
    cache = repo_factory.cache
    if use_cache:
        cached = await cache.get(url, "raw")
        if cached:
            logger.debug(f"缓存命中: {url}")
            return cached
    logger.info(f"拉取: {url}")
    try:
        async with session.get(url, timeout=settings.http_timeout) as resp:
            resp.raise_for_status()
            text = await resp.text()
            if use_cache:
                await cache.set(url, text, "raw", settings.cache_raw_hours)
            return text
    except Exception as e:
        logger.warning(f"拉取 {url} 失败: {e}")
        raise

async def fetch_all_sources(sources, use_cache=True):
    connector = aiohttp.TCPConnector(limit=settings.max_workers)
    timeout = aiohttp.ClientTimeout(total=settings.http_timeout + 5)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [fetch_url(session, url, use_cache) for url in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        output = {}
        for url, res in zip(sources, results):
            if isinstance(res, Exception):
                logger.warning(f"拉取 {url} 失败: {res}")
                output[url] = None
            else:
                output[url] = res
        return output
