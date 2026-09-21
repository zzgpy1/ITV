# src/alias_matcher.py
import re
from pathlib import Path
from typing import Dict, Optional, List
from src.config_loader import config


class AliasMatcher:
    def __init__(self, alias_file: Path = None):
        self.alias_file = alias_file or config.alias_file
        self.exact_mappings: Dict[str, str] = {}
        self.regex_mappings: List[tuple] = []
        self._load()

    def _load(self):
        if not self.alias_file.exists():
            print(f"⚠️ 别名文件不存在: {self.alias_file}")
            return
        with open(self.alias_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = [p.strip() for p in line.split(',')] if ',' in line else line.split(':', 1)
                if len(parts) < 2:
                    print(f"⚠️ 别名文件第 {line_num} 行格式错误，跳过: {line}")
                    continue
                standard = parts[0]
                for alias in parts[1:]:
                    alias = alias.strip()
                    if not alias:
                        continue
                    if alias.startswith('re:'):
                        try:
                            pattern = re.compile(alias[3:].strip(), re.IGNORECASE)
                            self.regex_mappings.append((pattern, standard))
                        except re.error as e:
                            print(f"⚠️ 别名文件第 {line_num} 行正则错误: {e}")
                    else:
                        self.exact_mappings[alias.lower()] = standard
        print(f"✅ 已加载别名规则：精确 {len(self.exact_mappings)}，正则 {len(self.regex_mappings)}")

    def _is_special_suffix_mismatch(self, channel_name: str, standard: str) -> bool:
        """
        检测特殊后缀不匹配，防止误匹配：
        - CCTV-5 不应匹配含 + 的名称（CCTV-5+ 单独处理）
        - CCTV-4 不应匹配含 K、美洲、欧洲 的名称
        - CCTV-8 不应匹配含 K 的名称
        - CCTV-1/2/3/6/7 不应匹配含 K 的名称（如 CCTV-1K 不存在但防御）
        - 通用：CCTV-N 不应匹配 CCTV-NN（已由 \b 保护）
        """
        name_lower = channel_name.lower()
        std_upper = standard.upper()

        # CCTV-5 vs CCTV-5+
        if standard == "CCTV-5":
            if '+' in channel_name or '＋' in channel_name or '5plus' in name_lower:
                return True

        # CCTV-4 vs CCTV-4K / CCTV-4美洲 / CCTV-4欧洲
        if standard == "CCTV-4":
            if re.search(r'[KkＫ]', channel_name):
                return True
            if any(kw in channel_name for kw in ('美洲', '欧洲', 'America', 'Europe', '亞洲', '亚洲')):
                return True

        # CCTV-8 vs CCTV-8K
        if standard == "CCTV-8":
            if re.search(r'[KkＫ]', channel_name):
                return True

        # 其他数字频道 vs K 后缀（防未来扩展）
        if re.match(r'^CCTV-\d+$', std_upper):
            if re.search(r'[KkＫ]', channel_name) and '4K' not in std_upper and '8K' not in std_upper:
                # 只拦截通道号频道被 K 后缀误匹配
                if not any(k in name_lower for k in ('cctv4k', 'cctv8k')):
                    return True

        return False

    def match(self, channel_name: str) -> Optional[str]:
        if not channel_name:
            return None
        name_lower = channel_name.lower()

        # 1. 精确匹配优先
        if name_lower in self.exact_mappings:
            return self.exact_mappings[name_lower]

        # 2. 正则匹配（带后缀防误匹配）
        for pattern, standard in self.regex_mappings:
            if pattern.search(channel_name):
                if self._is_special_suffix_mismatch(channel_name, standard):
                    continue
                return standard
        return None

    def normalize(self, channel_name: str) -> str:
        mapped = self.match(channel_name)
        return mapped if mapped is not None else channel_name


_matcher = None


def get_alias_matcher() -> AliasMatcher:
    global _matcher
    if _matcher is None and config.enable_alias:
        _matcher = AliasMatcher()
    return _matcher
