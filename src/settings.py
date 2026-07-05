# src/settings.py
"""统一配置管理 - 从环境变量加载并校验"""

import os
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path


@dataclass
class Settings:
    # ---------- 路径 ----------
    ROOT_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = ROOT_DIR / "data"
    OUTPUT_DIR: Path = ROOT_DIR / "output"

    # ---------- 性能 ----------
    MAX_WORKERS: int = 20
    TIMEOUT: int = 8
    HTTP_TIMEOUT: int = 8

    # ---------- ffmpeg ----------
    FFMPEG_ENABLE: bool = True
    FFMPEG_MODE: str = "deep"
    FFPROBE_CACHE_HOURS: int = 168
    FFMPEG_WORKERS: int = 5

    # ---------- 缓存 ----------
    CACHE_HOURS: int = 24
    CACHE_RAW_HOURS: int = 48
    CACHE_SPEED_HOURS: int = 24

    # ---------- 功能开关 ----------
    ENABLE_DEMO_FILTER: bool = True
    ENABLE_ALIAS: bool = True
    ENABLE_BLACKLIST: bool = True
    DATABASE_ENABLE: bool = True
    ENABLE_INCREMENTAL_FETCH: bool = True
    ENABLE_JSON_OUTPUT: bool = True
    ENABLE_LITE_VERSION: bool = True
    ENABLE_EPG_OUTPUT: bool = True
    DEMO_MATCH_MODE: str = "contains"

    # ---------- 合并 ----------
    MAX_SOURCES_PER_CHANNEL: int = 3

    # ---------- 测速与黑名单 ----------
    MAX_RETRY_BEFORE_BLACKLIST: int = 2
    SLOW_SPEED_THRESHOLD: int = 3000
    DOWNLOAD_CHUNK_SIZE: int = 262144

    # ---------- 自治模式 ----------
    AUTONOMOUS_MODE: bool = False
    AUTO_UPDATE_STABLE: bool = True
    AUTO_REPLACE_FAILED: bool = True
    QUALITY_CHECK_INTERVAL: int = 24
    CANDIDATE_OBSERVATION_HOURS: int = 24
    CANDIDATE_MIN_SUCCESS: int = 3
    CANDIDATE_MIN_SUCCESS_RATE: float = 0.5
    CANDIDATE_MAX_LATENCY: int = 3000
    AUTO_PROMOTE_THRESHOLD: int = 3

    # ---------- 健康预测 ----------
    HEALTH_HISTORY_DAYS: int = 30
    PREDICT_THRESHOLD: float = 0.6

    # ---------- 固定源优化 ----------
    ENABLE_FIXED_OPTIMIZATION: bool = True
    FIXED_OPTIMIZATION_THRESHOLD: int = 200

    # ---------- IPTV 源列表 ----------
    RAW_SOURCES: List[str] = field(default_factory=lambda: [
        "https://raw.githubusercontent.com/iptv-org/iptv/refs/heads/master/streams/cn.m3u",
        "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt",
        "https://raw.githubusercontent.com/zzgpy1/iptv-api/master/output/result.txt",
        "https://raw.githubusercontent.com/zzgpy1/Collect-IPTV/main/best_sorted.m3u",
        "https://raw.githubusercontent.com/zzgpy1/ipv6-iptv/master/tv/iptv4.txt",
        "https://raw.githubusercontent.com/CCSH/IPTV/refs/heads/main/live.txt",
       ])
    DIRECT_SOURCES: List[str] = field(default_factory=lambda: [
        "https://tv.19860519.xyz/abc123",
    ])

    # ---------- GitHub 代理 ----------
    ENABLE_GITHUB_PROXY: bool = False
    GITHUB_RAW_PROXIES: List[str] = field(default_factory=lambda: [
        "https://ghproxy.net/",
        "https://gh-proxy.19860519.xyz/",
        "https://raw.kkgithub.com/",
    ])
    GITHUB_PROXY_TIMEOUT: int = 15

    # ---------- 其他 ----------
    HEADERS: dict = field(default_factory=lambda: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })

    def __post_init__(self):
        self.FFMPEG_WORKERS = min(self.MAX_WORKERS, 5)
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.IPTV_SOURCES = []
        for src in self.RAW_SOURCES:
            if self.ENABLE_GITHUB_PROXY and "raw.githubusercontent.com" in src:
                proxy = self.GITHUB_RAW_PROXIES[0] if self.GITHUB_RAW_PROXIES else ""
                self.IPTV_SOURCES.append(proxy + src if proxy else src)
            else:
                self.IPTV_SOURCES.append(src)
        self.IPTV_SOURCES.extend(self.DIRECT_SOURCES)


