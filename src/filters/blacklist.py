# src/filters/blacklist.py
"""黑名单过滤器"""

import re
from pathlib import Path
from typing import List, Union, Optional

from src.core.config import get_config
from src.infrastructure.logger import get_logger

logger = get_logger(__name__)


class BlacklistFilter:
    """黑名单过滤器"""
    
    def __init__(self, blacklist_file: Optional[Path] = None):
        config = get_config()
        self.blacklist_file = blacklist_file or config.blacklist_file
        self.patterns: List[Union[str, re.Pattern]] = []
        self._load()
    
    def _load(self):
        if not self.blacklist_file.exists():
            logger.warning(f"⚠️ 黑名单文件不存在: {self.blacklist_file}")
            return
        
        with open(self.blacklist_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if re.search(r'[\.\*\?\+\[\]\(\)\{\}\\]', line):
                    try:
                        self.patterns.append(re.compile(line, re.IGNORECASE))
                    except re.error as e:
                        logger.warning(f"⚠️ 正则错误: {line} -> {e}")
                else:
                    self.patterns.append(line.lower())
        
        logger.info(f"✅ 加载黑名单: {len(self.patterns)} 条规则")
    
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
    
    def filter_channels(self, channels: List[Dict]) -> List[Dict]:
        original = len(channels)
        filtered = []
        
        for ch in channels:
            url = ch.get("url")
            if isinstance(url, list):
                url = url[0] if url else None
            
            if url and isinstance(url, str) and not self.is_blacklisted(url):
                filtered.append(ch)
            elif not url:
                filtered.append(ch)
        
        logger.info(f"🛡️ 黑名单过滤: {original} -> {len(filtered)} 个频道")
        return filtered
