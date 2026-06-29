# src/stable/models.py
"""稳定版数据模型"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
auto_optimize: bool = False

class StableStatus:
    """稳定源状态"""
    ACTIVE = "active"          # 正常使用中
    DEGRADED = "degraded"      # 质量下降
    FAILED = "failed"          # 已失效
    REPLACED = "replaced"      # 已被替换


@dataclass
class StableSource:
    """稳定源记录"""
    channel_name: str
    url: str
    latency: int
    video_codec: str
    promoted_at: datetime
    is_fixed: bool = False      # 是否为固定源
    last_verified: Optional[datetime] = None
    fail_count: int = 0
    status: str = StableStatus.ACTIVE
    
    def to_dict(self):
        return {
            "channel_name": self.channel_name,
            "url": self.url,
            "latency": self.latency,
            "video_codec": self.video_codec,
            "promoted_at": self.promoted_at.isoformat(),
            "is_fixed": self.is_fixed,
            "last_verified": self.last_verified.isoformat() if self.last_verified else None,
            "fail_count": self.fail_count,
            "status": self.status
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        data["promoted_at"] = datetime.fromisoformat(data["promoted_at"])
        if data.get("last_verified"):
            data["last_verified"] = datetime.fromisoformat(data["last_verified"])
        return cls(**data)
