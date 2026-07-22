from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class Source:
    """原始源"""
    channel_name: str
    url: str
    source_url: str
    discovered_at: datetime = field(default_factory=datetime.now)
    status: str = "pending"  # pending, verified, failed, promoted
    fail_count: int = 0
    success_count: int = 0
    last_check: Optional[datetime] = None
    latency: int = 0
    video_codec: str = ""

    def get_key(self) -> str:
        import hashlib
        return hashlib.md5(f"{self.channel_name}|{self.url}".encode()).hexdigest()

@dataclass
class Candidate:
    """候选源（观察中）"""
    source_key: str
    channel_name: str
    url: str
    status: str = "observing"  # observing, stable, promoted, rejected
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
        return self.success_count / total if total else 0.0

@dataclass
class StableSource:
    """稳定源"""
    channel_name: str
    url: str
    latency: int
    video_codec: str
    is_fixed: bool = False
    auto_optimize: bool = False
    promoted_at: datetime = field(default_factory=datetime.now)
    last_verified: Optional[datetime] = None
    fail_count: int = 0
    status: str = "active"  # active, degraded, failed

@dataclass
class ChannelCache:
    """速度缓存"""
    channel_key: str
    name: str
    url: str
    latency: int
    video_codec: str
    updated_at: datetime
