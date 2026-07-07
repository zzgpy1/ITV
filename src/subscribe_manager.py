import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from src.config_loader import config
from src.logger import logger

class SubscribeManager:
    """
    管理订阅源文件（config/subscribe.txt），支持：
    - 普通订阅条目
    - [WHITELIST] 区块内的白名单条目
    - 每个条目可附加请求头（如 UA="xxx"）
    """
    def __init__(self, subscribe_file: Optional[Path] = None):
        self.subscribe_file = subscribe_file or Path(config.subscribe_file)
        self._url_pattern = re.compile(r'(https?://[^\s]+)')
        self._kv_pattern = re.compile(r'(?P<key>\w+)=(?P<value>[^\s]+)')

    def parse_subscribe_entries(self) -> Tuple[List[Dict], List[Dict]]:
        """
        解析订阅文件，返回 (普通条目列表, 白名单条目列表)
        每个条目：{'url': str, 'headers': dict}
        """
        if not self.subscribe_file.exists():
            logger.warning(f"⚠️ 订阅文件不存在: {self.subscribe_file}")
            return [], []

        inside_whitelist = False
        normal_entries = []
        whitelist_entries = []

        with open(self.subscribe_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # 节标记
                if line.startswith('[') and line.endswith(']'):
                    inside_whitelist = line.upper() == '[WHITELIST]'
                    continue

                # 提取 URL
                match = self._url_pattern.search(line)
                if not match:
                    continue
                url = match.group(0)
                remainder = line[match.end():].strip()

                # 提取键值对 (如 UA="Mozilla/5.0")
                headers = {}
                for kv in self._kv_pattern.finditer(remainder):
                    key = kv.group('key')
                    value = kv.group('value')
                    if key.lower() in ('ua', 'user-agent'):
                        headers['User-Agent'] = value
                    else:
                        headers[key] = value

                entry = {'url': url}
                if headers:
                    entry['headers'] = headers

                if inside_whitelist:
                    whitelist_entries.append(entry)
                else:
                    normal_entries.append(entry)

        logger.info(f"📋 订阅源解析：普通 {len(normal_entries)} 个，白名单 {len(whitelist_entries)} 个")
        return normal_entries, whitelist_entries

    def get_all_subscribe_urls(self) -> List[str]:
        """获取所有订阅源 URL（普通 + 白名单）"""
        normal, whitelist = self.parse_subscribe_entries()
        all_entries = normal + whitelist
        return [e['url'] for e in all_entries]

    def get_whitelist_urls(self) -> List[str]:
        """获取白名单 URL"""
        _, whitelist = self.parse_subscribe_entries()
        return [e['url'] for e in whitelist]

    def get_normal_urls(self) -> List[str]:
        """获取普通订阅 URL"""
        normal, _ = self.parse_subscribe_entries()
        return [e['url'] for e in normal]

    def get_entries_with_headers(self) -> List[Dict]:
        """获取所有条目（包含 headers）用于请求"""
        normal, whitelist = self.parse_subscribe_entries()
        return normal + whitelist
