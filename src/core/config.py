# src/core/config.py
"""统一配置管理"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

# 尝试导入 yaml，如果失败则使用 json 后备
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    import json


@dataclass
class AppConfig:
    """应用配置"""
    # 路径
    root_dir: Path = field(default_factory=lambda: Path("."))
    data_dir: Path = field(default_factory=lambda: Path("data"))
    output_dir: Path = field(default_factory=lambda: Path("output"))
    
    # 性能
    max_workers: int = 20
    timeout: int = 8
    http_timeout: int = 8
    db_pool_size: int = 10
    
    # 功能开关
    autonomous_mode: bool = True
    enable_demo_filter: bool = True
    enable_alias: bool = True
    enable_blacklist: bool = True
    database_enable: bool = True
    ffmpeg_enable: bool = True
    ffmpeg_mode: str = "deep"
    enable_json_output: bool = True
    enable_lite_version: bool = True
    
    # 缓存
    cache_hours: int = 24
    cache_raw_hours: int = 48
    cache_speed_hours: int = 24
    ffprobe_cache_hours: int = 168
    
    # 合并
    max_sources_per_channel: int = 3
    
    # 测速
    slow_speed_threshold: int = 3000
    download_chunk_size: int = 262144
    max_retry_before_blacklist: int = 2
    
    # 候选源
    candidate_min_success: int = 3
    candidate_min_success_rate: float = 0.5
    candidate_max_latency: int = 3000
    auto_promote_threshold: int = 3
    
    # 固定源优化
    enable_fixed_optimization: bool = True
    fixed_optimization_threshold: int = 200
    
    # IPTV 源
    raw_sources: List[str] = field(default_factory=lambda: [
        "https://raw.githubusercontent.com/iptv-org/iptv/refs/heads/master/streams/cn.m3u",
        "https://raw.githubusercontent.com/iptv-org/iptv/gh-pages/countries/cn.m3u",
        "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt",
        "https://raw.githubusercontent.com/zzgpy1/Collect-IPTV/main/best_sorted.m3u",
        "https://raw.githubusercontent.com/zzgpy1/ipv6-iptv/master/tv/iptv4.txt",
        "https://raw.githubusercontent.com/CCSH/IPTV/refs/heads/main/live.txt",
        "https://raw.githubusercontent.com/kakaxi-1/IPTV/main/iptv.txt",
    ])
    direct_sources: List[str] = field(default_factory=lambda: [
        "https://tv.19860519.xyz/abc123",
    ])
    
    # 文件路径
    subscribe_file: Path = field(default_factory=lambda: Path("config/subscribe.txt"))
    alias_file: Path = field(default_factory=lambda: Path("config/alias.txt"))
    blacklist_file: Path = field(default_factory=lambda: Path("config/blacklist.txt"))
    demo_file: Path = field(default_factory=lambda: Path("config/demo.txt"))
    
    # 代理
    enable_github_proxy: bool = False
    github_proxy_timeout: int = 15
    github_raw_proxies: List[str] = field(default_factory=lambda: [
        "https://ghproxy.net/",
        "https://gh-proxy.19860519.xyz/",
        "https://raw.kkgithub.com/",
    ])
    
    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "AppConfig":
        """加载配置"""
        config_path = config_path or Path("config/config.yaml")
        data = {}
        
        # 1. 从 YAML 或 JSON 加载
        if config_path.exists():
            try:
                if HAS_YAML:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f) or {}
                else:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
            except Exception as e:
                print(f"⚠️ 加载配置文件失败: {e}")
        
        # 2. 从环境变量覆盖
        env_mapping = {
            "MAX_WORKERS": "max_workers",
            "TIMEOUT": "timeout",
            "HTTP_TIMEOUT": "http_timeout",
            "FFMPEG_ENABLE": "ffmpeg_enable",
            "FFMPEG_MODE": "ffmpeg_mode",
            "AUTONOMOUS_MODE": "autonomous_mode",
            "ENABLE_DEMO_FILTER": "enable_demo_filter",
            "ENABLE_ALIAS": "enable_alias",
            "ENABLE_BLACKLIST": "enable_blacklist",
            "DATABASE_ENABLE": "database_enable",
            "CACHE_HOURS": "cache_hours",
            "MAX_SOURCES_PER_CHANNEL": "max_sources_per_channel",
            "SLOW_SPEED_THRESHOLD": "slow_speed_threshold",
            "CANDIDATE_MIN_SUCCESS": "candidate_min_success",
            "CANDIDATE_MIN_SUCCESS_RATE": "candidate_min_success_rate",
            "CANDIDATE_MAX_LATENCY": "candidate_max_latency",
            "ENABLE_FIXED_OPTIMIZATION": "enable_fixed_optimization",
        }
        for env_key, config_key in env_mapping.items():
            if env_key in os.environ:
                value = os.environ[env_key]
                # 获取默认值类型
                default_val = getattr(cls, config_key, None)
                if isinstance(default_val, bool):
                    value = value.lower() in ('true', '1', 'yes')
                elif isinstance(default_val, int):
                    value = int(value)
                elif isinstance(default_val, float):
                    value = float(value)
                data[config_key] = value
        
        # 3. 创建实例
        config = cls(**data)
        
        # 4. 处理路径
        for key in ['root_dir', 'data_dir', 'output_dir', 'subscribe_file', 
                    'alias_file', 'blacklist_file', 'demo_file']:
            if hasattr(config, key):
                setattr(config, key, Path(getattr(config, key)))
        
        # 5. 确保目录存在
        config.data_dir.mkdir(parents=True, exist_ok=True)
        config.output_dir.mkdir(parents=True, exist_ok=True)
        
        return config
    
    @property
    def iptv_sources(self) -> List[str]:
        """获取所有 IPTV 源"""
        return list(self.raw_sources) + list(self.direct_sources)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, Path):
                result[key] = str(value)
            elif isinstance(value, list):
                result[key] = value.copy()
            else:
                result[key] = value
        return result


# 全局配置实例
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """获取全局配置实例"""
    global _config
    if _config is None:
        _config = AppConfig.load()
    return _config


def reload_config() -> AppConfig:
    """重新加载配置"""
    global _config
    _config = AppConfig.load()
    return _config
