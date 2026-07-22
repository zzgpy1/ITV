# src/subscribe_manager.py
import re
from pathlib import Path
from typing import List
from src.settings import settings
from src.logger import logger

class SubscribeManager:
    def __init__(self):
        self.subscribe_file = settings.subscribe_file

    def get_all_subscribe_urls(self) -> List[str]:
        if not self.subscribe_file.exists():
            return []
        urls = []
        with open(self.subscribe_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('['):
                    continue
                # 提取URL
                m = re.search(r'(https?://[^\s]+)', line)
                if m:
                    urls.append(m.group(1))
        return urls
