import os
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field

class Settings(BaseModel):
    # 路径
    root_dir: Path = Field(default=".")
    data_dir: Path = Field(default="data")
    output_dir: Path = Field(default="output")
    config_dir: Path = Field(default="config")
    
    # 性能
    max_workers: int = Field(default=20)
    timeout: int = Field(default=8)
    http_timeout: int = Field(default=8)
    
    # ffmpeg
    ffmpeg_enable: bool = Field(default=True)
    ffmpeg_mode: str = Field(default="deep")
    ffprobe_cache_hours: int = Field(default=168)
    
    # 缓存
    cache_hours: int = Field(default=24)
    cache_raw_hours: int = Field(default=48)
    cache_speed_hours: int = Field(default=24)
    
    # 功能开关
    enable_demo_filter: bool = Field(default=True)
    enable_alias: bool = Field(default=True)
    enable_blacklist: bool = Field(default=True)
    enable_database: bool = Field(default=True)
    enable_json_output: bool = Field(default=True)
    enable_lite_version: bool = Field(default=True)
    
    # 合并
    max_sources_per_channel: int = Field(default=3)
    
    # 测速
    max_retry_before_blacklist: int = Field(default=2)
    slow_speed_threshold: int = Field(default=3000)
    download_chunk_size: int = Field(default=262144)
    
    # 自治模式
    autonomous_mode: bool = Field(default=True)
    auto_update_stable: bool = Field(default=True)
    auto_replace_failed: bool = Field(default=True)
    quality_check_interval: int = Field(default=24)
    candidate_observation_hours: int = Field(default=24)
    candidate_min_success: int = Field(default=3)
    candidate_min_success_rate: float = Field(default=0.5)
    candidate_max_latency: int = Field(default=3000)
    auto_promote_threshold: int = Field(default=3)
    
    # 固定源优化
    enable_fixed_optimization: bool = Field(default=True)
    fixed_optimization_threshold: int = Field(default=200)
    
    # 订阅源
    subscribe_file: Path = Field(default="config/subscribe.txt")
    whitelist_file: Path = Field(default="config/whitelist.txt")
    blacklist_file: Path = Field(default="config/blacklist.txt")
    alias_file: Path = Field(default="config/alias.txt")
    demo_file: Path = Field(default="config/demo.txt")
    
    # 代理
    enable_github_proxy: bool = Field(default=False)
    github_raw_proxies: List[str] = Field(default=[
        "https://ghproxy.net/",
        "https://gh-proxy.19860519.xyz/",
        "https://raw.kkgithub.com/"
    ])
    github_proxy_timeout: int = Field(default=15)
    
    # 默认源
    raw_sources: List[str] = Field(default=[
        "https://raw.githubusercontent.com/iptv-org/iptv/refs/heads/master/streams/cn.m3u",
        "https://raw.githubusercontent.com/iptv-org/iptv/gh-pages/countries/cn.m3u",
        "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt",
        "https://raw.githubusercontent.com/zzgpy1/iptv-api/master/output/result.txt",
        "https://raw.githubusercontent.com/zzgpy1/Collect-IPTV/main/best_sorted.m3u",
        "https://raw.githubusercontent.com/zzgpy1/ipv6-iptv/master/tv/iptv4.txt",
        "https://raw.githubusercontent.com/CCSH/IPTV/refs/heads/main/live.txt",
        "https://raw.githubusercontent.com/kakaxi-1/IPTV/main/iptv.txt",
    ])
    direct_sources: List[str] = Field(default=["https://tv.19860519.xyz/abc123"])

    class Config:
        extra = "ignore"

def _parse_env() -> dict:
    """从环境变量读取配置，覆盖默认值"""
    env_vars = {}
    for field_name, field_info in Settings.__fields__.items():
        env_name = f"IPTV_{field_name.upper()}"
        value = os.environ.get(env_name)
        if value is not None:
            # 根据字段类型进行转换
            if field_info.type_ == bool:
                env_vars[field_name] = value.lower() in ('true', '1', 'yes')
            elif field_info.type_ == int:
                try:
                    env_vars[field_name] = int(value)
                except ValueError:
                    pass  # 保持默认
            elif field_info.type_ == float:
                try:
                    env_vars[field_name] = float(value)
                except ValueError:
                    pass
            elif field_info.type_ == Path:
                env_vars[field_name] = Path(value)
            elif field_info.type_ == list:
                if value:
                    env_vars[field_name] = [item.strip() for item in value.split(',') if item.strip()]
                else:
                    env_vars[field_name] = []
            else:
                env_vars[field_name] = value
    return env_vars

# 使用默认值创建实例，再用环境变量覆盖
settings = Settings(**_parse_env())
