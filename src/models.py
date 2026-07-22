from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Source:
    source_key: str
    channel_name: str
    url: str
    source_url: str = ""
    discovered_at: datetime = field(default_factory=datetime.now)
    last_check: Optional[datetime] = None
    status: str = "pending"
    fail_count: int = 0
    success_count: int = 0
    latency: int = 0
    video_codec: str = ""


@dataclass
class Candidate:
    source_key: str
    channel_name: str
    url: str
    status: str = "observing"
    check_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    total_latency: int = 0
    avg_latency: int = 0
    last_check: Optional[datetime] = None
    discovered_at: datetime = field(default_factory=datetime.now)
    promoted_at: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.fail_count
        return 0 if total == 0 else self.success_count / total


@dataclass
class Stable:
    channel_name: str
    url: str
    latency: int = 0
    video_codec: str = ""
    is_fixed: bool = False
    auto_optimize: bool = False
    promoted_at: datetime = field(default_factory=datetime.now)
    last_verified: Optional[datetime] = None
    fail_count: int = 0
    status: str = "active"  # active / degraded / failed
