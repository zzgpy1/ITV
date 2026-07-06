# src/generator.py
# 输出 M3U 和 TXT 文件模块，按 demo.txt 顺序输出，并确保所有频道按分类顺序输出

from pathlib import Path
from typing import List, Tuple, Dict
from collections import defaultdict
from src.config import OUTPUT_DIR, M3U_FILE, TXT_FILE
from src.logger import logger


def get_channel_urls(channel: dict) -> List[str]:
    """从频道字典中安全提取 URL 列表"""
    urls = channel.get("urls")
    if urls is None:
        url = channel.get("url")
        if url and isinstance(url, str):
            return [url]
        return []
    if isinstance(urls, str):
        return [urls]
    if isinstance(urls, list):
        flat = []
        for item in urls:
            if isinstance(item, str):
                flat.append(item)
            elif isinstance(item, list):
                for sub in item:
                    if isinstance(sub, str):
                        flat.append(sub)
        return flat
    return []


def get_first_url(channel: dict) -> str:
    urls = get_channel_urls(channel)
    return urls[0] if urls else ""


def generate_m3u_by_demo_order(
    channels: List[dict],
    demo_order: List[Tuple[str, str]],
    output_path: Path
) -> None:
    """生成 M3U 文件：按 demo_order 分类顺序输出所有频道"""
    # 构建分类到频道的映射（使用 demo_category）
    cat_to_channels = defaultdict(list)
    for ch in channels:
        cat = ch.get("demo_category", "其他")
        cat_to_channels[cat].append(ch)
    
    # 构建 demo_name 到频道的映射（用于快速查找）
    demo_name_to_ch = {}
    for ch in channels:
        name = ch.get("name")
        if name:
            demo_name_to_ch[name] = ch
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        # 遍历 demo_order 中的每个分类
        for cat, demo_name in demo_order:
            clean_cat = cat.replace(",#genre#", "").strip()
            f.write(f'\n# ----- {clean_cat} -----\n')
            # 先输出该分类下匹配 demo_name 的频道（按 demo_order 顺序）
            # 但 demo_order 中每个分类可能有多个频道，但 demo_name 是单个频道名，所以这里每个分类只对应一个 demo 条目
            # 但实际 demo_order 中每个分类下可能有多行，所以我们需要遍历当前分类下的所有 demo 条目
            # 由于 demo_order 是扁平的（每个条目是 (category, name)），我们不能按分类分组，只能按顺序输出。
            # 因此，重新设计：遍历 demo_order，对于每个条目，如果该频道存在，则输出；否则，该频道可能未匹配，但我们可以将其归类到该分类并稍后输出。
            # 但更好的方式是：我们先收集 demo_order 中所有的 (category, name) 对，对于匹配的频道，我们直接按此顺序输出。
            # 对于未匹配的频道，我们按分类追加到对应分类的尾部。
        
        # 由于上述设计复杂，简单方案：先按 demo_order 顺序输出匹配的频道，然后对于未匹配的频道，按分类追加到对应分类的尾部。
        # 但这样会导致分类重复。为了统一，我们决定将所有频道按分类分组，然后按 demo_order 中首次出现的分类顺序输出分类。
        # 获取 demo_order 中的分类顺序（去重）
        category_order = []
        for cat, _ in demo_order:
            clean_cat = cat.replace(",#genre#", "").strip()
            if clean_cat not in category_order:
                category_order.append(clean_cat)
        
        # 对于未在 category_order 中的分类，追加到末尾（按字母顺序）
        other_cats = sorted([cat for cat in cat_to_channels.keys() if cat not in category_order])
        all_cats = category_order + other_cats
        
        # 对于每个分类，输出该分类下的所有频道
        for cat in all_cats:
            if cat not in cat_to_channels:
                continue
            f.write(f'\n# ----- {cat} -----\n')
            # 对于该分类下的频道，优先输出在 demo_order 中出现的（按 demo_order 顺序），其余按名称排序
            # 构建 demo_order 中该分类下所有频道名的列表（按出现顺序）
            demo_names_in_cat = []
            for c, n in demo_order:
                if c.replace(",#genre#", "").strip() == cat:
                    demo_names_in_cat.append(n)
            # 将频道分为两组：在 demo_names_in_cat 中的和不在的
            matched = []
            unmatched = []
            for ch in cat_to_channels[cat]:
                name = ch.get("name")
                if name in demo_names_in_cat:
                    matched.append(ch)
                else:
                    unmatched.append(ch)
            # 对 matched 按 demo_order 顺序排序
            matched.sort(key=lambda ch: demo_names_in_cat.index(ch["name"]) if ch["name"] in demo_names_in_cat else 999)
            # 对 unmatched 按名称排序
            unmatched.sort(key=lambda ch: ch.get("name", ""))
            # 输出
            for ch in matched + unmatched:
                url = get_first_url(ch)
                if not url:
                    continue
                name = ch.get("name")
                f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n')
                f.write(f"{url}\n")
    
    logger.info(f"✅ M3U 文件已生成: {output_path}")


