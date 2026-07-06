# src/generator.py
# 输出 M3U 和 TXT 文件模块，按 demo.txt 顺序输出，自动合并同分类频道

from pathlib import Path
from typing import List, Tuple, Dict
from collections import defaultdict, OrderedDict
from src.config import OUTPUT_DIR, M3U_FILE, TXT_FILE
from src.logger import logger


def get_channel_urls(channel: dict) -> List[str]:
    """
    从频道字典中安全提取 URL 列表，确保是字符串列表
    """
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
    """获取第一个有效 URL"""
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
    # 提取 demo 中的分类顺序（去重）和每个分类下的频道名列表
    category_order = []
    category_demo_names = {}  # {分类名: [demo中的频道名列表]}
    for cat, demo_name in demo_order:
        clean_cat = cat.replace(",#genre#", "").strip()
        if clean_cat not in category_order:
            category_order.append(clean_cat)
            category_demo_names[clean_cat] = []
        category_demo_names[clean_cat].append(demo_name)

    # 构建 demo 名称集合（用于判断是否匹配）
    demo_names = {demo_name for _, demo_name in demo_order}

    # 按分类分组
    groups = defaultdict(list)
    for ch in ordered_channels:
        name = ch.get("name")
        cat = ch.get("demo_category", ch.get("group_title", "其他"))
        if name in demo_names:
            # 找到对应的 demo 分类
            for d_cat, d_name in demo_order:
                if d_name == name:
                    clean_cat = d_cat.replace(",#genre#", "").strip()
                    ch["demo_category"] = clean_cat
                    groups[clean_cat].append(ch)
                    break
        else:
            # 未匹配的频道，保留原分类
            groups[cat].append(ch)

    # 对每个分类内的频道排序
    result = OrderedDict()

    # 先按 category_order 顺序输出分类
    for cat in category_order:
        if cat in groups:
            # 获取该分类在 demo 中的频道名列表（按顺序）
            demo_names_in_cat = category_demo_names.get(cat, [])
            # 分离匹配和未匹配
            matched = []
            unmatched = []
            for ch in groups[cat]:
                if ch.get("name") in demo_names:
                    matched.append(ch)
                else:
                    unmatched.append(ch)

            # 匹配的按 demo 顺序排序
            # 创建一个排序映射
            demo_order_map = {name: idx for idx, name in enumerate(demo_names_in_cat)}
            matched.sort(key=lambda x: demo_order_map.get(x.get("name", ""), 9999))

            # 未匹配的按名称排序（自然排序）
            unmatched.sort(key=lambda x: x.get("name", ""))

            groups[cat] = matched + unmatched
            result[cat] = groups[cat]

    # 处理其他未在 category_order 中的分类（按字母排序）
    other_cats = sorted([cat for cat in groups.keys() if cat not in category_order])
    for cat in other_cats:
        groups[cat].sort(key=lambda x: x.get("name", ""))
        result[cat] = groups[cat]

    return result


def generate_m3u_from_groups(
    groups: Dict[str, List[dict]],
    output_path: Path
) -> None:
    """根据分类组生成 M3U 文件"""
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
    """根据分类组生成 TXT 文件"""
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
    """生成多源 M3U 文件"""
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
    """
    按照 demo.txt 的顺序输出 M3U 和 TXT 文件，自动合并同分类频道
    """
    if not ordered_channels:
        logger.warning("无频道数据，跳过输出生成")
        return

    groups = build_category_groups(ordered_channels, demo_order)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    generate_m3u_from_groups(groups, OUTPUT_DIR / M3U_FILE)
    generate_txt_from_groups(groups, OUTPUT_DIR / TXT_FILE)
    generate_multi_m3u_from_groups(groups, OUTPUT_DIR / "tv_multi.m3u")
