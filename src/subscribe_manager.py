# src/subscribe_manager.py
import re
from pathlib import Path
from typing import List, Optional

from src.config_loader import config
from src.logger import logger


class SubscribeManager:
    """
    订阅源管理器：
    - 优先读取 config/subscribe.txt
    - 若 subscribe.txt 不存在或为空，回退到 config.yaml 的 source_groups（enabled=true）
    """

    def __init__(self, subscribe_file: Optional[Path] = None):
        self.config = config
        self.subscribe_file = subscribe_file or self.config.subscribe_file
        self._url_pattern = re.compile(r'(https?://[^\s]+)')

    def _parse_subscribe_file(self) -> List[str]:
        if not self.subscribe_file.exists():
            return []
        urls = []
        with open(self.subscribe_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.startswith('[') and line.endswith(']'):
                    continue
                match = self._url_pattern.search(line)
                if match:
                    urls.append(match.group(0))
        return urls

    def parse(self) -> List[str]:
        """返回所有订阅源 URL（含白名单）"""
        urls = self._parse_subscribe_file()
        if urls:
            logger.info(f"📋 subscribe.txt 提供 {len(urls)} 个源")
            return urls
        # 回退到 source_groups
        group_urls = self.config.get_enabled_group_sources()
        if group_urls:
            logger.info(f"📋 source_groups 提供 {len(group_urls)} 个启用源")
        return group_urls

    def get_all_subscribe_urls(self) -> List[str]:
        return self.parse()

    def get_whitelist(self) -> List[str]:
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
    return SubscribeManager().parse()


def get_whitelist_urls() -> List[str]:
    return SubscribeManager().get_whitelist()
