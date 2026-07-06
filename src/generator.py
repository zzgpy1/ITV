# src/generator.py

from pathlib import Path
from typing import List, Tuple, Dict
from collections import defaultdict, OrderedDict
from src.config import OUTPUT_DIR, M3U_FILE, TXT_FILE
from src.logger import logger


def get_channel_urls(channel: dict) -> List[str]:
    # 同前，不变
    ...

def get_first_url(channel: dict) -> str:
    # 同前，不变
    ...

def generate_m3u_by_demo_order(
    ordered_channels: List[dict],
    demo_order: List[Tuple[str, str]],
    output_path: Path
) -> None:
    """
    生成 M3U 文件：
    1. 按 demo 顺序输出 demo 中列出的频道（如果存在）
    2. 对于 demo 分类中存在但未在 demo 中列出条目的频道，追加在该分类末尾
    3. 对于 demo 中不存在的分类，追加到末尾
    """
    # 构建 demo 分类集合
    demo_categories = {cat for cat, _ in demo_order}
    # 构建 demo 顺序映射：分类 -> 频道名列表（保持顺序）
    demo_map = OrderedDict()
    for cat, name in demo_order:
        if cat not in demo_map:
            demo_map[cat] = []
        demo_map[cat].append(name)

    # 将 ordered_channels 按 demo_category 分组
    channels_by_cat = defaultdict(list)
    for ch in ordered_channels:
        cat = ch.get("demo_category", "其他")
        channels_by_cat[cat].append(ch)

    # 准备输出
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        # 用于记录已经输出过的分类
        outputed_cats = set()

        # 1. 先按 demo 顺序输出
        for cat, demo_names in demo_map.items():
            # 先输出该分类下 demo 中列出的频道（按 demo 顺序）
            # 但我们无法确保每个 demo_name 都对应一个频道，所以遍历 demo_names
            # 并查找 channels_by_cat[cat] 中是否有 demo_name 匹配的频道
            # 为了保持顺序，我们遍历 demo_names，在 channels_by_cat[cat] 中查找
            # 如果找到则输出，并从列表中移除，避免重复
            cat_channels = channels_by_cat.get(cat, [])
            # 为了查找方便，构建 name->channel 映射
            name_to_ch = {ch.get("demo_name", ch["name"]): ch for ch in cat_channels}
            # 输出 demo 中的频道
            for demo_name in demo_names:
                ch = name_to_ch.get(demo_name)
                if ch:
                    url = get_first_url(ch)
                    if url:
                        clean_cat = cat.replace(",#genre#", "").strip()
                        f.write(f'#EXTINF:-1 group-title="{clean_cat}",{demo_name}\n{url}\n')
                        # 从 cat_channels 中移除已输出的，避免重复
                        # 由于我们使用 name_to_ch，我们可以标记已输出
            # 输出该分类下未在 demo 中列出的其余频道
            # 遍历 cat_channels，如果其 demo_name 不在 demo_names 中，则输出
            for ch in cat_channels:
                demo_name = ch.get("demo_name", ch["name"])
                if demo_name not in demo_names:
                    url = get_first_url(ch)
                    if url:
                        clean_cat = cat.replace(",#genre#", "").strip()
                        f.write(f'#EXTINF:-1 group-title="{clean_cat}",{ch["name"]}\n{url}\n')
            outputed_cats.add(cat)

        # 2. 输出 demo 中不存在的分类
        # 获取所有分类，按字母顺序输出（或保持原顺序）
        remaining_cats = set(channels_by_cat.keys()) - demo_categories
        for cat in sorted(remaining_cats):
            for ch in channels_by_cat.get(cat, []):
                url = get_first_url(ch)
                if url:
                    clean_cat = cat.replace(",#genre#", "").strip()
                    f.write(f'#EXTINF:-1 group-title="{clean_cat}",{ch["name"]}\n{url}\n')
            outputed_cats.add(cat)

    logger.info(f"✅ M3U 文件已生成: {output_path}")


def generate_txt_by_demo_order(
    ordered_channels: List[dict],
    demo_order: List[Tuple[str, str]],
    output_path: Path
) -> None:
    """类似逻辑生成 TXT 文件"""
    demo_categories = {cat for cat, _ in demo_order}
    demo_map = OrderedDict()
    for cat, name in demo_order:
        if cat not in demo_map:
            demo_map[cat] = []
        demo_map[cat].append(name)

    channels_by_cat = defaultdict(list)
    for ch in ordered_channels:
        cat = ch.get("demo_category", "其他")
        channels_by_cat[cat].append(ch)

    with open(output_path, 'w', encoding='utf-8') as f:
        outputed_cats = set()

        # 按 demo 顺序输出
        for cat, demo_names in demo_map.items():
            name_to_ch = {ch.get("demo_name", ch["name"]): ch for ch in channels_by_cat.get(cat, [])}
            clean_cat = cat.replace(",#genre#", "").strip()
            f.write(f"{clean_cat},#genre#\n")
            # 输出 demo 中的频道
            for demo_name in demo_names:
                ch = name_to_ch.get(demo_name)
                if ch:
                    url = get_first_url(ch)
                    if url:
                        f.write(f"{demo_name},{url}\n")
            # 输出未列出的频道
            for ch in channels_by_cat.get(cat, []):
                demo_name = ch.get("demo_name", ch["name"])
                if demo_name not in demo_names:
                    url = get_first_url(ch)
                    if url:
                        f.write(f'{ch["name"]},{url}\n')
            outputed_cats.add(cat)

        # 输出剩余分类
        remaining_cats = set(channels_by_cat.keys()) - demo_categories
        for cat in sorted(remaining_cats):
            clean_cat = cat.replace(",#genre#", "").strip()
            f.write(f"\n{clean_cat},#genre#\n")
            for ch in channels_by_cat.get(cat, []):
                url = get_first_url(ch)
                if url:
                    f.write(f'{ch["name"]},{url}\n')

    logger.info(f"✅ TXT 文件已生成: {output_path}")


def generate_multi_m3u_by_demo_order(
    ordered_channels: List[dict],
    demo_order: List[Tuple[str, str]],
    output_path: Path
) -> None:
    """多源 M3U 类似逻辑"""
    # 类似上述逻辑，但使用 urls 列表多源输出
    # 为简洁，此处略，可仿照上面实现


def generate_outputs_from_demo(ordered_channels: List[dict], demo_order: List[Tuple[str, str]]) -> None:
    if not ordered_channels:
        logger.warning("无频道数据，跳过输出生成")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generate_m3u_by_demo_order(ordered_channels, demo_order, OUTPUT_DIR / M3U_FILE)
    generate_txt_by_demo_order(ordered_channels, demo_order, OUTPUT_DIR / TXT_FILE)
    # generate_multi_m3u_by_demo_order 类似，暂略
