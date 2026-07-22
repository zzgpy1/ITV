# src/core/stable_manager.py
from src.repository import repo_factory
from src.fixed_sources import CCTV_FIXED_SOURCES, ENABLE_FIXED_SOURCES
from src.logger import logger

class StableManager:
    async def sync_fixed_sources(self):
        if not ENABLE_FIXED_SOURCES:
            return
        for name, urls in CCTV_FIXED_SOURCES.items():
            if isinstance(urls, list) and urls:
                url = urls[0]
            elif isinstance(urls, str):
                url = urls
            else:
                continue
            await repo_factory.stable.upsert(
                name, url, latency=50, video_codec="h264",
                is_fixed=True, auto_optimize=True
            )
        logger.info("固定源同步完成")

    async def get_stable_sources(self):
        return await repo_factory.stable.get_all()
