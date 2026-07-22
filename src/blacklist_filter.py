import re
from typing import List, Union
from src.settings import settings


class BlacklistFilter:
    def __init__(self):
        self.patterns: List[Union[str, re.Pattern]] = []
        self._load()

    def _load(self):
        if not settings.blacklist_file.exists():
            return
        with open(settings.blacklist_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if re.search(r'[\.\*\?\+\[\]\(\)\{\}\\]', line):
                    try:
                        self.patterns.append(re.compile(line, re.I))
                    except:
                        pass
                else:
                    self.patterns.append(line.lower())

    def is_blacklisted(self, url: str) -> bool:
        lower = url.lower()
        for p in self.patterns:
            if isinstance(p, re.Pattern):
                if p.search(lower):
                    return True
            else:
                if p in lower:
                    return True
        return False

    def filter(self, channels: list) -> list:
        return [ch for ch in channels if not self.is_blacklisted(ch.get('url', ''))]


_filter = None

def get_blacklist_filter():
    global _filter
    if _filter is None:
        _filter = BlacklistFilter()
    return _filter
