import asyncio
from datetime import datetime
from typing import Dict, Optional, Any
from src.logger import logger
from src.database import get_db_cache, DatabaseCache

class StableManager:
    """
    稳定源管理器，所有操作持久化到数据库。
    """
    def __init__(self):
        self.db: Optional[DatabaseCache] = None

    async def _ensure_db(self):
        if self.db is None:
            self.db = await get_db_cache()

    async def get_stable_sources(self) -> Dict[str, Dict]:
        """获取所有稳定源 {channel_name: {url, latency, video_codec, is_fixed, updated_at}}"""
        await self._ensure_db()
        return await self.db.get_all_stable_sources()

    async def get_stable_source(self, channel_name: str) -> Optional[Dict]:
        """获取单个稳定源"""
        await self._ensure_db()
        return await self.db.get_stable_source(channel_name)

    async def promote_candidate(self, channel_name: str, url: str, latency: int, video_codec: str = '') -> bool:
        """
        将候选源提升为稳定源（若已存在且为固定源则拒绝）
        """
        await self._ensure_db()
        existing = await self.db.get_stable_source(channel_name)
        if existing and existing.get('is_fixed'):
            logger.warning(f"⚠️ {channel_name} 是固定源，不允许自动替换")
            return False
        await self.db.upsert_stable_source(channel_name, url, latency, video_codec, is_fixed=False)
        logger.info(f"✅ {channel_name} 已提升为稳定源")
        return True

    async def set_fixed_source(self, channel_name: str, url: str, latency: int = 0, video_codec: str = '') -> bool:
        """手动设置固定源（强制覆盖）"""
        await self._ensure_db()
        await self.db.upsert_stable_source(channel_name, url, latency, video_codec, is_fixed=True)
        logger.info(f"📌 {channel_name} 已设为固定源")
        return True

    async def sync_fixed_sources(self):
        """从 fixed_sources.py 同步固定源到数据库（若不存在或非固定则添加）"""
        await self._ensure_db()
        try:
            from src.fixed_sources import CCTV_FIXED_SOURCES, ENABLE_FIXED_SOURCES
            if not ENABLE_FIXED_SOURCES:
                return
            for name, urls in CCTV_FIXED_SOURCES.items():
                if isinstance(urls, list):
                    url = urls[0] if urls else None
                else:
                    url = urls
                if not url:
                    continue
                existing = await self.db.get_stable_source(name)
                if not existing or not existing.get('is_fixed'):
                    await self.db.upsert_stable_source(name, url, 0, '', is_fixed=True)
                    logger.info(f"📌 固定源已同步: {name} -> {url[:50]}...")
        except ImportError:
            logger.warning("⚠️ fixed_sources.py 不存在，跳过同步")
        except Exception as e:
            logger.warning(f"⚠️ 固定源同步失败: {e}")

    async def replace_source(self, channel_name: str, new_url: str, latency: int, video_codec: str = '') -> bool:
        """替换稳定源（保留固定标记，若为固定源且不允许自动优化则拒绝）"""
        await self._ensure_db()
        existing = await self.db.get_stable_source(channel_name)
        if existing and existing.get('is_fixed'):
            # 检查是否允许自动优化（从额外字段读取，默认不允许）
            auto_optimize = existing.get('auto_optimize', False)
            if not auto_optimize:
                logger.warning(f"⚠️ {channel_name} 是固定源且不允许自动优化，拒绝替换")
                return False
        is_fixed = existing.get('is_fixed', False) if existing else False
        await self.db.upsert_stable_source(channel_name, new_url, latency, video_codec, is_fixed=is_fixed)
        logger.info(f"🔄 {channel_name} 已替换为 {new_url[:50]}...")
        return True

    async def record_failure(self, channel_name: str):
        """记录频道失败（可扩展）"""
        # 这里可以增加失败计数，暂不实现
        pass

    async def record_success(self, channel_name: str):
        """记录频道成功（可扩展）"""
        pass

    # 为了兼容旧代码，提供同步方法（不推荐，但可快速适配）
    def get_stable_sources_sync(self) -> Dict[str, Dict]:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.get_stable_sources())
