import asyncio
import aiohttp
from typing import Dict, Optional
from src.settings import settings
from src.logger import logger
from src.repositories import CacheRepository
from src.http_client import get_session


class Fetcher:
    def __init__(self):
        self.cache_repo = CacheRepository()
        self.session = get_session()

    async def fetch_url(self, url: str, force_refresh: bool = False) -> Optional[str]:
        if not force_refresh:
            cached = await self.cache_repo.get(url, "raw", settings.cache_raw_hours)
            if cached:
                return cached

        try:
            async with self.session.get(url, timeout=settings.http_timeout) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    await self.cache_repo.set(url, text, "raw", settings.cache_raw_hours)
                    return text
                else:
                    logger.warning(f"HTTP {resp.status} for {url}")
        except Exception as e:
            logger.error(f"Fetch error {url}: {e}")
        return None

    async def fetch_all(self, sources: list, force_refresh: bool = False) -> Dict[str, Optional[str]]:
        tasks = [self.fetch_url(url, force_refresh) for url in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        out = {}
        for url, res in zip(sources, results):
            if isinstance(res, Exception):
                out[url] = None
            else:
                out[url] = res
        return out
