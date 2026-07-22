# src/stable/manager.py
from src.repositories import repo_factory
from src.fixed_sources import CCTV_FIXED_SOURCES, ENABLE_FIXED_SOURCES
from src.logger import logger

class StableManager:
    async def init(self):
        self.repo = repo_factory.stable
        if ENABLE_FIXED_SOURCES:
            await self.sync_fixed_sources()

    async def sync_fixed_sources(self):
        for name, urls in CCTV_FIXED_SOURCES.items():
            url = urls[0] if isinstance(urls, list) and urls else urls
            if url:
                await self.repo.upsert(name, url, 50, "h264", is_fixed=True, auto_optimize=True)
                logger.info(f"固定源同步: {name}")
