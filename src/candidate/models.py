# src/candidate/models.py
"""候选版数据模型"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


class CandidateStatus:
    """候选源状态"""
    OBSERVING = "observing"    # 观察中
    STABLE = "stable"          # 已稳定
    REJECTED = "rejected"      # 被拒绝
    PROMOTED = "promoted"      # 已提升到稳定版


@dataclass
class ObservationResult:
    """观察结果"""
    source_key: str
    channel_name: str
    url: str
    check_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    total_latency: int = 0
    last_check: Optional[datetime] = None
    status: str = CandidateStatus.OBSERVING
    promoted_at: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        if self.check_count == 0:
            return 0.0
        return self.success_count / self.check_count
    
    @property
    def avg_latency(self) -> int:
        if self.success_count == 0:
            return 9999
        return self.total_latency // self.success_count
    
    def to_dict(self):
        return {
            "source_key": self.source_key,
            "channel_name": self.channel_name,
            "url": self.url,
            "check_count": self.check_count,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "total_latency": self.total_latency,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "status": self.status,
            "promoted_at": self.promoted_at.isoformat() if self.promoted_at else None
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        if data.get("last_check"):
            data["last_check"] = datetime.fromisoformat(data["last_check"])
        if data.get("promoted_at"):
            data["promoted_at"] = datetime.fromisoformat(data["promoted_at"])
        return cls(**data)
