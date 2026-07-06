# src/generator.py
# 输出 M3U 和 TXT 文件模块，严格按 ordered_channels 顺序输出

from pathlib import Path
from typing import List, Dict
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
    urls = get_channel_urls(channel)
    return urls[0] if urls else ""


def generate_m3u_from_ordered(ordered_channels: List[dict], output_path: Path) -> None:
    """直接按 ordered_channels 顺序生成 M3U 文件"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for ch in ordered_channels:
            cat = ch.get("demo_category", "其他")
            # 统一港澳台分类名称
            if cat == "🌊港澳台频道":
                cat = "🌊港·澳·台"
            url = get_first_url(ch)
            if not url:
                continue
            name = ch.get("name", "未知频道")
            f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n')
            f.write(f"{url}\n")
    logger.info(f"✅ M3U 文件已生成: {output_path}")


def generate_txt_from_ordered(ordered_channels: List[dict], output_path: Path) -> None:
    """直接按 ordered_channels 顺序生成 TXT 文件，动态插入分类标题"""
    with open(output_path, 'w', encoding='utf-8') as f:
        last_category = None
        for ch in ordered_channels:
            cat = ch.get("demo_category", "其他")
            if cat == "🌊港澳台频道":
                cat = "🌊港·澳·台"
            # 当分类变化时写入分类行
            if cat != last_category:
                last_category = cat
                f.write(f"{cat},#genre#\n")
            url = get_first_url(ch)
            if not url:
                continue
            name = ch.get("name", "未知频道")
            f.write(f"{name},{url}\n")
    logger.info(f"✅ TXT 文件已生成: {output_path}")


def generate_outputs_from_demo(ordered_channels: List[dict], demo_order: List[tuple]) -> None:
    """
    按照 ordered_channels 的顺序输出 M3U 和 TXT 文件
    demo_order 参数仅用于保持接口兼容，实际顺序由 ordered_channels 决定
    """
    if not ordered_channels:
        logger.warning("无频道数据，跳过输出生成")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    generate_m3u_from_ordered(ordered_channels, OUTPUT_DIR / M3U_FILE)
    generate_txt_from_ordered(ordered_channels, OUTPUT_DIR / TXT_FILE)
    # 不再生成 tv_multi.m3u
    logger.info("✅ 已生成标准 M3U 和 TXT 文件（tv_multi.m3u 已取消）")
