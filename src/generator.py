# src/generator.py
# 输出 M3U 和 TXT 文件模块，按 demo.txt 顺序输出，自动合并同分类频道

from pathlib import Path
from typing import List, Tuple, Dict
from collections import defaultdict, OrderedDict
from src.config import OUTPUT_DIR, M3U_FILE, TXT_FILE
from src.logger import logger


def get_channel_urls(channel: dict) -> List[str]:
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


def build_category_groups(
    ordered_channels: List[dict],
    demo_order: List[Tuple[str, str]]
) -> Dict[str, List[dict]]:
    """
    按分类聚合频道，保持 demo 顺序
    返回: {分类名: [频道对象列表]}
    """
    # 1. 解析 demo_order，构建分类顺序、每个分类下的demo频道名列表
    category_order = []
    category_demo_names = {}  # {分类名: [demo中的频道名列表]}
    demo_name_to_category = {}  # {频道名: 分类名}
    for cat, demo_name in demo_order:
        clean_cat = cat.replace(",#genre#", "").strip()
        if clean_cat not in category_order:
            category_order.append(clean_cat)
            category_demo_names[clean_cat] = []
        category_demo_names[clean_cat].append(demo_name)
        demo_name_to_category[demo_name] = clean_cat

    # 2. 构建频道名到频道对象的映射（只取第一个，因为合并后同名应唯一）
    channel_by_name = {}
    for ch in ordered_channels:
        name = ch.get("name")
        if name and name not in channel_by_name:
            channel_by_name[name] = ch
        # 如果有同名，可考虑覆盖或合并，但通常不会

    # 3. 按分类聚合
    groups = OrderedDict()
    # 先按 category_order 顺序处理
    for cat in category_order:
        # 该分类的频道列表
        cat_channels = []
        # 3a. 按 demo 顺序添加匹配的频道
        demo_names_in_cat = category_demo_names.get(cat, [])
        for demo_name in demo_names_in_cat:
            ch = channel_by_name.get(demo_name)
            if ch:
                # 确保分类标记
                ch_copy = ch.copy()
                ch_copy["demo_category"] = cat
                cat_channels.append(ch_copy)
        # 3b. 收集该分类下未匹配的频道（不在 demo_names 中）
        # 遍历 ordered_channels，找出属于该分类但不在 demo_names 中的频道
        unmatched = []
        for ch in ordered_channels:
            name = ch.get("name")
            if name not in demo_name_to_category:
                # 判断频道所属分类
                ch_cat = ch.get("demo_category", ch.get("group_title", "其他"))
                if ch_cat == cat:
                    unmatched.append(ch.copy())
        # 未匹配的按名称排序
        unmatched.sort(key=lambda x: x.get("name", ""))
        # 合并
        groups[cat] = cat_channels + unmatched

    # 4. 处理未在 category_order 中的分类（其他）
    # 收集所有已处理分类
    processed_cats = set(category_order)
    # 从 ordered_channels 中找出未处理分类的频道
    other_groups = defaultdict(list)
    for ch in ordered_channels:
        name = ch.get("name")
        if name in demo_name_to_category:
            continue  # 已处理
        cat = ch.get("demo_category", ch.get("group_title", "其他"))
        if cat not in processed_cats:
            other_groups[cat].append(ch.copy())

    # 其他分类按字母排序
    for cat in sorted(other_groups.keys()):
        other_groups[cat].sort(key=lambda x: x.get("name", ""))
        groups[cat] = other_groups[cat]

    return groups


def generate_m3u_from_groups(
    groups: Dict[str, List[dict]],
    output_path: Path
) -> None:
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for cat, channels in groups.items():
            if not channels:
                continue
            f.write(f'\n# ----- {cat} -----\n')
            for ch in channels:
                url = get_first_url(ch)
                if not url:
                    continue
                name = ch.get("name", "未知频道")
                f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n')
                f.write(f"{url}\n")
    logger.info(f"✅ M3U 文件已生成: {output_path}")


def generate_txt_from_groups(
    groups: Dict[str, List[dict]],
    output_path: Path
) -> None:
    with open(output_path, 'w', encoding='utf-8') as f:
        for cat, channels in groups.items():
            if not channels:
                continue
            f.write(f"{cat},#genre#\n")
            for ch in channels:
                url = get_first_url(ch)
                if not url:
                    continue
                name = ch.get("name", "未知频道")
                f.write(f"{name},{url}\n")
    logger.info(f"✅ TXT 文件已生成: {output_path}")


def generate_multi_m3u_from_groups(
    groups: Dict[str, List[dict]],
    output_path: Path
) -> None:
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for cat, channels in groups.items():
            if not channels:
                continue
            f.write(f'\n# ----- {cat} -----\n')
            for ch in channels:
                urls = get_channel_urls(ch)
                valid_urls = [u for u in urls if u and u.startswith(('http://', 'https://'))]
                if valid_urls:
                    multi_url = " # ".join(valid_urls)
                    name = ch.get("name", "未知频道")
                    f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n')
                    f.write(f"{multi_url}\n")
    logger.info(f"✅ 多源 M3U 文件已生成: {output_path}")


def generate_outputs_from_demo(
    ordered_channels: List[dict],
    demo_order: List[Tuple[str, str]]
) -> None:
    if not ordered_channels:
        logger.warning("无频道数据，跳过输出生成")
        return

    groups = build_category_groups(ordered_channels, demo_order)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    generate_m3u_from_groups(groups, OUTPUT_DIR / M3U_FILE)
    generate_txt_from_groups(groups, OUTPUT_DIR / TXT_FILE)
    generate_multi_m3u_from_groups(groups, OUTPUT_DIR / "tv_multi.m3u")
