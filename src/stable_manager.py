# src/stable_manager.py
"""稳定版管理器 - 管理最终使用的稳定源"""

from datetime import datetime
from typing import Dict, Optional
from src.logger import logger
from src.database import get_db_cache
from src.fixed_sources import CCTV_FIXED_SOURCES, ENABLE_FIXED_SOURCES
from src.config_loader import config


class StableManager:
    """稳定源管理器"""

    def __init__(self):
        self.db = None

    async def _ensure_db(self):
        """确保数据库连接已初始化"""
        if self.db is None:
            self.db = await get_db_cache()

    async def sync_fixed_sources(self):
        """从 fixed_sources.py 同步固定源到数据库（强制覆盖）"""
        if not ENABLE_FIXED_SOURCES:
            return
        await self._ensure_db()
        for name, urls in CCTV_FIXED_SOURCES.items():
            if isinstance(urls, list):
                url = urls[0] if urls else None
            else:
                url = urls
            if url:
                # 强制覆盖：无论是否存在，都设置为固定源
                await self.db.upsert_stable_source(name, url, 50, 'h264', is_fixed=True)
                logger.info(f"📌 同步固定源: {name} -> {url[:50]}...")

    async def get_stable_sources(self) -> Dict[str, Dict]:
        """获取所有稳定源"""
        await self._ensure_db()
        return await self.db.get_all_stable_sources()

    async def get_stable_source(self, channel_name: str) -> Optional[Dict]:
        """获取单个稳定源"""
        await self._ensure_db()
        return await self.db.get_stable_source(channel_name)

    async def promote_candidate(self, channel_name: str, url: str, latency: int, video_codec: str = '') -> bool:
        """提升候选源为稳定源（如果已存在且是固定源则不可覆盖）"""
        await self._ensure_db()
        existing = await self.db.get_stable_source(channel_name)
        if existing and existing.get('is_fixed'):
            logger.warning(f"⚠️ {channel_name} 是固定源，不允许自动替换")
            return False
        await self.db.upsert_stable_source(channel_name, url, latency, video_codec, is_fixed=False)
        logger.info(f"✅ {channel_name} 已提升为稳定源")
        return True

    async def set_fixed_source(self, channel_name: str, url: str, latency: int = 0, video_codec: str = '') -> bool:
        """设置固定源（用户手动指定）"""
        await self._ensure_db()
        await self.db.upsert_stable_source(channel_name, url, latency, video_codec, is_fixed=True)
        logger.info(f"📌 {channel_name} 已设为固定源")
        return True

    async def replace_source(self, channel_name: str, new_url: str, latency: int, video_codec: str = '') -> bool:
        """替换稳定源（保留固定标记）"""
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
        """记录频道失败（用于质量监控）"""
        # 可扩展实现
        pass

    async def record_success(self, channel_name: str):
        """记录频道成功（用于质量监控）"""
        pass

    def get_active_sources(self) -> Dict[str, Dict]:
        """获取活跃源（同步方法，实际使用需改为异步）"""
        # 注意：此方法为同步，仅用于兼容旧代码，建议使用异步方法
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            return loop.run_until_complete(self.get_stable_sources())
        except RuntimeError:
            import asyncio
            return asyncio.run(self.get_stable_sources())
