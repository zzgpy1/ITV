# src/generator.py
# 输出 M3U 和 TXT 文件模块，按 demo.txt 顺序输出，并追加所有未匹配的频道

import re
from pathlib import Path
from typing import List, Tuple, Dict
from collections import defaultdict, OrderedDict
from src.config import OUTPUT_DIR, M3U_FILE, TXT_FILE
from src.logger import logger


def normalize_category_name(name: str) -> str:
    """标准化分类名，去除 emoji 和特殊符号，只保留中文字符和数字字母"""
    # 去除 emoji 和特殊符号
    cleaned = re.sub(r'[^\w\u4e00-\u9fa5]', '', name)
    return cleaned


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
    channels_by_name: Dict[str, dict],
    demo_order: List[Tuple[str, str]],
    extra_channels: List[dict],
    output_path: Path
) -> None:
    """生成 M3U 文件，先输出 demo 顺序，再追加 extra_channels"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        # 1. 输出 demo 中的频道
        for cat, demo_name in demo_order:
            channel = channels_by_name.get(demo_name)
            if channel:
                url = get_first_url(channel)
                if not url:
                    continue
                name = channel.get("name", demo_name)
                clean_cat = cat.replace(",#genre#", "").strip()
                f.write(f'#EXTINF:-1 group-title="{clean_cat}",{name}\n')
                f.write(f"{url}\n")
        
        # 2. 追加额外的频道
        if extra_channels:
            f.write("\n# ===== 以下为自动追加的频道 =====\n")
            
            # 构建 demo_order 中的分类标准化映射：标准化名 -> 原始显示名
            demo_category_map = {}
            for cat, _ in demo_order:
                clean_cat = cat.replace(",#genre#", "").strip()
                # 标准化后的名称作为键
                norm = normalize_category_name(clean_cat)
                demo_category_map[norm] = clean_cat
            
            # 按分类分组 extra_channels
            grouped = defaultdict(list)
            for ch in extra_channels:
                cat = ch.get("demo_category", "其他")
                grouped[cat].append(ch)
            
            # 对 extra_channels 的分类排序：尽量匹配 demo_order 顺序
            # 先构建 demo_order 中的分类列表（按出现顺序）
            demo_categories = []
            for cat, _ in demo_order:
                clean_cat = cat.replace(",#genre#", "").strip()
                if clean_cat not in demo_categories:
                    demo_categories.append(clean_cat)
            
            def cat_sort_key(cat):
                # 将分类 cat 标准化后与 demo_category_map 的键比较
                norm = normalize_category_name(cat)
                # 检查是否匹配某个 demo 分类
                matched_demo_cat = None
                for demo_norm, demo_orig in demo_category_map.items():
                    if norm == demo_norm or cat == demo_orig:
                        matched_demo_cat = demo_orig
                        break
                if matched_demo_cat:
                    # 如果匹配，则按其所在的 demo_order 索引排序
                    if matched_demo_cat in demo_categories:
                        return (0, demo_categories.index(matched_demo_cat))
                    else:
                        return (0, len(demo_categories))  # 理论上不会发生
                else:
                    # 不匹配的放在后面，按原分类名排序
                    return (1, cat)
            
            # 按排序后的分类输出
            for cat in sorted(grouped.keys(), key=cat_sort_key):
                channels = grouped[cat]
                # 确定显示用的分类名：优先使用 demo_order 中的原始名，否则用 cat
                norm = normalize_category_name(cat)
                display_cat = cat
                for demo_norm, demo_orig in demo_category_map.items():
                    if norm == demo_norm or cat == demo_orig:
                        display_cat = demo_orig
                        break
                f.write(f"\n# ----- {display_cat} -----\n")
                for ch in sorted(channels, key=lambda x: x.get("name", "")):
                    url = get_first_url(ch)
                    if not url:
                        continue
                    name = ch.get("name")
                    f.write(f'#EXTINF:-1 group-title="{display_cat}",{name}\n')
                    f.write(f"{url}\n")
    
    logger.info(f"✅ M3U 文件已生成: {output_path}")


def generate_txt_by_demo_order(
    channels_by_name: Dict[str, dict],
    demo_order: List[Tuple[str, str]],
    extra_channels: List[dict],
    output_path: Path
) -> None:
    """生成 TXT 文件，先输出 demo 顺序，再追加 extra_channels"""
    with open(output_path, 'w', encoding='utf-8') as f:
        current_cat = None
        # 1. 输出 demo 中的频道
        for cat, demo_name in demo_order:
            clean_cat = cat.replace(",#genre#", "").strip()
            if clean_cat != current_cat:
                current_cat = clean_cat
                f.write(f"{current_cat},#genre#\n")
            channel = channels_by_name.get(demo_name)
            if channel:
                url = get_first_url(channel)
                if not url:
                    continue
                name = channel.get("name", demo_name)
                f.write(f"{name},{url}\n")
        
        # 2. 追加额外的频道
        if extra_channels:
            f.write("\n# ===== 以下为自动追加的频道 =====\n")
            
            demo_category_map = {}
            for cat, _ in demo_order:
                clean_cat = cat.replace(",#genre#", "").strip()
                norm = normalize_category_name(clean_cat)
                demo_category_map[norm] = clean_cat
            
            grouped = defaultdict(list)
            for ch in extra_channels:
                cat = ch.get("demo_category", "其他")
                grouped[cat].append(ch)
            
            demo_categories = []
            for cat, _ in demo_order:
                clean_cat = cat.replace(",#genre#", "").strip()
                if clean_cat not in demo_categories:
                    demo_categories.append(clean_cat)
            
            def cat_sort_key(cat):
                norm = normalize_category_name(cat)
                for demo_norm, demo_orig in demo_category_map.items():
                    if norm == demo_norm or cat == demo_orig:
                        matched = demo_orig
                        if matched in demo_categories:
                            return (0, demo_categories.index(matched))
                        else:
                            return (0, len(demo_categories))
                return (1, cat)
            
            for cat in sorted(grouped.keys(), key=cat_sort_key):
                channels = grouped[cat]
                norm = normalize_category_name(cat)
                display_cat = cat
                for demo_norm, demo_orig in demo_category_map.items():
                    if norm == demo_norm or cat == demo_orig:
                        display_cat = demo_orig
                        break
                f.write(f"\n{display_cat},#genre#\n")
                for ch in sorted(channels, key=lambda x: x.get("name", "")):
                    url = get_first_url(ch)
                    if not url:
                        continue
                    name = ch.get("name")
                    f.write(f"{name},{url}\n")
    
    logger.info(f"✅ TXT 文件已生成: {output_path}")


def generate_multi_m3u_by_demo_order(
    channels_by_name: Dict[str, dict],
    demo_order: List[Tuple[str, str]],
    extra_channels: List[dict],
    output_path: Path
) -> None:
    """生成多源 M3U 文件"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        # 1. demo 频道
        for cat, demo_name in demo_order:
            channel = channels_by_name.get(demo_name)
            if channel:
                urls = get_channel_urls(channel)
                valid_urls = [u for u in urls if u and u.startswith(('http://', 'https://'))]
                if valid_urls:
                    multi_url = " # ".join(valid_urls)
                    name = channel.get("name", demo_name)
                    clean_cat = cat.replace(",#genre#", "").strip()
                    f.write(f'#EXTINF:-1 group-title="{clean_cat}",{name}\n')
                    f.write(f"{multi_url}\n")
        
        # 2. 额外频道
        if extra_channels:
            f.write("\n# ===== 以下为自动追加的频道 =====\n")
            
            demo_category_map = {}
            for cat, _ in demo_order:
                clean_cat = cat.replace(",#genre#", "").strip()
                norm = normalize_category_name(clean_cat)
                demo_category_map[norm] = clean_cat
            
            grouped = defaultdict(list)
            for ch in extra_channels:
                cat = ch.get("demo_category", "其他")
                grouped[cat].append(ch)
            
            demo_categories = []
            for cat, _ in demo_order:
                clean_cat = cat.replace(",#genre#", "").strip()
                if clean_cat not in demo_categories:
                    demo_categories.append(clean_cat)
            
            def cat_sort_key(cat):
                norm = normalize_category_name(cat)
                for demo_norm, demo_orig in demo_category_map.items():
                    if norm == demo_norm or cat == demo_orig:
                        matched = demo_orig
                        if matched in demo_categories:
                            return (0, demo_categories.index(matched))
                        else:
                            return (0, len(demo_categories))
                return (1, cat)
            
            for cat in sorted(grouped.keys(), key=cat_sort_key):
                channels = grouped[cat]
                norm = normalize_category_name(cat)
                display_cat = cat
                for demo_norm, demo_orig in demo_category_map.items():
                    if norm == demo_norm or cat == demo_orig:
                        display_cat = demo_orig
                        break
                f.write(f"\n# ----- {display_cat} -----\n")
                for ch in sorted(channels, key=lambda x: x.get("name", "")):
                    urls = get_channel_urls(ch)
                    valid_urls = [u for u in urls if u and u.startswith(('http://', 'https://'))]
                    if valid_urls:
                        multi_url = " # ".join(valid_urls)
                        name = ch.get("name")
                        f.write(f'#EXTINF:-1 group-title="{display_cat}",{name}\n')
                        f.write(f"{multi_url}\n")
    
    logger.info(f"✅ 多源 M3U 文件已生成: {output_path}")


def generate_outputs_from_demo(ordered_channels: List[dict], demo_order: List[Tuple[str, str]]) -> None:
    if not ordered_channels:
        logger.warning("无频道数据，跳过输出生成")
        return

    demo_names = {demo_name for _, demo_name in demo_order}
    channels_by_name = {}
    extra_channels = []

    for ch in ordered_channels:
        name = ch.get("name")
        if name and name in demo_names:
            channels_by_name[name] = ch
        else:
            extra_channels.append(ch)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    generate_m3u_by_demo_order(channels_by_name, demo_order, extra_channels, OUTPUT_DIR / M3U_FILE)
    generate_txt_by_demo_order(channels_by_name, demo_order, extra_channels, OUTPUT_DIR / TXT_FILE)
    generate_multi_m3u_by_demo_order(channels_by_name, demo_order, extra_channels, OUTPUT_DIR / "tv_multi.m3u")
