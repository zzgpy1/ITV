# src/stable_manager.py
"""稳定版管理器 - 管理最终使用的稳定源"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.logger import logger
from src.config import OUTPUT_DIR, DATA_DIR, ENABLE_FIXED_OPTIMIZATION, FIXED_OPTIMIZATION_THRESHOLD
from src.stable.models import StableSource, StableStatus
from src.fixed_sources import CCTV_FIXED_SOURCES, ENABLE_FIXED_SOURCES


class StableManager:
    """稳定版管理器"""
    
    # 将稳定源状态文件保存在 data 目录，而不是 output
    STABLE_FILE = DATA_DIR / "stable_sources.json"
    
    def __init__(self):
        self.stable_sources: Dict[str, StableSource] = {}
        self.db = None  # 数据库连接（异步）
        self._load()
        # 注意：不再在 __init__ 中同步固定源，改为显式调用 sync_fixed_sources

    def _load(self):
        if self.STABLE_FILE.exists():
            try:
                with open(self.STABLE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for name, src in data.items():
                        self.stable_sources[name] = StableSource.from_dict(src)
                logger.info(f"✅ 加载 {len(self.stable_sources)} 个稳定源")
            except Exception as e:
                logger.warning(f"加载稳定源失败: {e}")

    def _save(self):
        try:
            data = {name: src.to_dict() for name, src in self.stable_sources.items()}
            with open(self.STABLE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存稳定源失败: {e}")

    async def _ensure_db(self):
        """确保数据库连接可用"""
        if self.db is None:
            from src.database import get_db_cache
            self.db = await get_db_cache()

    async def sync_fixed_sources(self):
        """从 fixed_sources.py 同步固定源到数据库（强制覆盖）"""
        if not ENABLE_FIXED_SOURCES:
            return
        await self._ensure_db()
        if self.db is None:
            logger.warning("⚠️ 数据库连接不可用，无法同步固定源")
            return
        try:
            for name, urls in CCTV_FIXED_SOURCES.items():
                if isinstance(urls, list):
                    url = urls[0] if urls else None
                else:
                    url = urls
                if url:
                    # 强制覆盖：无论是否存在，都设置为固定源
                    await self.db.upsert_stable_source(name, url, 50, 'h264', is_fixed=True)
                    logger.info(f"📌 同步固定源: {name} -> {url[:50]}...")
            logger.info("✅ 固定源同步完成")
        except Exception as e:
            logger.warning(f"⚠️ 固定源同步失败: {e}")

    def _sync_fixed_sources_sync(self):
        """同步固定源到 JSON 文件（兼容旧版）"""
        if not ENABLE_FIXED_SOURCES:
            return
        for name, urls in CCTV_FIXED_SOURCES.items():
            if isinstance(urls, list):
                url = urls[0] if urls else None
            else:
                url = urls
            if url:
                if name in self.stable_sources:
                    src = self.stable_sources[name]
                    if src.url != url:
                        src.url = url
                        src.is_fixed = True
                        src.auto_optimize = True
                        src.promoted_at = datetime.now()
                        logger.info(f"📌 更新固定源: {name} -> {url}")
                else:
                    self.set_fixed_source_sync(name, url, auto_optimize=True)
                    logger.info(f"📌 添加固定源: {name} -> {url}")
        self._save()

    def set_fixed_source_sync(self, channel_name: str, url: str, auto_optimize: bool = True) -> bool:
        """同步设置固定源（用于 JSON 存储）"""
        if not url:
            return False
        self.stable_sources[channel_name] = StableSource(
            channel_name=channel_name,
            url=url,
            latency=0,
            video_codec="",
            promoted_at=datetime.now(),
            is_fixed=True,
            auto_optimize=auto_optimize,
            status=StableStatus.ACTIVE
        )
        self._save()
        logger.info(f"📌 {channel_name} 已设为固定源 (自动优化: {auto_optimize})")
        return True

    async def get_stable_sources(self) -> Dict[str, Dict]:
        """获取所有稳定源（从数据库）"""
        await self._ensure_db()
        if self.db is None:
            return {}
        try:
            return await self.db.get_all_stable_sources()
        except Exception as e:
            logger.warning(f"获取稳定源失败: {e}")
            return {}

    async def get_stable_source(self, channel_name: str) -> Optional[Dict]:
        """获取单个稳定源（从数据库）"""
        await self._ensure_db()
        if self.db is None:
            return None
        try:
            return await self.db.get_stable_source(channel_name)
        except Exception as e:
            logger.warning(f"获取稳定源失败: {e}")
            return None

    async def promote_candidate(self, channel_name: str, url: str, latency: int, video_codec: str = '') -> bool:
        """提升候选源为稳定源（如果已存在且是固定源则不可覆盖）"""
        await self._ensure_db()
        if self.db is None:
            return False
        try:
            existing = await self.db.get_stable_source(channel_name)
            if existing and existing.get('is_fixed'):
                logger.warning(f"⚠️ {channel_name} 是固定源，不允许自动替换")
                return False
            await self.db.upsert_stable_source(channel_name, url, latency, video_codec, is_fixed=False)
            logger.info(f"✅ {channel_name} 已提升为稳定源")
            return True
        except Exception as e:
            logger.warning(f"提升稳定源失败: {e}")
            return False

    async def set_fixed_source(self, channel_name: str, url: str, latency: int = 0, video_codec: str = '') -> bool:
        """设置固定源（用户手动指定）"""
        await self._ensure_db()
        if self.db is None:
            return False
        try:
            await self.db.upsert_stable_source(channel_name, url, latency, video_codec, is_fixed=True)
            logger.info(f"📌 {channel_name} 已设为固定源")
            return True
        except Exception as e:
            logger.warning(f"设置固定源失败: {e}")
            return False

    async def replace_source(self, channel_name: str, new_url: str, latency: int, video_codec: str = '') -> bool:
        """替换稳定源（保留固定标记）"""
        await self._ensure_db()
        if self.db is None:
            return False
        try:
            existing = await self.db.get_stable_source(channel_name)
            if existing and existing.get('is_fixed'):
                logger.warning(f"⚠️ {channel_name} 是固定源，拒绝替换")
                return False
            is_fixed = existing.get('is_fixed', False) if existing else False
            await self.db.upsert_stable_source(channel_name, new_url, latency, video_codec, is_fixed=is_fixed)
            logger.info(f"🔄 {channel_name} 已替换为 {new_url[:50]}...")
            return True
        except Exception as e:
            logger.warning(f"替换稳定源失败: {e}")
            return False

    async def record_failure(self, channel_name: str):
        """记录失败（暂不实现）"""
        pass

    async def record_success(self, channel_name: str):
        """记录成功（暂不实现）"""
        pass

    def get_active_sources(self) -> Dict[str, StableSource]:
        """获取活跃稳定源（从内存 JSON，兼容旧逻辑）"""
        return {n: s for n, s in self.stable_sources.items() if s.status == StableStatus.ACTIVE and s.url}

    def get_output_channels(self) -> List[dict]:
        """获取输出频道列表（从内存 JSON）"""
        channels = []
        for name, src in self.stable_sources.items():
            if src.status == StableStatus.ACTIVE and src.url:
                channels.append({
                    "name": name,
                    "url": src.url,
                    "latency": src.latency,
                    "video_codec": src.video_codec,
                    "is_fixed": src.is_fixed,
                    "auto_optimize": src.auto_optimize
                })
        return channels

    def optimize_fixed_sources(self, all_sources_by_channel: Dict[str, List[Dict]], 
                               candidate_observer=None) -> int:
        """固定源优化（仅用于 JSON 模式）"""
        if not ENABLE_FIXED_OPTIMIZATION:
            return 0
        # 这里可以添加优化逻辑，但不关键
        return 0

    def set_auto_optimize(self, channel_name: str, enabled: bool) -> bool:
        """切换固定源的自动优化开关（JSON 模式）"""
        if channel_name not in self.stable_sources:
            return False
        src = self.stable_sources[channel_name]
        if not src.is_fixed:
            return False
        src.auto_optimize = enabled
        self._save()
        logger.info(f"🔄 {channel_name} 自动优化开关: {enabled}")
        return True

    def replace_source_sync(self, channel_name: str, new_url: str, latency: int, video_codec: str) -> bool:
        """同步替换（JSON 模式）"""
        current = self.stable_sources.get(channel_name)
        if current and current.is_fixed and not current.auto_optimize:
            logger.warning(f"⚠️ {channel_name} 是固定源且不允许自动优化，拒绝替换")
            return False
        old_url = current.url if current else "None"
        is_fixed = current.is_fixed if current else False
        auto_optimize = current.auto_optimize if current else False
        self.stable_sources[channel_name] = StableSource(
            channel_name=channel_name,
            url=new_url,
            latency=latency,
            video_codec=video_codec,
            promoted_at=datetime.now(),
            is_fixed=is_fixed,
            auto_optimize=auto_optimize,
            status=StableStatus.ACTIVE
        )
        self._save()
        logger.info(f"🔄 {channel_name} 已替换: {old_url[:50]}... -> {new_url[:50]}...")
        return True
