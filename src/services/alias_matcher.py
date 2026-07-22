import re
from pathlib import Path
from typing import Dict, List, Optional, Pattern
from src.settings import settings

class AliasMatcher:
    def __init__(self, alias_file: Path = None):
        self.alias_file = alias_file or settings.alias_file
        self.exact_mappings: Dict[str, str] = {}
        self.regex_mappings: List[tuple] = []
        self._load()

    def _load(self):
        if not self.alias_file.exists():
            return
        with open(self.alias_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if ',' in line:
                    parts = [p.strip() for p in line.split(',')]
                else:
                    parts = [p.strip() for p in line.split(':', 1)] if ':' in line else []
                    if len(parts) < 2:
                        continue
                standard = parts[0]
                aliases = parts[1:]
                for alias in aliases:
                    alias = alias.strip()
                    if not alias:
                        continue
                    if alias.startswith('re:'):
                        pattern_str = alias[3:].strip()
                        try:
                            pattern = re.compile(pattern_str, re.IGNORECASE)
                            self.regex_mappings.append((pattern, standard))
                        except re.error:
                            pass
                    else:
                        self.exact_mappings[alias.lower()] = standard

    def match(self, channel_name: str) -> Optional[str]:
        if not channel_name:
            return None
        name_lower = channel_name.lower()
        if name_lower in self.exact_mappings:
            return self.exact_mappings[name_lower]
        for pattern, standard in self.regex_mappings:
            if pattern.search(channel_name):
                return standard
        return None

    def normalize(self, channel_name: str) -> str:
        mapped = self.match(channel_name)
        return mapped if mapped is not None else channel_name

_matcher = None

def get_alias_matcher() -> Optional[AliasMatcher]:
    global _matcher
    if _matcher is None and settings.enable_alias:
        _matcher = AliasMatcher()
    return _matcher
