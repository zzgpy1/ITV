# src/services/fetcher.py（关键改动）
import aiohttp
import asyncio
from src.settings import settings
from src.repository import repo_factory
from src.logger import logger
from src.proxy_utils import fetch_with_proxy_fallback

async def fetch_url_with_metadata(session, url, cache_repo, force_refresh=False):
    if not force_refresh:
        cached = await cache_repo.get(url, "raw", settings.cache_raw_hours)
        if cached:
            logger.debug(f"使用缓存: {url}")
            return cached
    content, _ = await fetch_with_proxy_fallback(session, url)
    if content:
        await cache_repo.set(url, content, "raw", settings.cache_raw_hours)
    return content

async def fetch_all_sources(sources, force_refresh=False):
    cache_repo = repo_factory.cache
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_url_with_metadata(session, url, cache_repo, force_refresh) for url in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    return {url: res for url, res in zip(sources, results) if not isinstance(res, Exception)}
