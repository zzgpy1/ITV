# src/stable/manager.py
from src.repositories import repo_factory
from src.fixed_sources import CCTV_FIXED_SOURCES, ENABLE_FIXED_SOURCES
from src.logger import logger


class StableManager:
    async def init(self):
        self.stable_repo = repo_factory.stable
        if ENABLE_FIXED_SOURCES:
            await self.sync_fixed_sources()

    async def sync_fixed_sources(self):
        for name, urls in CCTV_FIXED_SOURCES.items():
            if isinstance(urls, list):
                url = urls[0] if urls else None
            else:
                url = urls
            if url:
                existing = await self.stable_repo.get(name)
                if existing:
                    await self.stable_repo.upsert(name, url, 50, "h264",
                                                  is_fixed=True, auto_optimize=True)
                    logger.info(f"📌 固定源同步: {name} -> {url[:50]}...")

    async def get_stable_sources(self):
        return await self.stable_repo.get_all()

    async def promote_candidate(self, channel_name: str, url: str, latency: int, video_codec: str = ""):
        existing = await self.stable_repo.get(channel_name)
        if existing and existing["is_fixed"]:
            logger.warning(f"⚠️ {channel_name} 是固定源，拒绝自动提升")
            return False
        await self.stable_repo.upsert(channel_name, url, latency, video_codec)
        logger.info(f"✅ {channel_name} 已提升为稳定源")
        return True

    async def get_active_sources(self):
        all_sources = await self.stable_repo.get_all()
        return {k: v for k, v in all_sources.items() if v["status"] == "active"}
