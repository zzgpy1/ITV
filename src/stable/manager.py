# src/stable/manager.py
from src.repositories import repo_factory
from src.fixed_sources import CCTV_FIXED_SOURCES, ENABLE_FIXED_SOURCES
from src.logger import logger


class StableManager:
    def __init__(self):
        self.stable_repo = None
        self._initialized = False

    async def _ensure_init(self):
        if not self._initialized:
            self.stable_repo = repo_factory.stable
            self._initialized = True

    async def init(self):
        await self._ensure_init()
        if ENABLE_FIXED_SOURCES:
            await self.sync_fixed_sources()

    async def sync_fixed_sources(self):
        await self._ensure_init()
        for name, urls in CCTV_FIXED_SOURCES.items():
            if isinstance(urls, list):
                url = urls[0] if urls else None
            else:
                url = urls
            if url:
                await self.stable_repo.upsert(
                    name, url, 50, "h264",
                    is_fixed=True, auto_optimize=True
                )
                logger.info(f"📌 固定源同步: {name}")

    async def get_stable_sources(self):
        await self._ensure_init()
        return await self.stable_repo.get_all()

    async def promote_candidate(self, channel_name: str, url: str, latency: int, video_codec: str = ""):
        await self._ensure_init()
        existing = await self.stable_repo.get(channel_name)
        if existing and existing.get("is_fixed", False):
            logger.debug(f"⚠️ {channel_name} 是固定源，拒绝自动提升")
            return False
        await self.stable_repo.upsert(channel_name, url, latency, video_codec)
        logger.info(f"✅ {channel_name} 已提升为稳定源")
        return True

    async def get_active_sources(self):
        await self._ensure_init()
        all_sources = await self.stable_repo.get_all()
        return {k: v for k, v in all_sources.items() if v.get("status") == "active"}
