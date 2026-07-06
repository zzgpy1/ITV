# src/generator.py
# 输出 M3U 和 TXT 文件模块，按 demo.txt 顺序输出，并追加未匹配的港澳台日频道

from pathlib import Path
from typing import List, Tuple, Dict
from collections import defaultdict
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
    
    # 如果 urls 是字符串，直接转为列表
    if isinstance(urls, str):
        return [urls]
    
    # 如果 urls 是列表，展平嵌套列表
    if isinstance(urls, list):
        flat = []
        for item in urls:
            if isinstance(item, str):
                flat.append(item)
            elif isinstance(item, list):
                # 递归展平
                for sub in item:
                    if isinstance(sub, str):
                        flat.append(sub)
        return flat
    
    return []


def get_first_url(channel: dict) -> str:
    """获取第一个有效 URL"""
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
        
        # 2. 追加额外的频道（按分类分组）
        if extra_channels:
            f.write("\n# ===== 以下为自动追加的频道 =====\n")
            # 按分类分组
            grouped = defaultdict(list)
            for ch in extra_channels:
                cat = ch.get("demo_category", "其他")
                grouped[cat].append(ch)
            
            for cat, channels in grouped.items():
                f.write(f"\n# ----- {cat} -----\n")
                for ch in channels:
                    url = get_first_url(ch)
                    if not url:
                        continue
                    name = ch.get("name")
                    f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n')
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
        
        # 2. 追加额外的频道（按分类分组）
        if extra_channels:
            f.write("\n# ===== 以下为自动追加的频道 =====\n")
            grouped = defaultdict(list)
            for ch in extra_channels:
                cat = ch.get("demo_category", "其他")
                grouped[cat].append(ch)
            
            for cat, channels in grouped.items():
                f.write(f"\n{cat},#genre#\n")
                for ch in channels:
                    url = get_first_url(ch)
                    if not url:
                        continue
                    name = ch.get("name")
                    f.write(f"{name},{url}\n")
    
    logger.info(f"✅ TXT 文件已生成: {output_path}")


# 已废弃：不再生成 tv_multi.m3u
def generate_multi_m3u_by_demo_order(...):
    """已废弃，不再使用"""
    pass


def generate_outputs_from_demo(ordered_channels: List[dict], demo_order: List[Tuple[str, str]]) -> None:
    """
    按照 demo.txt 的顺序输出 M3U 和 TXT 文件，并自动追加未匹配的港澳台日频道
    不再生成 tv_multi.m3u
    """
    if not ordered_channels:
        logger.warning("无频道数据，跳过输出生成")
        return

    demo_categories = {cat for cat, _ in demo_order}
    channels_by_name = {}
    
    # 构建 channels_by_name
    for ch in ordered_channels:
        name = ch.get("name")
        if name:
            channels_by_name[name] = ch
        # 同时使用 demo_name 作为备用键
        if "demo_name" in ch:
            channels_by_name[ch["demo_name"]] = ch
    
    # 提取额外频道（分类不在 demo_order 中）
    extra_channels = [
        ch for ch in ordered_channels
        if ch.get("demo_category") and ch.get("demo_category") not in demo_categories
    ]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    generate_m3u_by_demo_order(channels_by_name, demo_order, extra_channels, OUTPUT_DIR / M3U_FILE)
    generate_txt_by_demo_order(channels_by_name, demo_order, extra_channels, OUTPUT_DIR / TXT_FILE)
    # 不再生成 tv_multi.m3u
    logger.info("✅ 输出文件生成完成（仅 tv.m3u 和 tv.txt）")
