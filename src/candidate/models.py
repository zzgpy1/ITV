# src/candidate/models.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

class CandidateStatus:
    OBSERVING = "observing"
    STABLE = "stable"
    PROMOTED = "promoted"
    REJECTED = "rejected"

@dataclass
class ObservationResult:
    source_key: str
    channel_name: str
    url: str
    status: str = CandidateStatus.OBSERVING
    check_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    total_latency: int = 0
    avg_latency: int = 0
    last_check: Optional[datetime] = None
    discovered_at: datetime = field(default_factory=datetime.now)  # 添加此字段
    promoted_at: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        total = self.success_count + self.fail_count
        if total == 0:
            return 0.0
        return self.success_count / total
    
    def to_dict(self):
        return {
            "source_key": self.source_key,
            "channel_name": self.channel_name,
            "url": self.url,
            "status": self.status,
            "check_count": self.check_count,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "total_latency": self.total_latency,
            "avg_latency": self.avg_latency,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "discovered_at": self.discovered_at.isoformat() if self.discovered_at else None,
            "promoted_at": self.promoted_at.isoformat() if self.promoted_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        # 处理日期字段
        if data.get("last_check") and isinstance(data["last_check"], str):
            data["last_check"] = datetime.fromisoformat(data["last_check"])
        if data.get("discovered_at") and isinstance(data["discovered_at"], str):
            data["discovered_at"] = datetime.fromisoformat(data["discovered_at"])
        elif not data.get("discovered_at"):
            data["discovered_at"] = datetime.now()
        if data.get("promoted_at") and isinstance(data["promoted_at"], str):
            data["promoted_at"] = datetime.fromisoformat(data["promoted_at"])
        return cls(**data)
