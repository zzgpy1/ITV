# src/core/__init__.py
"""核心模块"""

# 延迟导入避免循环依赖
from src.core.config import get_config, AppConfig
from src.core.constants import (
    CATEGORY_CCTV,
    CATEGORY_SATELLITE,
    CATEGORY_LOCAL,
    CATEGORY_HKMT,
    CATEGORY_OTHER,
    OUTPUT_CATEGORY_ORDER,
    CCTV_ORDER,
    PROVINCES,
    HK_MACAU_TAIWAN_KEYWORDS,
)
from src.core.exceptions import (
    IPTVError,
    ConfigError,
    DatabaseError,
    FetchError,
    ParseError,
    ValidationError,
    SpeedTestError,
    ChannelNotFoundError,
    FixedSourceError,
    handle_exception,
)
from src.core.types import Channel, ChannelGroup, SourceInfo, QualityReport, Stats

__all__ = [
    "get_config",
    "AppConfig",
    "Channel",
    "ChannelGroup",
    "SourceInfo",
    "QualityReport",
    "Stats",
    "IPTVError",
    "ConfigError",
    "DatabaseError",
    "FetchError",
    "ParseError",
    "ValidationError",
    "SpeedTestError",
    "ChannelNotFoundError",
    "FixedSourceError",
    "handle_exception",
    "CATEGORY_CCTV",
    "CATEGORY_SATELLITE",
    "CATEGORY_LOCAL",
    "CATEGORY_HKMT",
    "CATEGORY_OTHER",
    "OUTPUT_CATEGORY_ORDER",
    "CCTV_ORDER",
    "PROVINCES",
    "HK_MACAU_TAIWAN_KEYWORDS",
]
