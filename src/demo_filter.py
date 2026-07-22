# src/demo_filter.py
import re
from pathlib import Path
from typing import List, Tuple
from src.settings import settings
from src.classifier import classify_channel, PROVINCES
from src.logger import logger

def parse_demo_order(demo_file: Path = None) -> List[Tuple[str, str]]:
    demo_file = demo_file or settings.demo_file
    if not demo_file.exists():
        logger.warning(f"Demo文件不存在: {demo_file}")
        return []
    order = []
    cat = None
    with open(demo_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.endswith(",#genre#") or line.endswith(", #genre#"):
                cat = line.replace(",#genre#", "").replace(", #genre#", "").strip()
                continue
            if line.startswith('#'):
                continue
            if cat:
                order.append((cat, line))
    logger.info(f"加载 {len(order)} 个 demo 条目")
    return order

def match_channel_name(ch_name: str, demo_name: str) -> bool:
    if settings.demo_match_mode == "exact":
        return ch_name == demo_name
    # 包含匹配
    cn_lower = ch_name.lower()
    dn_lower = demo_name.lower()
    if dn_lower in cn_lower or cn_lower in dn_lower:
        return True
    # 去掉特殊字符
    def clean(s):
        return re.sub(r'[^a-zA-Z\u4e00-\u9fa5]', '', s).lower()
    if clean(demo_name) in clean(ch_name) or clean(ch_name) in clean(demo_name):
        return True
    return False

def filter_and_order_by_demo(channels: list) -> tuple:
    demo_order = parse_demo_order()
    if not demo_order:
        return channels, []
    name_to_ch = {ch["name"]: ch for ch in channels}
    matched = []
    unmatched = list(channels)
    matched_names = set()
    for cat, demo_name in demo_order:
        if demo_name in name_to_ch:
            ch = name_to_ch[demo_name].copy()
            ch["demo_category"] = cat
            ch["demo_name"] = demo_name
            matched.append(ch)
            matched_names.add(ch["name"])
            unmatched = [c for c in unmatched if c["name"] != ch["name"]]
            continue
        for i, ch in enumerate(unmatched[:]):
            if ch["name"] in matched_names:
                continue
            if match_channel_name(ch["name"], demo_name):
                ch_copy = ch.copy()
                ch_copy["demo_category"] = cat
                ch_copy["demo_name"] = demo_name
                matched.append(ch_copy)
                matched_names.add(ch["name"])
                unmatched.pop(i)
                break
    # 未匹配的按省份归类
    for ch in unmatched:
        if ch["name"] in matched_names:
            continue
        # 简单分类
        cat = classify_channel(ch)
        ch["demo_category"] = cat
        ch["demo_name"] = ch["name"]
        matched.append(ch)
    logger.info(f"Demo筛选: {len(channels)} -> {len(matched)}")
    return matched, []
