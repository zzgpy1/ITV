import os
import sys
from pathlib import Path
from typing import Any, Dict
from src.logger import logger

class Config:
    def __init__(self):
        self._data = {}
        self._load_from_yaml()
        self._load_from_env()
        self._apply_defaults()
        self._post_init()

    def _load_from_yaml(self):
        yaml_path = Path("config/config.yaml")
        if yaml_path.exists():
            try:
                import yaml
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    self._data = yaml.safe_load(f) or {}
                logger.info(f"✅ 已加载配置文件: {yaml_path}")
                return
            except ImportError:
                logger.warning("⚠️ pyyaml 未安装，无法读取 config.yaml，将使用环境变量和默认值")
            except Exception as e:
                logger.warning(f"⚠️ 读取 config.yaml 失败: {e}")
        else:
            logger.info("ℹ️ config/config.yaml 不存在，使用环境变量和默认值")

    def _load_from_env(self):
        """从环境变量覆盖配置（大写变量名）"""
        for key, value in list(self._data.items()):
            env_val = os.getenv(key.upper())
            if env_val is not None:
                if isinstance(value, bool):
                    self._data[key] = env_val.lower() in ('true', '1', 'yes')
                elif isinstance(value, int):
                    self._data[key] = int(env_val)
                elif isinstance(value, float):
                    self._data[key] = float(env_val)
                elif isinstance(value, list):
                    self._data[key] = [item.strip() for item in env_val.split(',') if item.strip()]
                else:
                    self._data[key] = env_val

    def _apply_defaults(self):
        """设置默认值（若未定义）"""
        defaults = {
            'root_dir': '.',
            'data_dir': 'data',
            'output_dir': 'output',
            'max_workers': 20,
            'timeout': 8,
            'http_timeout': 8,
            'ffmpeg_enable': True,
            'ffmpeg_mode': 'deep',
            'ffprobe_cache_hours': 168,
            'cache_hours': 24,
            'cache_raw_hours': 48,
            'cache_speed_hours': 24,
            'enable_demo_filter': True,
            'enable_alias': True,
            'enable_blacklist': True,
            'database_enable': True,
            'enable_incremental_fetch': True,
            'enable_json_output': True,
            'enable_lite_version': True,
            'enable_epg_output': True,
            'demo_match_mode': 'contains',
            'max_sources_per_channel': 3,
            'max_retry_before_blacklist': 2,
            'slow_speed_threshold': 3000,
            'download_chunk_size': 262144,
            'autonomous_mode': True,
            'auto_update_stable': True,
            'auto_replace_failed': True,
            'quality_check_interval': 24,
            'candidate_observation_hours': 24,
            'candidate_min_success': 3,
            'candidate_min_success_rate': 0.5,
            'candidate_max_latency': 3000,
            'auto_promote_threshold': 3,
            'health_history_days': 30,
            'predict_threshold': 0.6,
            'enable_fixed_optimization': True,
            'fixed_optimization_threshold': 200,
            'open_rtmp': False,
            'nginx_http_port': 8080,
            'nginx_rtmp_port': 1935,
            'rtmp_idle_timeout': 300,
            'rtmp_max_streams': 10,
            'rtmp_transcode_mode': 'copy',
            'open_epg': True,
            'open_subscribe_epg': True,
            'subscribe_file': 'config/subscribe.txt',
            'whitelist_file': 'config/whitelist.txt',
            'blacklist_file': 'config/blacklist.txt',
            'alias_file': 'config/alias.txt',
            'demo_file': 'config/demo.txt',
            'enable_github_proxy': False,
            'github_raw_proxies': [
                'https://ghproxy.net/',
                'https://gh-proxy.19860519.xyz/',
                'https://raw.kkgithub.com/',
            ],
            'github_proxy_timeout': 15,
            'raw_sources': [
                'https://raw.githubusercontent.com/iptv-org/iptv/refs/heads/master/streams/cn.m3u',
                'https://raw.githubusercontent.com/iptv-org/iptv/gh-pages/countries/cn.m3u',
                'https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt',
                'https://raw.githubusercontent.com/zzgpy1/iptv-api/master/output/result.txt',
                'https://raw.githubusercontent.com/zzgpy1/Collect-IPTV/main/best_sorted.m3u',
                'https://raw.githubusercontent.com/zzgpy1/ipv6-iptv/master/tv/iptv4.txt',
                'https://raw.githubusercontent.com/CCSH/IPTV/refs/heads/main/live.txt',
                'https://raw.githubusercontent.com/kakaxi-1/IPTV/main/iptv.txt',
            ],
            'direct_sources': [
                'https://tv.19860519.xyz/abc123',
            ],
        }
        for key, val in defaults.items():
            if key not in self._data or self._data[key] is None:
                self._data[key] = val

    def _post_init(self):
        """后处理：路径转换、派生属性"""
        for key in ['root_dir', 'data_dir', 'output_dir', 'subscribe_file', 'whitelist_file', 'blacklist_file', 'alias_file', 'demo_file']:
            if key in self._data:
                self._data[key] = Path(self._data[key])
        # 派生 IPTV_SOURCES = raw_sources + direct_sources
        raw = self._data.get('raw_sources', [])
        direct = self._data.get('direct_sources', [])
        self._data['iptv_sources'] = list(raw) + list(direct)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def __getattr__(self, name: str) -> Any:
        if name.startswith('_'):
            return super().__getattr__(name)
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"Config has no attribute '{name}'")

    def to_dict(self) -> Dict:
        return self._data.copy()

# 全局单例
config = Config()
