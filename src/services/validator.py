# src/services/validator.py
"""验证服务 - ffmpeg 深度验证"""

import asyncio
import json
import subprocess
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from src.core.config import get_config
from src.core.exceptions import ValidationError
from src.infrastructure.database import get_db
from src.infrastructure.logger import get_logger

logger = get_logger(__name__)


class Validator:
    """验证器"""
    
    def __init__(self):
        self.config = get_config()
        self._ffprobe_available = None
    
    async def check_ffprobe(self) -> bool:
        """检查 ffprobe 是否可用"""
        if self._ffprobe_available is not None:
            return self._ffprobe_available
        
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    ["ffprobe", "-version"],
                    capture_output=True,
                    timeout=5,
                    text=True
                )
            )
            self._ffprobe_available = result.returncode == 0
            if self._ffprobe_available:
                logger.info("✅ ffprobe 可用")
            else:
                logger.warning("⚠️ ffprobe 不可用，跳过深度验证")
            return self._ffprobe_available
        except Exception:
            self._ffprobe_available = False
            return False
    
    async def validate_with_ffprobe(self, url: str, timeout: int = 10) -> Dict:
        """使用 ffprobe 验证"""
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-analyzeduration", "5000000",
            "-probesize", "5000000", url
        ]
        
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(cmd, capture_output=True, timeout=timeout, text=True)
            )
            
            if result.returncode != 0:
                return {"valid": False, "has_video": False, "video_codec": ""}
            
            data = json.loads(result.stdout)
            streams = data.get("streams", [])
            
            for s in streams:
                if s.get("codec_type") == "video":
                    return {
                        "valid": True,
                        "has_video": True,
                        "video_codec": s.get("codec_name", "").lower()
                    }
            
            return {"valid": False, "has_video": False, "video_codec": ""}
            
        except Exception as e:
            logger.debug(f"ffprobe 验证失败 {url}: {e}")
            return {"valid": False, "has_video": False, "video_codec": ""}
    
    async def validate_batch(self, channels: List[Dict]) -> List[Dict]:
        """批量验证"""
        if not self.config.ffmpeg_enable:
            logger.info("⚙️ ffmpeg 深度验证已禁用")
            return channels
        
        if not await self.check_ffprobe():
            logger.warning("⚠️ ffprobe 不可用，跳过深度验证")
            return channels
        
        db = await get_db()
        valid = []
        
        for i, ch in enumerate(channels):
            # 检查缓存
            cached = await db.fetch_one(
                "SELECT valid, video_codec FROM ffprobe_cache WHERE url = ?",
                (ch["url"],)
            )
            
            if cached and cached["valid"]:
                ch["video_codec"] = cached["video_codec"]
                valid.append(ch)
                continue
            
            # 验证
            result = await self.validate_with_ffprobe(ch["url"])
            
            # 缓存结果
            await db.execute(
                """INSERT OR REPLACE INTO ffprobe_cache 
                   (url, valid, video_codec, has_video, updated_at) 
                   VALUES (?, ?, ?, ?, ?)""",
                (ch["url"], result["valid"], result["video_codec"], result["has_video"], datetime.now().isoformat())
            )
            
            if result["valid"]:
                ch["video_codec"] = result["video_codec"]
                valid.append(ch)
            
            if (i + 1) % 50 == 0:
                logger.info(f"  🎬 验证进度: {i+1}/{len(channels)}")
        
        logger.info(f"✅ ffmpeg 验证完成: {len(valid)}/{len(channels)}")
        return valid
