# src/source_pool/models.py
"""源池数据模型"""

from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional
import hashlib


class SourceStatus:
    """源状态常量"""
    PENDING = "pending"      # 待验证
    VERIFIED = "verified"    # 已验证通过
    FAILED = "failed"        # 验证失败
    PROMOTED = "promoted"    # 已提升到候选版
    OBSOLETE = "obsolete"    # 已废弃


@dataclass
class RawSource:
    """原始源记录"""
    url: str
    channel_name: str
    source_url: str          # 来自哪个源文件
    discovered_at: datetime
    status: str = SourceStatus.PENDING
    fail_count: int = 0
    success_count: int = 0
    last_check: Optional[datetime] = None
    latency: int = 0
    video_codec: str = ""
    
    def get_key(self) -> str:
        """生成唯一键"""
        return hashlib.md5(f"{self.channel_name}|{self.url}".encode()).hexdigest()
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)