def generate_txt_by_demo_order(
    channels: List[dict],
    demo_order: List[Tuple[str, str]],
    output_path: Path
) -> None:
    """生成 TXT 文件：按 demo_order 分类顺序输出所有频道"""
    cat_to_channels = defaultdict(list)
    for ch in channels:
        cat = ch.get("demo_category", "其他")
        cat_to_channels[cat].append(ch)
    
    category_order = []
    for cat, _ in demo_order:
        clean_cat = cat.replace(",#genre#", "").strip()
        if clean_cat not in category_order:
            category_order.append(clean_cat)
    other_cats = sorted([cat for cat in cat_to_channels.keys() if cat not in category_order])
    all_cats = category_order + other_cats
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for cat in all_cats:
            if cat not in cat_to_channels:
                continue
            f.write(f"{cat},#genre#\n")
            # 同样按 demo 顺序优先
            demo_names_in_cat = []
            for c, n in demo_order:
                if c.replace(",#genre#", "").strip() == cat:
                    demo_names_in_cat.append(n)
            matched = []
            unmatched = []
            for ch in cat_to_channels[cat]:
                name = ch.get("name")
                if name in demo_names_in_cat:
                    matched.append(ch)
                else:
                    unmatched.append(ch)
            matched.sort(key=lambda ch: demo_names_in_cat.index(ch["name"]) if ch["name"] in demo_names_in_cat else 999)
            unmatched.sort(key=lambda ch: ch.get("name", ""))
            for ch in matched + unmatched:
                url = get_first_url(ch)
                if not url:
                    continue
                name = ch.get("name")
                f.write(f"{name},{url}\n")
    
    logger.info(f"✅ TXT 文件已生成: {output_path}")


def generate_multi_m3u_by_demo_order(
    channels: List[dict],
    demo_order: List[Tuple[str, str]],
    output_path: Path
) -> None:
    """生成多源 M3U 文件"""
    cat_to_channels = defaultdict(list)
    for ch in channels:
        cat = ch.get("demo_category", "其他")
        cat_to_channels[cat].append(ch)
    
    category_order = []
    for cat, _ in demo_order:
        clean_cat = cat.replace(",#genre#", "").strip()
        if clean_cat not in category_order:
            category_order.append(clean_cat)
    other_cats = sorted([cat for cat in cat_to_channels.keys() if cat not in category_order])
    all_cats = category_order + other_cats
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for cat in all_cats:
            if cat not in cat_to_channels:
                continue
            f.write(f'\n# ----- {cat} -----\n')
            demo_names_in_cat = []
            for c, n in demo_order:
                if c.replace(",#genre#", "").strip() == cat:
                    demo_names_in_cat.append(n)
            matched = []
            unmatched = []
            for ch in cat_to_channels[cat]:
                name = ch.get("name")
                if name in demo_names_in_cat:
                    matched.append(ch)
                else:
                    unmatched.append(ch)
            matched.sort(key=lambda ch: demo_names_in_cat.index(ch["name"]) if ch["name"] in demo_names_in_cat else 999)
            unmatched.sort(key=lambda ch: ch.get("name", ""))
            for ch in matched + unmatched:
                urls = get_channel_urls(ch)
                valid_urls = [u for u in urls if u and u.startswith(('http://', 'https://'))]
                if valid_urls:
                    multi_url = " # ".join(valid_urls)
                    name = ch.get("name")
                    f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n')
                    f.write(f"{multi_url}\n")
    
    logger.info(f"✅ 多源 M3U 文件已生成: {output_path}")


def generate_outputs_from_demo(ordered_channels: List[dict], demo_order: List[Tuple[str, str]]) -> None:
    """按照 demo.txt 的顺序输出 M3U 和 TXT 文件"""
    if not ordered_channels:
        logger.warning("无频道数据，跳过输出生成")
        return
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    generate_m3u_by_demo_order(ordered_channels, demo_order, OUTPUT_DIR / M3U_FILE)
    generate_txt_by_demo_order(ordered_channels, demo_order, OUTPUT_DIR / TXT_FILE)
    generate_multi_m3u_by_demo_order(ordered_channels, demo_order, OUTPUT_DIR / "tv_multi.m3u")
