# src/core/types.py
"""类型定义"""

from typing import TypedDict, List, Optional, Dict, Any
from datetime import datetime


class Channel(TypedDict, total=False):
    """频道类型"""
    name: str
    url: str
    urls: List[str]
    group_title: str
    tvg_id: str
    tvg_logo: str
    latency: int
    video_codec: str
    speed: float
    demo_category: str
    demo_name: str
    is_fixed: bool
    auto_optimize: bool
    subcategory: str


class ChannelGroup(TypedDict):
    """频道分组"""
    name: str
    channels: List[Channel]


class SourceInfo(TypedDict):
    """源信息"""
    url: str
    channel_name: str
    source_url: str
    status: str
    latency: int
    success_count: int
    fail_count: int


class QualityReport(TypedDict):
    """质量报告"""
    channel_name: str
    status: str
    success_rate: float
    avg_latency: int
    sample_count: int
    consecutive_fails: int


class Stats(TypedDict):
    """统计信息"""
    total_channels: int
    total_sources: int
    categories: Dict[str, int]
    fixed_count: int
    stable_count: int
    candidate_count: int
    generated_at: str
