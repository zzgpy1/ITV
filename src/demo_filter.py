# src/demo_filter.py
# Demo 频道筛选与排序模块，并输出未匹配的频道到 shai.txt

from pathlib import Path
from typing import List, Tuple
from src.config import DEMO_FILE, OUTPUT_DIR
from src.alias_matcher import get_alias_matcher

try:
    from src.config import DEMO_MATCH_MODE
except ImportError:
    DEMO_MATCH_MODE = "contains"

def parse_demo_order_with_categories(demo_file: Path = DEMO_FILE) -> List[Tuple[str, str]]:
    """解析 demo.txt，返回 [(分类, 标准化频道名), ...]"""
    if not demo_file.exists():
        print(f"⚠️ Demo 文件不存在: {demo_file}")
        return []
    matcher = get_alias_matcher()
    order = []
    current_category = None
    with open(demo_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.endswith(",#genre#"):
                current_category = line[:-7]
                continue
            if line.startswith('#'):
                continue
            if current_category is not None:
                demo_name = line
                if matcher:
                    demo_name = matcher.normalize(demo_name)
                order.append((current_category, demo_name))
            else:
                order.append(("其他", line))
    print(f"📋 从 demo.txt 解析到 {len(order)} 个有序频道，共 {len(set(c for c,_ in order))} 个分类")
    return order

def match_channel_name(channel_name: str, demo_name: str) -> bool:
    if DEMO_MATCH_MODE == "exact":
        return channel_name == demo_name
    else:
        return demo_name in channel_name or channel_name in demo_name

def filter_and_order_by_demo(channels: list, alias_matcher=None) -> tuple:
    """
    根据 demo.txt 筛选并排序频道。
    返回 (ordered_channels, unmatched_channels)
    ordered_channels: 按 demo 顺序排列的频道列表（每个频道增加 'demo_category' 字段）
    unmatched_channels: 未匹配上的频道列表（用于输出到 shai.txt）
    """
    demo_order = parse_demo_order_with_categories()
    if not demo_order:
        print("⚠️ demo.txt 为空，跳过筛选")
        return channels, []

    name_to_channel = {ch["name"]: ch for ch in channels}
    matched = []
    matched_names = set()
    unmatched = []

    for category, demo_name in demo_order:
        # 精确匹配优先
        if demo_name in name_to_channel:
            ch = name_to_channel[demo_name].copy()
            ch["demo_category"] = category
            if ch["name"] not in matched_names:
                matched.append(ch)
                matched_names.add(ch["name"])
                continue
        # 模糊匹配
        found = False
        for ch in channels:
            if ch["name"] in matched_names:
                continue
            if match_channel_name(ch["name"], demo_name):
                ch_copy = ch.copy()
                ch_copy["demo_category"] = category
                matched.append(ch_copy)
                matched_names.add(ch["name"])
                found = True
                break
        if not found:
            print(f"⚠️ Demo 未匹配: {demo_name} (分类: {category})")

    # 收集未匹配的频道
    for ch in channels:
        if ch["name"] not in matched_names:
            unmatched.append(ch)

    print(f"🎯 Demo 筛选：原始 {len(channels)} 个频道 -> 匹配 {len(matched)} 个频道，未匹配 {len(unmatched)} 个")

    # 输出未匹配频道到 shai.txt
    if unmatched:
        shai_path = OUTPUT_DIR / "shai.txt"
        with open(shai_path, "w", encoding="utf-8") as f:
            f.write("# 未被 demo.txt 匹配的频道列表\n")
            f.write("# 格式：频道名,URL\n\n")
            for ch in unmatched:
                url = ch["urls"][0] if ch.get("urls") else ch["url"]
                f.write(f"{ch['name']},{url}\n")
        print(f"📄 未匹配频道已写入 {shai_path}")

    return matched, unmatched
