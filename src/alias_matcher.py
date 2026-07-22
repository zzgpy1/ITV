import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from src.settings import settings


class AliasMatcher:
    def __init__(self):
        self.exact: Dict[str, str] = {}
        self.regex: List[Tuple[re.Pattern, str]] = []
        self._load()

    def _load(self):
        if not settings.alias_file.exists():
            return
        with open(settings.alias_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = [p.strip() for p in line.split(',')]
                if len(parts) < 2:
                    continue
                standard = parts[0]
                for alias in parts[1:]:
                    if not alias:
                        continue
                    if alias.startswith('re:'):
                        try:
                            self.regex.append((re.compile(alias[3:], re.I), standard))
                        except:
                            pass
                    else:
                        self.exact[alias.lower()] = standard

    def match(self, name: str) -> Optional[str]:
        lower = name.lower()
        if lower in self.exact:
            return self.exact[lower]
        for pat, std in self.regex:
            if pat.search(name):
                return std
        return None

    def normalize(self, name: str) -> str:
        mapped = self.match(name)
        return mapped if mapped else name


_matcher = None

def get_alias_matcher():
    global _matcher
    if _matcher is None:
        _matcher = AliasMatcher()
    return _matcher
