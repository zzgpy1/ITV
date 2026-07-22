import re
from pathlib import Path
from typing import List, Tuple
from src.settings import settings
from src.services.classifier import classify_and_filter
from src.logger import logger

try:
    from pypinyin import lazy_pinyin
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False
    logger.warning("⚠️ pypinyin 未安装，拼音匹配不可用")

def parse_demo_order_with_categories(demo_file: Path = None) -> List[Tuple[str, str]]:
    demo_file = demo_file or settings.demo_file
    if not demo_file.exists():
        return []
    order = []
    current_category = None
    with open(demo_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.endswith(",#genre#") or line.endswith(", #genre#"):
                current_category = line.replace(",#genre#", "").replace(", #genre#", "").strip()
                continue
            if line.startswith('#'):
                continue
            if current_category is not None:
                order.append((current_category, line))
            else:
                order.append(("其他", line))
    return order

def match_channel_name(channel_name: str, demo_name: str) -> bool:
    cn_lower = channel_name.lower()
    dn_lower = demo_name.lower()
    if dn_lower in cn_lower or cn_lower in dn_lower:
        return True
    if HAS_PYPINYIN:
        pinyin_ch = ''.join(lazy_pinyin(channel_name)).lower()
        pinyin_demo = ''.join(lazy_pinyin(demo_name)).lower()
        if pinyin_demo in pinyin_ch or pinyin_ch in pinyin_demo:
            return True
    # 去除特殊字符
    clean = lambda s: re.sub(r'[^a-zA-Z\u4e00-\u9fa5]', '', s).lower()
    if clean(demo_name) in clean(channel_name) or clean(channel_name) in clean(demo_name):
        return True
    return False

def filter_and_order_by_demo(channels: list) -> tuple:
    demo_order = parse_demo_order_with_categories()
    if not demo_order:
        classified = classify_and_filter(channels)
        matched = []
        for cat in ["央视", "卫视", "地方", "港澳台"]:
            for ch in classified.get(cat, []):
                ch["demo_category"] = cat
                ch["demo_name"] = ch["name"]
                matched.append(ch)
        return matched, []

    name_to_channel = {ch["name"]: ch for ch in channels}
    matched = []
    unmatched = list(channels)
    matched_names = set()

    for category, demo_name in demo_order:
        if demo_name in name_to_channel:
            ch = name_to_channel[demo_name].copy()
            ch["demo_category"] = category
            ch["demo_name"] = demo_name
            if ch["name"] not in matched_names:
                matched.append(ch)
                matched_names.add(ch["name"])
                unmatched = [c for c in unmatched if c["name"] != ch["name"]]
                continue

        for i, ch in enumerate(unmatched[:]):
            if ch["name"] in matched_names:
                continue
            if match_channel_name(ch["name"], demo_name):
                ch_copy = ch.copy()
                ch_copy["demo_category"] = category
                ch_copy["demo_name"] = demo_name
                matched.append(ch_copy)
                matched_names.add(ch["name"])
                unmatched.pop(i)
                break

    # 未匹配的放入"其他"
    for ch in unmatched:
        if ch["name"] not in matched_names:
            ch_copy = ch.copy()
            ch_copy["demo_category"] = "其他"
            ch_copy["demo_name"] = ch["name"]
            matched.append(ch_copy)
            matched_names.add(ch["name"])

    return matched, []
