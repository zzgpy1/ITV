# src/generator.py
# 输出 M3U 和 TXT 文件模块，按 demo.txt 顺序输出，所有频道按分类归入对应 demo 分类

from pathlib import Path
from typing import List, Tuple, Dict
from collections import defaultdict
from src.config import OUTPUT_DIR, M3U_FILE, TXT_FILE
from src.logger import logger
import re


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
    urls = get_channel_urls(channel)
    return urls[0] if urls else ""


def _normalize_category(cat: str) -> str:
    """标准化分类名称：去除emoji、特殊符号、空格，转为小写"""
    # 去除emoji (简单做法：移除所有非ASCII字母数字和中文)
    # 保留中文、字母、数字，移除其他
    cat = re.sub(r'[^\w\u4e00-\u9fa5]', '', cat)
    return cat.lower()


def _generate_m3u(category_channels: Dict[str, List[dict]], 
                  demo_category_order: List[str],
                  demo_category_names: Dict[str, List[str]],
                  output_path: Path) -> None:
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for cat in demo_category_order:
            channels = category_channels.get(cat, [])
            if not channels:
                continue
            # 先按 demo 顺序输出该分类下在 demo 中指定的频道
            demo_names_in_cat = demo_category_names.get(cat, [])
            # 先输出 demo 中的频道
            for demo_name in demo_names_in_cat:
                # 查找频道
                for ch in channels:
                    if ch.get("name") == demo_name:
                        url = get_first_url(ch)
                        if url:
                            f.write(f'#EXTINF:-1 group-title="{cat}",{ch["name"]}\n{url}\n')
                        break
            # 再输出该分类下其他频道（不在 demo 中的）
            other_channels = [ch for ch in channels if ch.get("name") not in demo_names_in_cat]
            if other_channels:
                # 按名称排序
                other_channels.sort(key=lambda x: x.get("name", ""))
                for ch in other_channels:
                    url = get_first_url(ch)
                    if url:
                        f.write(f'#EXTINF:-1 group-title="{cat}",{ch["name"]}\n{url}\n')
        # 处理可能未归入任何 demo 分类的频道（如"其他"分类）
        # 我们已经在 category_channels 中包含了所有频道，但可能有些频道的分类未在 demo_category_order 中
        # 我们把它们放到最后，分类名保持原样
        extra_cats = [cat for cat in category_channels.keys() if cat not in demo_category_order]
        if extra_cats:
            f.write("\n# ===== 未在 demo 中定义的分类 =====\n")
            for cat in sorted(extra_cats):
                channels = category_channels[cat]
                for ch in sorted(channels, key=lambda x: x.get("name", "")):
                    url = get_first_url(ch)
                    if url:
                        f.write(f'#EXTINF:-1 group-title="{cat}",{ch["name"]}\n{url}\n')
    logger.info(f"✅ M3U 文件已生成: {output_path}")


def _generate_txt(category_channels: Dict[str, List[dict]],
                  demo_category_order: List[str],
                  demo_category_names: Dict[str, List[str]],
                  output_path: Path) -> None:
    with open(output_path, 'w', encoding='utf-8') as f:
        for cat in demo_category_order:
            channels = category_channels.get(cat, [])
            if not channels:
                continue
            f.write(f"{cat},#genre#\n")
            demo_names_in_cat = demo_category_names.get(cat, [])
            # 先输出 demo 中的频道
            for demo_name in demo_names_in_cat:
                for ch in channels:
                    if ch.get("name") == demo_name:
                        url = get_first_url(ch)
                        if url:
                            f.write(f'{ch["name"]},{url}\n')
                        break
            # 再输出其他
            other_channels = [ch for ch in channels if ch.get("name") not in demo_names_in_cat]
            if other_channels:
                other_channels.sort(key=lambda x: x.get("name", ""))
                for ch in other_channels:
                    url = get_first_url(ch)
                    if url:
                        f.write(f'{ch["name"]},{url}\n')
        # 未定义的分类
        extra_cats = [cat for cat in category_channels.keys() if cat not in demo_category_order]
        if extra_cats:
            f.write("\n# ===== 未在 demo 中定义的分类 =====\n")
            for cat in sorted(extra_cats):
                channels = category_channels[cat]
                f.write(f"{cat},#genre#\n")
                for ch in sorted(channels, key=lambda x: x.get("name", "")):
                    url = get_first_url(ch)
                    if url:
                        f.write(f'{ch["name"]},{url}\n')
    logger.info(f"✅ TXT 文件已生成: {output_path}")


