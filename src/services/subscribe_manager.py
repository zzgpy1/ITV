# src/services/subscribe_manager.py
"""订阅源管理"""

import re
from pathlib import Path
from typing import List, Dict, Optional

from src.core.config import get_config
from src.infrastructure.logger import get_logger

logger = get_logger(__name__)


class SubscribeManager:
    """订阅源管理器"""
    
    def __init__(self, subscribe_file: Optional[Path] = None):
        self.config = get_config()
        self.subscribe_file = subscribe_file or self.config.subscribe_file
        self._url_pattern = re.compile(r'(https?://[^\s]+)')
        self._kv_pattern = re.compile(r'(?P<key>\w+)=(?P<value>[^\s]+)')
    
    def parse(self) -> List[str]:
        """解析订阅文件，返回 URL 列表"""
        if not self.subscribe_file.exists():
            logger.debug(f"订阅文件不存在: {self.subscribe_file}")
            return []
        
        urls = []
        inside_whitelist = False
        
        with open(self.subscribe_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if line.startswith('[') and line.endswith(']'):
                    inside_whitelist = line.upper() == '[WHITELIST]'
                    continue
                
                match = self._url_pattern.search(line)
                if match:
                    urls.append(match.group(0))
        
        return urls
    
    def get_whitelist(self) -> List[str]:
        """获取白名单 URL"""
        if not self.subscribe_file.exists():
            return []
        
        urls = []
        inside_whitelist = False
        
        with open(self.subscribe_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if line.startswith('[') and line.endswith(']'):
                    inside_whitelist = line.upper() == '[WHITELIST]'
                    continue
                
                if inside_whitelist:
                    match = self._url_pattern.search(line)
                    if match:
                        urls.append(match.group(0))
        
        return urls


def get_subscribe_urls() -> List[str]:
    """获取所有订阅源 URL"""
    manager = SubscribeManager()
    return manager.parse()


def get_whitelist_urls() -> List[str]:
    """获取白名单 URL"""
    manager = SubscribeManager()
    return manager.get_whitelist()
