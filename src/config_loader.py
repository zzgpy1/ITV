import os
from pathlib import Path
from typing import Any, Dict, List
import yaml


class Config:
    def __init__(self):
        self._data = {}
        self._load_yaml()
        self._apply_env()
        self._defaults()
        self._post_process()

    def _load_yaml(self):
        yaml_path = Path("config/config.yaml")
        if yaml_path.exists():
            try:
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    self._data = yaml.safe_load(f) or {}
                print(f"✅ 已加载配置: {yaml_path}")
            except Exception as e:
                print(f"⚠️ 加载配置失败: {e}")

    def _apply_env(self):
        for key, val in list(self._data.items()):
            env_val = os.getenv(key.upper())
            if env_val is not None:
                if isinstance(val, bool):
                    self._data[key] = env_val.lower() in ('true', '1', 'yes')
                elif isinstance(val, int):
                    self._data[key] = int(env_val)
                elif isinstance(val, float):
                    self._data[key] = float(env_val)
                elif isinstance(val, list):
                    self._data[key] = [x.strip() for x in env_val.split(',') if x.strip()]
                else:
                    self._data[key] = env_val

    def _defaults(self):
        defaults = {
            'root_dir': '.',
            'data_dir': 'data',
            'output_dir': 'output',
            'max_workers': 20,
            'timeout': 8,
            'http_timeout': 8,
            'fetch_timeout': 20,
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
            'max_retry_before_blacklist': 3,
            'freeze_retest_hours': 2,
            'freeze_retest_max_hours': 24,
            'slow_speed_threshold': 3000,
            'download_chunk_size': 262144,
            'host_cache_ttl_seconds': 300,
            'final_verify_enable': True,
            'autonomous_mode': True,
            'candidate_min_success': 3,
            'candidate_min_success_rate': 0.5,
            'candidate_max_latency': 3000,
            'enable_fixed_optimization': True,
            'fixed_optimization_threshold': 200,
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
            'source_groups': {
                'core': {
                    'enabled': True,
                    'timeout': 20,
                    'sources': [
                        'https://raw.githubusercontent.com/iptv-org/iptv/refs/heads/master/streams/cn.m3u',
                        'https://raw.githubusercontent.com/iptv-org/iptv/gh-pages/countries/cn.m3u',
                        'https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt',
                        'https://raw.githubusercontent.com/zzgpy1/Collect-IPTV/main/best_sorted.m3u',
                        'https://raw.githubusercontent.com/zzgpy1/ipv6-iptv/master/tv/iptv4.txt',
                        'https://raw.githubusercontent.com/kakaxi-1/IPTV/main/iptv.txt',
                        'https://raw.githubusercontent.com/zzgpy1/iptv-pro/main/iptv.txt',
                    ]
                },
                'local': {'enabled': False, 'timeout': 20, 'sources': [
                    'https://raw.githubusercontent.com/CCSH/IPTV/refs/heads/main/live.txt'
                ]},
                'experimental': {'enabled': False, 'timeout': 20, 'sources': [
                    'https://tv.19860519.xyz/xymm',
                    'https://iptv.19860519.xyz/result.txt'
                ]},
            },
        }
        for k, v in defaults.items():
            if k not in self._data or self._data[k] is None:
                self._data[k] = v

    def _post_process(self):
        for key in ['root_dir', 'data_dir', 'output_dir', 'subscribe_file',
                    'whitelist_file', 'blacklist_file', 'alias_file', 'demo_file']:
            if key in self._data:
                self._data[key] = Path(self._data[key])
        # 兼容旧 iptv_sources
        raw = self._data.get('raw_sources', [])
        direct = self._data.get('direct_sources', [])
        self._data['iptv_sources'] = list(raw) + list(direct)

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def __getattr__(self, name):
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"Config has no attribute '{name}'")

    def to_dict(self):
        return self._data.copy()

    # ---------- 源分组辅助方法（新增） ----------
    def get_source_groups(self) -> Dict[str, Dict]:
        """返回所有源分组配置"""
        return self._data.get('source_groups', {}) or {}

    def get_enabled_group_sources(self) -> List[str]:
        """返回所有启用的分组内源 URL 列表"""
        urls = []
        for name, group in self.get_source_groups().items():
            if not isinstance(group, dict):
                continue
            if not group.get('enabled', True):
                continue
            for u in group.get('sources', []) or []:
                if u and u not in urls:
                    urls.append(u)
        return urls

    def get_group_timeout(self, url: str) -> int:
        """根据 URL 找到所属分组，返回该分组的超时设置"""
        for name, group in self.get_source_groups().items():
            if not isinstance(group, dict):
                continue
            if url in (group.get('sources') or []):
                return int(group.get('timeout', self._data.get('fetch_timeout', 20)))
        return int(self._data.get('fetch_timeout', 20))


config = Config()
