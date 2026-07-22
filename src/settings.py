from pathlib import Path
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    root_dir: Path = Field(default=".")
    data_dir: Path = Field(default="data")
    output_dir: Path = Field(default="output")

    max_workers: int = 20
    timeout: int = 8
    http_timeout: int = 8
    ffmpeg_enable: bool = True
    ffmpeg_mode: str = "deep"
    ffprobe_cache_hours: int = 168

    cache_hours: int = 24
    cache_raw_hours: int = 48
    cache_speed_hours: int = 24

    enable_demo_filter: bool = True
    enable_alias: bool = True
    enable_blacklist: bool = True
    database_enable: bool = True
    enable_incremental_fetch: bool = True
    enable_json_output: bool = True
    enable_lite_version: bool = True
    demo_match_mode: str = "contains"

    max_sources_per_channel: int = 3
    max_retry_before_blacklist: int = 2
    slow_speed_threshold: int = 3000
    download_chunk_size: int = 262144

    autonomous_mode: bool = True
    auto_update_stable: bool = True
    auto_replace_failed: bool = True
    quality_check_interval: int = 24
    candidate_observation_hours: int = 24
    candidate_min_success: int = 3
    candidate_min_success_rate: float = 0.5
    candidate_max_latency: int = 3000
    auto_promote_threshold: int = 3

    health_history_days: int = 30
    predict_threshold: float = 0.6

    enable_fixed_optimization: bool = True
    fixed_optimization_threshold: int = 200

    subscribe_file: Path = Field(default="config/subscribe.txt")
    whitelist_file: Path = Field(default="config/whitelist.txt")
    blacklist_file: Path = Field(default="config/blacklist.txt")
    alias_file: Path = Field(default="config/alias.txt")
    demo_file: Path = Field(default="config/demo.txt")

    enable_github_proxy: bool = False
    github_raw_proxies: List[str] = [
        "https://ghproxy.net/",
        "https://gh-proxy.19860519.xyz/",
        "https://raw.kkgithub.com/",
    ]
    github_proxy_timeout: int = 15

    raw_sources: List[str] = [
        "https://raw.githubusercontent.com/iptv-org/iptv/refs/heads/master/streams/cn.m3u",
        "https://raw.githubusercontent.com/iptv-org/iptv/gh-pages/countries/cn.m3u",
        "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt",
        "https://raw.githubusercontent.com/zzgpy1/iptv-api/master/output/result.txt",
        "https://raw.githubusercontent.com/zzgpy1/Collect-IPTV/main/best_sorted.m3u",
        "https://raw.githubusercontent.com/zzgpy1/ipv6-iptv/master/tv/iptv4.txt",
        "https://raw.githubusercontent.com/CCSH/IPTV/refs/heads/main/live.txt",
        "https://raw.githubusercontent.com/kakaxi-1/IPTV/main/iptv.txt",
    ]
    direct_sources: List[str] = [
        "https://tv.19860519.xyz/abc123",
    ]

    class Config:
        env_file = ".env"
        env_prefix = "IPTV_"
        extra = "ignore"

    @property
    def iptv_sources(self) -> List[str]:
        return list(self.raw_sources) + list(self.direct_sources)


settings = Settings()
