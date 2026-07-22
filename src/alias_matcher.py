# src/alias_matcher.py
import re
from pathlib import Path
from typing import Dict, List, Pattern, Optional
from src.settings import settings
from src.logger import logger

class AliasMatcher:
    def __init__(self, alias_file: Path = None):
        self.alias_file = alias_file or settings.alias_file
        self.exact: Dict[str, str] = {}
        self.regex: List[tuple] = []  # (Pattern, standard)
        self._load()

    def _load(self):
        if not self.alias_file.exists():
            logger.warning(f"别名文件不存在: {self.alias_file}")
            return
        with open(self.alias_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if ',' not in line:
                    continue
                parts = [p.strip() for p in line.split(',')]
                standard = parts[0]
                for alias in parts[1:]:
                    if not alias:
                        continue
                    if alias.startswith('re:'):
                        try:
                            self.regex.append((re.compile(alias[3:], re.IGNORECASE), standard))
                        except Exception:
                            pass
                    else:
                        self.exact[alias.lower()] = standard
        logger.info(f"别名加载: 精确 {len(self.exact)}, 正则 {len(self.regex)}")

    def match(self, name: str) -> Optional[str]:
        if not name:
            return None
        lower = name.lower()
        if lower in self.exact:
            return self.exact[lower]
        for pattern, std in self.regex:
            if pattern.search(name):
                return std
        return None

    def normalize(self, name: str) -> str:
        matched = self.match(name)
        return matched if matched else name

_matcher = None

def get_alias_matcher():
    global _matcher
    if _matcher is None and settings.enable_alias:
        _matcher = AliasMatcher()
    return _matcher
