# src/stable_manager.py
import asyncio
from datetime import datetime
from typing import Dict, Optional
from src.database import get_db_cache
from src.logger import logger
from src.fixed_sources import CCTV_FIXED_SOURCES, ENABLE_FIXED_SOURCES

class StableManager:
    def __init__(self):
        self.db = None

    async def _ensure_db(self):
        if self.db is None:
            self.db = await get_db_cache()

    async def get_stable_sources(self) -> Dict[str, Dict]:
        await self._ensure_db()
        return await self.db.get_all_stable_sources()

    async def get_stable_source(self, channel_name: str) -> Optional[Dict]:
        await self._ensure_db()
        return await self.db.get_stable_source(channel_name)

    async def promote_candidate(self, channel_name: str, url: str, latency: int, video_codec: str = '') -> bool:
        await self._ensure_db()
        existing = await self.db.get_stable_source(channel_name)
        if existing and existing.get('is_fixed'):
            logger.warning(f"⚠️ {channel_name} 是固定源，不允许自动替换")
            return False
        await self.db.upsert_stable_source(channel_name, url, latency, video_codec, is_fixed=False)
        logger.info(f"✅ {channel_name} 已提升为稳定源")
        return True

    async def set_fixed_source(self, channel_name: str, url: str, latency: int = 0, video_codec: str = '') -> bool:
        await self._ensure_db()
        await self.db.upsert_stable_source(channel_name, url, latency, video_codec, is_fixed=True)
        logger.info(f"📌 {channel_name} 已设为固定源")
        return True

    async def sync_fixed_sources(self):
        if not ENABLE_FIXED_SOURCES:
            return
        await self._ensure_db()
        for name, urls in CCTV_FIXED_SOURCES.items():
            if isinstance(urls, list):
                url = urls[0] if urls else None
            else:
                url = urls
            if url:
                existing = await self.db.get_stable_source(name)
                if not existing or not existing.get('is_fixed'):
                    await self.db.upsert_stable_source(name, url, 0, '', is_fixed=True)
                    logger.info(f"📌 同步固定源: {name} -> {url[:50]}...")

    async def replace_source(self, channel_name: str, new_url: str, latency: int, video_codec: str = '') -> bool:
        await self._ensure_db()
        existing = await self.db.get_stable_source(channel_name)
        if existing and existing.get('is_fixed'):
            logger.warning(f"⚠️ {channel_name} 是固定源，拒绝替换")
            return False
        is_fixed = existing.get('is_fixed', False) if existing else False
        await self.db.upsert_stable_source(channel_name, new_url, latency, video_codec, is_fixed=is_fixed)
        logger.info(f"🔄 {channel_name} 已替换为 {new_url[:50]}...")
        return True

    async def record_failure(self, channel_name: str):
        # 可增加失败计数功能，这里简化
        pass

    async def record_success(self, channel_name: str):
        pass

    # 为了保持兼容，提供同步方法（不推荐使用）
    def get_stable_sources_sync(self) -> Dict[str, Dict]:
        # 实际项目中建议全面 async
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.get_stable_sources())
