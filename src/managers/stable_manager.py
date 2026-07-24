# src/managers/stable_manager.py
"""稳定源管理器"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List

from src.infrastructure.logger import get_logger
from src.core.constants import FIXED_SOURCE_LATENCY, FIXED_SOURCE_CODEC

logger = get_logger(__name__)


class StableManager:
    """稳定源管理器"""
    
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self._stable_sources: Dict[str, Dict] = {}
        self._load()
    
    def _load(self):
        stable_file = self.data_dir / "stable_sources.json"
        if stable_file.exists():
            try:
                with open(stable_file, 'r', encoding='utf-8') as f:
                    self._stable_sources = json.load(f)
                logger.info(f"📦 加载稳定源: {len(self._stable_sources)} 个")
            except Exception as e:
                logger.warning(f"加载稳定源失败: {e}")
    
    def _save(self):
        stable_file = self.data_dir / "stable_sources.json"
        try:
            with open(stable_file, 'w', encoding='utf-8') as f:
                json.dump(self._stable_sources, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存稳定源失败: {e}")
    
    async def get_source(self, channel_name: str) -> Optional[Dict]:
        return self._stable_sources.get(channel_name)
    
    async def get_active_sources(self) -> Dict[str, Dict]:
        return {
            name: src for name, src in self._stable_sources.items()
            if src.get("status") == "active" and src.get("url")
        }
    
    async def promote(self, channel_name: str, url: str, latency: int, video_codec: str) -> bool:
        """提升为稳定源"""
        existing = self._stable_sources.get(channel_name)
        if existing and existing.get("is_fixed"):
            logger.warning(f"⚠️ {channel_name} 是固定源，不允许自动替换")
            return False
        
        self._stable_sources[channel_name] = {
            "channel_name": channel_name,
            "url": url,
            "latency": latency,
            "video_codec": video_codec,
            "is_fixed": False,
            "auto_optimize": True,
            "fail_count": 0,
            "status": "active",
            "promoted_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self._save()
        logger.info(f"✅ {channel_name} 已提升为稳定源")
        return True
    
    async def set_fixed(self, channel_name: str, url: str, latency: int = FIXED_SOURCE_LATENCY) -> bool:
        """设置固定源"""
        self._stable_sources[channel_name] = {
            "channel_name": channel_name,
            "url": url,
            "latency": latency,
            "video_codec": FIXED_SOURCE_CODEC,
            "is_fixed": True,
            "auto_optimize": True,
            "fail_count": 0,
            "status": "active",
            "promoted_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self._save()
        logger.info(f"📌 {channel_name} 已设为固定源")
        return True
    
    async def replace(self, channel_name: str, new_url: str, latency: int, video_codec: str) -> bool:
        """替换稳定源"""
        existing = self._stable_sources.get(channel_name)
        if existing and existing.get("is_fixed"):
            logger.warning(f"⚠️ {channel_name} 是固定源，拒绝替换")
            return False
        
        is_fixed = existing.get("is_fixed", False) if existing else False
        auto_optimize = existing.get("auto_optimize", True) if existing else True
        
        self._stable_sources[channel_name] = {
            "channel_name": channel_name,
            "url": new_url,
            "latency": latency,
            "video_codec": video_codec,
            "is_fixed": is_fixed,
            "auto_optimize": auto_optimize,
            "fail_count": 0,
            "status": "active",
            "promoted_at": existing.get("promoted_at", datetime.now().isoformat()) if existing else datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self._save()
        logger.info(f"🔄 {channel_name} 已替换")
        return True
    
    async def record_failure(self, channel_name: str):
        if channel_name in self._stable_sources:
            src = self._stable_sources[channel_name]
            src["fail_count"] = src.get("fail_count", 0) + 1
            src["updated_at"] = datetime.now().isoformat()
            if src["fail_count"] >= 3 and not src.get("is_fixed"):
                src["status"] = "degraded"
                logger.warning(f"⚠️ {channel_name} 质量下降")
            self._save()
    
    async def record_success(self, channel_name: str):
        if channel_name in self._stable_sources:
            src = self._stable_sources[channel_name]
            src["fail_count"] = 0
            src["updated_at"] = datetime.now().isoformat()
            if src.get("status") == "degraded":
                src["status"] = "active"
            self._save()
