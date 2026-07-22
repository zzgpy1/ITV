import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from src.settings import settings
from src.logger import logger

class SubscribeManager:
    def __init__(self, subscribe_file: Optional[Path] = None):
        self.subscribe_file = subscribe_file or settings.subscribe_file
        self._url_pattern = re.compile(r'(https?://[^\s]+)')
        self._kv_pattern = re.compile(r'(?P<key>\w+)=(?P<value>[^\s]+)')

    def parse_subscribe_entries(self) -> Tuple[List[Dict], List[Dict]]:
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
                if line.startswith('[') and line.endswith(']'):
                    inside_whitelist = line.upper() == '[WHITELIST]'
                    continue

                match = self._url_pattern.search(line)
                if not match:
                    continue
                url = match.group(0)
                remainder = line[match.end():].strip()

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
        normal, whitelist = self.parse_subscribe_entries()
        return [e['url'] for e in normal + whitelist]
