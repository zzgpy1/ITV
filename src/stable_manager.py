# src/stable_manager.py
"""稳定版管理器 - 使用数据库存储稳定源"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.logger import logger
from src.config import (
    ENABLE_FIXED_OPTIMIZATION,
    FIXED_OPTIMIZATION_THRESHOLD,
)
from src.stable.models import StableSource, StableStatus


class StableManager:
    """稳定版管理器（数据库版）"""
    
    def __init__(self):
        self.db = None

    async def _ensure_db(self):
        if self.db is None:
            from src.database import get_db_cache
            self.db = await get_db_cache()

    async def get_stable_sources(self) -> Dict[str, Dict]:
        """获取所有稳定源"""
        await self._ensure_db()
        return await self.db.get_all_stable_sources()

    async def get_stable_source(self, channel_name: str) -> Optional[Dict]:
        """获取单个稳定源"""
        await self._ensure_db()
        return await self.db.get_stable_source(channel_name)

    async def promote_candidate(self, channel_name: str, url: str, latency: int, video_codec: str = '') -> bool:
        """将候选源提升为稳定源"""
        await self._ensure_db()
        existing = await self.db.get_stable_source(channel_name)
        if existing and existing.get('is_fixed'):
            logger.warning(f"⚠️ {channel_name} 是固定源，不允许自动替换")
            return False
        await self.db.upsert_stable_source(channel_name, url, latency, video_codec, is_fixed=False)
        logger.info(f"✅ {channel_name} 已提升为稳定源: {url[:80]}...")
        return True

    async def set_fixed_source(self, channel_name: str, url: str, auto_optimize: bool = True) -> bool:
        """设置固定源（用户明确保留，不会被自动替换）"""
        await self._ensure_db()
        if not url:
            return False
        # 检查是否已存在且是固定源
        existing = await self.db.get_stable_source(channel_name)
        if existing and existing.get('is_fixed') and existing.get('url') == url:
            return True
        await self.db.upsert_stable_source(channel_name, url, 0, '', is_fixed=True)
        logger.info(f"📌 {channel_name} 已设为固定源 (自动优化: {auto_optimize})")
        return True

    async def sync_fixed_sources(self):
        """从 fixed_sources.py 同步固定源到数据库"""
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
                if url:
                    existing = await self.db.get_stable_source(name)
                    if not existing or not existing.get('is_fixed'):
                        await self.db.upsert_stable_source(name, url, 0, '', is_fixed=True)
                        logger.info(f"📌 同步固定源: {name} -> {url[:50]}...")
        except ImportError:
            logger.warning("⚠️ fixed_sources.py 不存在，跳过固定源同步")
        except Exception as e:
            logger.warning(f"⚠️ 固定源同步失败: {e}")

    async def replace_source(self, channel_name: str, new_url: str, latency: int, video_codec: str = '') -> bool:
        """替换失效源（保留原有的 is_fixed 标记）"""
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
        """记录失败（可扩展：增加失败计数）"""
        # 目前数据库未存储失败计数，可后续扩展
        pass

    async def record_success(self, channel_name: str):
        """记录成功"""
        pass

    # ---------- 兼容旧接口（非异步） ----------
    def get_active_sources(self) -> Dict[str, Dict]:
        """同步获取活跃源（仅用于兼容，不建议）"""
        import asyncio
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.get_stable_sources())
