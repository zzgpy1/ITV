# src/blacklist_filter.py
import re
from pathlib import Path
from typing import List, Union
from src.settings import settings
from src.logger import logger

class BlacklistFilter:
    def __init__(self, blacklist_file: Path = None):
        self.blacklist_file = blacklist_file or settings.blacklist_file
        self.patterns: List[Union[str, re.Pattern]] = []
        self._load()

    def _load(self):
        if not self.blacklist_file.exists():
            logger.warning(f"黑名单文件不存在: {self.blacklist_file}")
            return
        with open(self.blacklist_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if re.search(r'[\.\*\?\+\[\]\(\)\{\}\\]', line):
                    try:
                        self.patterns.append(re.compile(line, re.IGNORECASE))
                    except Exception:
                        pass
                else:
                    self.patterns.append(line.lower())
        logger.info(f"黑名单加载: {len(self.patterns)} 条规则")

    def is_blacklisted(self, url: str) -> bool:
        if not url:
            return False
        url_lower = url.lower()
        for p in self.patterns:
            if isinstance(p, re.Pattern):
                if p.search(url):
                    return True
            else:
                if p in url_lower:
                    return True
        return False

    def filter_channels(self, channels: list) -> list:
        original = len(channels)
        filtered = []
        for ch in channels:
            url = ch.get("url", "")
            if not self.is_blacklisted(url):
                filtered.append(ch)
        logger.info(f"黑名单过滤: {original} -> {len(filtered)}")
        return filtered

_filter = None

def get_blacklist_filter():
    global _filter
    if _filter is None:
        _filter = BlacklistFilter()
    return _filter
