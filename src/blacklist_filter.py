# src/blacklist_filter.py
# URL 黑名单过滤器

import re
from pathlib import Path
from typing import List, Union
from src.config import BLACKLIST_FILE

class BlacklistFilter:
    def __init__(self, blacklist_file: Path = BLACKLIST_FILE):
        self.patterns: List[Union[str, re.Pattern]] = []
        self._load(blacklist_file)
    
    def _load(self, filepath):
        if not filepath.exists():
            print(f"⚠️ 黑名单文件不存在: {filepath}")
            return
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if re.search(r'[\.\*\?\+\[\]\(\)\{\}\\]', line):
                    try:
                        self.patterns.append(re.compile(line, re.IGNORECASE))
                    except re.error as e:
                        print(f"⚠️ 正则错误: {line} -> {e}")
                else:
                    self.patterns.append(line.lower())
        print(f"✅ 已加载 {len(self.patterns)} 条黑名单规则")
    
    def is_blacklisted(self, url) -> bool:
        # 防御性检查：如果 url 是列表，取其第一个有效项
        if isinstance(url, list):
            url = url[0] if url else ""
        if not isinstance(url, str):
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
        # 过滤时确保每个频道对象有 'url' 键，且为字符串或列表
        filtered = []
        for ch in channels:
            # 如果 ch 不是字典，跳过
            if not isinstance(ch, dict):
                continue
            url = ch.get("url")
            if isinstance(url, list):
                # 如果是列表，取第一个
                url = url[0] if url else None
            if url and isinstance(url, str) and not self.is_blacklisted(url):
                filtered.append(ch)
            elif not url:
                # 如果没有 url，也保留（但通常不会有）
                filtered.append(ch)
        print(f"🛡️ 黑名单过滤：{original} -> {len(filtered)} 个频道")
        return filtered

_filter = None

def get_blacklist_filter():
    global _filter
    if _filter is None:
        _filter = BlacklistFilter()
    return _filter