def _generate_multi_m3u(category_channels: Dict[str, List[dict]],
                         demo_category_order: List[str],
                         demo_category_names: Dict[str, List[str]],
                         output_path: Path) -> None:
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for cat in demo_category_order:
            channels = category_channels.get(cat, [])
            if not channels:
                continue
            demo_names_in_cat = demo_category_names.get(cat, [])
            # 先输出 demo 中的
            for demo_name in demo_names_in_cat:
                for ch in channels:
                    if ch.get("name") == demo_name:
                        urls = get_channel_urls(ch)
                        valid_urls = [u for u in urls if u and u.startswith(('http://', 'https://'))]
                        if valid_urls:
                            multi_url = " # ".join(valid_urls)
                            f.write(f'#EXTINF:-1 group-title="{cat}",{ch["name"]}\n{multi_url}\n')
                        break
            # 其他
            other_channels = [ch for ch in channels if ch.get("name") not in demo_names_in_cat]
            if other_channels:
                other_channels.sort(key=lambda x: x.get("name", ""))
                for ch in other_channels:
                    urls = get_channel_urls(ch)
                    valid_urls = [u for u in urls if u and u.startswith(('http://', 'https://'))]
                    if valid_urls:
                        multi_url = " # ".join(valid_urls)
                        f.write(f'#EXTINF:-1 group-title="{cat}",{ch["name"]}\n{multi_url}\n')
        # 未定义分类
        extra_cats = [cat for cat in category_channels.keys() if cat not in demo_category_order]
        if extra_cats:
            f.write("\n# ===== 未在 demo 中定义的分类 =====\n")
            for cat in sorted(extra_cats):
                channels = category_channels[cat]
                for ch in sorted(channels, key=lambda x: x.get("name", "")):
                    urls = get_channel_urls(ch)
                    valid_urls = [u for u in urls if u and u.startswith(('http://', 'https://'))]
                    if valid_urls:
                        multi_url = " # ".join(valid_urls)
                        f.write(f'#EXTINF:-1 group-title="{cat}",{ch["name"]}\n{multi_url}\n')
    logger.info(f"✅ 多源 M3U 文件已生成: {output_path}")


def generate_outputs_from_demo(ordered_channels: List[dict], demo_order: List[Tuple[str, str]]) -> None:
    if not ordered_channels:
        logger.warning("无频道数据，跳过输出生成")
        return

    # 构建 demo 分类顺序和每个分类下的频道名集合
    demo_category_order = []
    demo_category_names = defaultdict(list)
    for cat, name in demo_order:
        clean_cat = cat.replace(",#genre#", "").strip()
        if clean_cat not in demo_category_order:
            demo_category_order.append(clean_cat)
        demo_category_names[clean_cat].append(name)

    # 构建频道名到分类的映射（用于判断是否在demo中）
    demo_name_to_category = {}
    for cat, name in demo_order:
        clean_cat = cat.replace(",#genre#", "").strip()
        demo_name_to_category[name] = clean_cat

    # 按分类分组所有频道
    category_channels = defaultdict(list)
    for ch in ordered_channels:
        name = ch.get("name", "")
        # 确定分类
        if name in demo_name_to_category:
            cat = demo_name_to_category[name]
        else:
            # 使用已有的 demo_category
            cat = ch.get("demo_category", "其他")
            # 尝试将 cat 映射到 demo 中的分类（标准化匹配）
            std_cat = _normalize_category(cat)
            matched_cat = None
            for dc in demo_category_order:
                if _normalize_category(dc) == std_cat:
                    matched_cat = dc
                    break
            if matched_cat:
                cat = matched_cat
            # 否则保留原分类，后续作为 extra 处理
        category_channels[cat].append(ch)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _generate_m3u(category_channels, demo_category_order, demo_category_names, OUTPUT_DIR / M3U_FILE)
    _generate_txt(category_channels, demo_category_order, demo_category_names, OUTPUT_DIR / TXT_FILE)
    _generate_multi_m3u(category_channels, demo_category_order, demo_category_names, OUTPUT_DIR / "tv_multi.m3u")
