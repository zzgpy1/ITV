#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
别名匹配模块（整词边界匹配 + 最长匹配优先）
"""

import re
import os
from typing import List, Tuple, Optional

class AliasMatcher:
    def __init__(self, alias_file: str = "alias.txt"):
        self.alias_file = alias_file
        self.patterns: List[Tuple[re.Pattern, str]] = []

    def _load(self):
        if not os.path.exists(self.alias_file):
            print(f"⚠️ 别名文件不存在: {self.alias_file}")
            return

        with open(self.alias_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split(',')
                if len(parts) < 2:
                    print(f"⚠️ 别名文件第 {line_num} 行格式错误，跳过")
                    continue
                standard = parts[0].strip()
                aliases = parts[1:]
                for alias in aliases:
                    alias = alias.strip()
                    if not alias:
                        continue
                    if alias.startswith('re:'):
                        pattern_str = alias[3:].strip()
                        try:
                            pattern = re.compile(pattern_str, re.IGNORECASE)
                            self.patterns.append((pattern, standard))
                        except re.error as e:
                            print(f"⚠️ 别名文件第 {line_num} 行正则错误: {e}")
                    else:
                        escaped = re.escape(alias)
                        pattern_str = rf'(?<![a-zA-Z0-9\u4e00-\u9fa5]){escaped}(?![a-zA-Z0-9\u4e00-\u9fa5])'
                        try:
                            pattern = re.compile(pattern_str, re.IGNORECASE)
                            self.patterns.append((pattern, standard))
                        except re.error as e:
                            print(f"⚠️ 别名文件第 {line_num} 行转换正则错误: {e}")

        print(f"✅ 已加载 {len(self.patterns)} 条别名规则（整词匹配）")

    def match(self, channel_name: str) -> Optional[str]:
        if not channel_name:
            return None
        for pattern, standard in self.patterns:
            if pattern.search(channel_name):
                return standard
        return None

    def normalize(self, channel_name: str) -> str:
        """如果匹配到别名则返回标准名，否则返回原名称"""
        result = self.match(channel_name)
        return result if result is not None else channel_name

    def get_all_standard_names(self) -> set:
        return {std for _, std in self.patterns}


_matcher = None

def get_alias_matcher() -> AliasMatcher:
    global _matcher
    if _matcher is None:
        _matcher = AliasMatcher()
    return _matcher