def load_settings() -> Settings:
    s = Settings()
    def _bool(val: Optional[str]) -> bool:
        return val.lower() in ("true", "1", "yes") if val else False
    def _int(val: Optional[str]) -> int:
        return int(val) if val and val.isdigit() else None
    env_map = {
        "MAX_WORKERS": ("MAX_WORKERS", int),
        "TIMEOUT": ("TIMEOUT", int),
        "HTTP_TIMEOUT": ("HTTP_TIMEOUT", int),
        "FFMPEG_ENABLE": ("FFMPEG_ENABLE", lambda x: _bool(x)),
        "FFMPEG_MODE": ("FFMPEG_MODE", str),
        "FFPROBE_CACHE_HOURS": ("FFPROBE_CACHE_HOURS", int),
        "CACHE_HOURS": ("CACHE_HOURS", int),
        "CACHE_RAW_HOURS": ("CACHE_RAW_HOURS", int),
        "CACHE_SPEED_HOURS": ("CACHE_SPEED_HOURS", int),
        "ENABLE_DEMO_FILTER": ("ENABLE_DEMO_FILTER", lambda x: _bool(x)),
        "ENABLE_ALIAS": ("ENABLE_ALIAS", lambda x: _bool(x)),
        "ENABLE_BLACKLIST": ("ENABLE_BLACKLIST", lambda x: _bool(x)),
        "DATABASE_ENABLE": ("DATABASE_ENABLE", lambda x: _bool(x)),
        "ENABLE_INCREMENTAL_FETCH": ("ENABLE_INCREMENTAL_FETCH", lambda x: _bool(x)),
        "ENABLE_JSON_OUTPUT": ("ENABLE_JSON_OUTPUT", lambda x: _bool(x)),
        "ENABLE_LITE_VERSION": ("ENABLE_LITE_VERSION", lambda x: _bool(x)),
        "ENABLE_EPG_OUTPUT": ("ENABLE_EPG_OUTPUT", lambda x: _bool(x)),
        "DEMO_MATCH_MODE": ("DEMO_MATCH_MODE", str),
        "MAX_SOURCES_PER_CHANNEL": ("MAX_SOURCES_PER_CHANNEL", int),
        "MAX_RETRY_BEFORE_BLACKLIST": ("MAX_RETRY_BEFORE_BLACKLIST", int),
        "SLOW_SPEED_THRESHOLD": ("SLOW_SPEED_THRESHOLD", int),
        "DOWNLOAD_CHUNK_SIZE": ("DOWNLOAD_CHUNK_SIZE", int),
        "AUTONOMOUS_MODE": ("AUTONOMOUS_MODE", lambda x: _bool(x)),
        "AUTO_UPDATE_STABLE": ("AUTO_UPDATE_STABLE", lambda x: _bool(x)),
        "AUTO_REPLACE_FAILED": ("AUTO_REPLACE_FAILED", lambda x: _bool(x)),
        "QUALITY_CHECK_INTERVAL": ("QUALITY_CHECK_INTERVAL", int),
        "CANDIDATE_OBSERVATION_HOURS": ("CANDIDATE_OBSERVATION_HOURS", int),
        "CANDIDATE_MIN_SUCCESS": ("CANDIDATE_MIN_SUCCESS", int),
        "CANDIDATE_MIN_SUCCESS_RATE": ("CANDIDATE_MIN_SUCCESS_RATE", float),
        "CANDIDATE_MAX_LATENCY": ("CANDIDATE_MAX_LATENCY", int),
        "AUTO_PROMOTE_THRESHOLD": ("AUTO_PROMOTE_THRESHOLD", int),
        "HEALTH_HISTORY_DAYS": ("HEALTH_HISTORY_DAYS", int),
        "PREDICT_THRESHOLD": ("PREDICT_THRESHOLD", float),
        "ENABLE_FIXED_OPTIMIZATION": ("ENABLE_FIXED_OPTIMIZATION", lambda x: _bool(x)),
        "FIXED_OPTIMIZATION_THRESHOLD": ("FIXED_OPTIMIZATION_THRESHOLD", int),
        "ENABLE_GITHUB_PROXY": ("ENABLE_GITHUB_PROXY", lambda x: _bool(x)),
        "GITHUB_PROXY_TIMEOUT": ("GITHUB_PROXY_TIMEOUT", int),
    }
    for env_key, (attr_name, converter) in env_map.items():
        val = os.getenv(env_key)
        if val is not None:
            try:
                setattr(s, attr_name, converter(val) if callable(converter) else converter)
            except Exception:
                pass
    s.__post_init__()
    return s

settings = load_settings()
