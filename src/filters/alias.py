# src/filters/alias.py
"""别名匹配器"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Pattern

from src.core.config import get_config
from src.infrastructure.logger import get_logger

logger = get_logger(__name__)


class AliasMatcher:
    """别名匹配器"""
    
    def __init__(self, alias_file: Optional[Path] = None):
        config = get_config()
        self.alias_file = alias_file or config.alias_file
        self.exact_mappings: Dict[str, str] = {}
        self.regex_mappings: List[tuple] = []
        self._load()
    
    def _load(self):
        if not self.alias_file.exists():
            logger.warning(f"⚠️ 别名文件不存在: {self.alias_file}")
            return
        
        with open(self.alias_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if ',' in line:
                    parts = [p.strip() for p in line.split(',')]
                elif ':' in line:
                    parts = [p.strip() for p in line.split(':', 1)]
                else:
                    continue
                
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
                        except re.error as e:
                            logger.warning(f"⚠️ 别名文件第 {line_num} 行正则错误: {e}")
                    else:
                        self.exact_mappings[alias.lower()] = standard
        
        logger.info(f"✅ 加载别名规则：精确 {len(self.exact_mappings)}，正则 {len(self.regex_mappings)}")
    
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
