# src/settings.py
from pathlib import Path
from typing import List, Optional
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    # 路径
    root_dir: Path = Field(default=".")
    data_dir: Path = Field(default="data")
    output_dir: Path = Field(default="output")

    # 性能
    max_workers: int = Field(default=20, env="IPTV_MAX_WORKERS")
    timeout: int = Field(default=8, env="IPTV_TIMEOUT")
    http_timeout: int = Field(default=8, env="IPTV_HTTP_TIMEOUT")

    # ffmpeg
    ffmpeg_enable: bool = Field(default=True, env="IPTV_FFMPEG_ENABLE")
    ffmpeg_mode: str = Field(default="deep", env="IPTV_FFMPEG_MODE")  # deep/quick/off
    ffprobe_cache_hours: int = Field(default=168, env="IPTV_FFPROBE_CACHE_HOURS")

    # 缓存
    cache_hours: int = Field(default=24, env="IPTV_CACHE_HOURS")
    cache_raw_hours: int = Field(default=48, env="IPTV_CACHE_RAW_HOURS")
    cache_speed_hours: int = Field(default=24, env="IPTV_CACHE_SPEED_HOURS")

    # 功能开关
    enable_demo_filter: bool = Field(default=True, env="IPTV_ENABLE_DEMO_FILTER")
    enable_alias: bool = Field(default=True, env="IPTV_ENABLE_ALIAS")
    enable_blacklist: bool = Field(default=True, env="IPTV_ENABLE_BLACKLIST")
    enable_json_output: bool = Field(default=True, env="IPTV_ENABLE_JSON_OUTPUT")
    enable_lite_version: bool = Field(default=True, env="IPTV_ENABLE_LITE_VERSION")
    demo_match_mode: str = Field(default="contains", env="IPTV_DEMO_MATCH_MODE")

    # 合并
    max_sources_per_channel: int = Field(default=3, env="IPTV_MAX_SOURCES_PER_CHANNEL")

    # 测速与黑名单
    max_retry_before_blacklist: int = Field(default=2, env="IPTV_MAX_RETRY_BEFORE_BLACKLIST")
    slow_speed_threshold: int = Field(default=3000, env="IPTV_SLOW_SPEED_THRESHOLD")
    download_chunk_size: int = Field(default=262144, env="IPTV_DOWNLOAD_CHUNK_SIZE")

    # 自治模式
    autonomous_mode: bool = Field(default=True, env="IPTV_AUTONOMOUS_MODE")
    auto_update_stable: bool = Field(default=True, env="IPTV_AUTO_UPDATE_STABLE")
    auto_replace_failed: bool = Field(default=True, env="IPTV_AUTO_REPLACE_FAILED")
    quality_check_interval: int = Field(default=24, env="IPTV_QUALITY_CHECK_INTERVAL")
    candidate_observation_hours: int = Field(default=24, env="IPTV_CANDIDATE_OBSERVATION_HOURS")
    candidate_min_success: int = Field(default=3, env="IPTV_CANDIDATE_MIN_SUCCESS")
    candidate_min_success_rate: float = Field(default=0.5, env="IPTV_CANDIDATE_MIN_SUCCESS_RATE")
    candidate_max_latency: int = Field(default=3000, env="IPTV_CANDIDATE_MAX_LATENCY")
    auto_promote_threshold: int = Field(default=3, env="IPTV_AUTO_PROMOTE_THRESHOLD")

    # 固定源优化
    enable_fixed_optimization: bool = Field(default=True, env="IPTV_ENABLE_FIXED_OPTIMIZATION")
    fixed_optimization_threshold: int = Field(default=200, env="IPTV_FIXED_OPTIMIZATION_THRESHOLD")

    # 订阅源
    raw_sources: List[str] = Field(default=[
        "https://raw.githubusercontent.com/iptv-org/iptv/refs/heads/master/streams/cn.m3u",
        "https://raw.githubusercontent.com/iptv-org/iptv/gh-pages/countries/cn.m3u",
        "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt",
        "https://raw.githubusercontent.com/zzgpy1/iptv-api/master/output/result.txt",
        "https://raw.githubusercontent.com/zzgpy1/Collect-IPTV/main/best_sorted.m3u",
        "https://raw.githubusercontent.com/zzgpy1/ipv6-iptv/master/tv/iptv4.txt",
        "https://raw.githubusercontent.com/CCSH/IPTV/refs/heads/main/live.txt",
        "https://raw.githubusercontent.com/kakaxi-1/IPTV/main/iptv.txt",
        "https://tv.19860519.xyz/abc123",
    ], env="IPTV_RAW_SOURCES", env_delimiter=",")

    # 代理
    enable_github_proxy: bool = Field(default=False, env="IPTV_ENABLE_GITHUB_PROXY")
    github_raw_proxies: List[str] = Field(default=[
        "https://ghproxy.net/",
        "https://gh-proxy.19860519.xyz/",
        "https://raw.kkgithub.com/",
    ], env="IPTV_GITHUB_RAW_PROXIES", env_delimiter=",")
    github_proxy_timeout: int = Field(default=15, env="IPTV_GITHUB_PROXY_TIMEOUT")

    # 文件路径
    alias_file: Path = Field(default="config/alias.txt")
    blacklist_file: Path = Field(default="config/blacklist.txt")
    demo_file: Path = Field(default="config/demo.txt")
    subscribe_file: Path = Field(default="config/subscribe.txt")

    class Config:
        env_file = ".env"
        env_prefix = "IPTV_"
        extra = "ignore"


settings = Settings()
