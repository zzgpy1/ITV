from pathlib import Path
from typing import List, Tuple, Dict
from collections import defaultdict
from src.settings import settings
from src.logger import logger

def get_channel_urls(channel: dict) -> List[str]:
    url = channel.get("url")
    if url:
        return [url] if isinstance(url, str) else url
    urls = channel.get("urls")
    if urls:
        return urls if isinstance(urls, list) else [urls]
    return []

def generate_m3u(category_channels: Dict[str, List[dict]], category_order: List[str], output_path: Path):
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for cat in category_order:
            for ch in category_channels.get(cat, []):
                url = get_channel_urls(ch)[0] if get_channel_urls(ch) else None
                if url:
                    name = ch.get("demo_name") or ch.get("name", "未知")
                    f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n{url}\n')

def generate_txt(category_channels: Dict[str, List[dict]], category_order: List[str], output_path: Path):
    with open(output_path, 'w', encoding='utf-8') as f:
        for cat in category_order:
            channels = category_channels.get(cat, [])
            if not channels:
                continue
            f.write(f"{cat},#genre#\n")
            for ch in channels:
                url = get_channel_urls(ch)[0] if get_channel_urls(ch) else None
                if url:
                    name = ch.get("demo_name") or ch.get("name", "未知")
                    f.write(f"{name},{url}\n")

def generate_multi_m3u(category_channels: Dict[str, List[dict]], category_order: List[str], output_path: Path):
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for cat in category_order:
            for ch in category_channels.get(cat, []):
                urls = get_channel_urls(ch)
                valid = [u for u in urls if u and u.startswith(('http://', 'https://'))]
                if valid:
                    name = ch.get("demo_name") or ch.get("name", "未知")
                    f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n{" # ".join(valid)}\n')

def generate_outputs_from_demo(ordered_channels: List[dict], demo_order: List[Tuple[str, str]]):
    if not ordered_channels:
        logger.warning("无频道数据，跳过输出")
        return
    # 获取分类顺序
    seen = set()
    category_order = []
    for cat, _ in demo_order:
        if cat not in seen:
            seen.add(cat)
            category_order.append(cat)
    # 分组
    category_channels = defaultdict(list)
    for ch in ordered_channels:
        cat = ch.get("demo_category", "其他")
        if cat in seen:
            category_channels[cat].append(ch)
    # 确保所有分类都在 order 中
    final_order = [cat for cat in category_order if cat in category_channels]
    # 输出
    output_dir = settings.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    generate_m3u(category_channels, final_order, output_dir / "tv.m3u")
    generate_txt(category_channels, final_order, output_dir / "tv.txt")
    generate_multi_m3u(category_channels, final_order, output_dir / "tv_multi.m3u")
    logger.info("✅ 输出文件生成完成")
