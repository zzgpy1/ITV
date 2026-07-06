# src/generator.py
from pathlib import Path
from typing import List, Tuple, Dict
from collections import defaultdict
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


def generate_m3u_by_demo_order(
    channels_by_name: Dict[str, dict],
    demo_order: List[Tuple[str, str]],
    extra_channels: List[dict],
    output_path: Path
) -> None:
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for cat, demo_name in demo_order:
            channel = channels_by_name.get(demo_name)
            if channel:
                url = get_first_url(channel)
                if url:
                    clean_cat = cat.replace(",#genre#", "").strip()
                    f.write(f'#EXTINF:-1 group-title="{clean_cat}",{demo_name}\n{url}\n')
        if extra_channels:
            f.write("\n# ===== 以下为自动追加的频道 =====\n")
            grouped = defaultdict(list)
            for ch in extra_channels:
                grouped[ch.get("demo_category", "其他")].append(ch)
            for cat, chs in grouped.items():
                f.write(f"\n# ----- {cat} -----\n")
                for ch in chs:
                    url = get_first_url(ch)
                    if url:
                        f.write(f'#EXTINF:-1 group-title="{cat}",{ch["name"]}\n{url}\n')
    logger.info(f"✅ M3U 文件已生成: {output_path}")


def generate_txt_by_demo_order(
    channels_by_name: Dict[str, dict],
    demo_order: List[Tuple[str, str]],
    extra_channels: List[dict],
    output_path: Path
) -> None:
    with open(output_path, 'w', encoding='utf-8') as f:
        current_cat = None
        for cat, demo_name in demo_order:
            clean_cat = cat.replace(",#genre#", "").strip()
            if clean_cat != current_cat:
                current_cat = clean_cat
                f.write(f"{current_cat},#genre#\n")
            channel = channels_by_name.get(demo_name)
            if channel:
                url = get_first_url(channel)
                if url:
                    f.write(f"{demo_name},{url}\n")
        if extra_channels:
            f.write("\n# ===== 以下为自动追加的频道 =====\n")
            grouped = defaultdict(list)
            for ch in extra_channels:
                grouped[ch.get("demo_category", "其他")].append(ch)
            for cat, chs in grouped.items():
                f.write(f"\n{cat},#genre#\n")
                for ch in chs:
                    url = get_first_url(ch)
                    if url:
                        f.write(f"{ch['name']},{url}\n")
    logger.info(f"✅ TXT 文件已生成: {output_path}")


def generate_multi_m3u_by_demo_order(
    channels_by_name: Dict[str, dict],
    demo_order: List[Tuple[str, str]],
    extra_channels: List[dict],
    output_path: Path
) -> None:
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for cat, demo_name in demo_order:
            channel = channels_by_name.get(demo_name)
            if channel:
                urls = get_channel_urls(channel)
                valid = [u for u in urls if u and u.startswith(('http://', 'https://'))]
                if valid:
                    clean_cat = cat.replace(",#genre#", "").strip()
                    f.write(f'#EXTINF:-1 group-title="{clean_cat}",{demo_name}\n{" # ".join(valid)}\n')
        if extra_channels:
            f.write("\n# ===== 以下为自动追加的频道 =====\n")
            grouped = defaultdict(list)
            for ch in extra_channels:
                grouped[ch.get("demo_category", "其他")].append(ch)
            for cat, chs in grouped.items():
                f.write(f"\n# ----- {cat} -----\n")
                for ch in chs:
                    urls = get_channel_urls(ch)
                    valid = [u for u in urls if u and u.startswith(('http://', 'https://'))]
                    if valid:
                        f.write(f'#EXTINF:-1 group-title="{cat}",{ch["name"]}\n{" # ".join(valid)}\n')
    logger.info(f"✅ 多源 M3U 文件已生成: {output_path}")


def generate_outputs_from_demo(ordered_channels: List[dict], demo_order: List[Tuple[str, str]]) -> None:
    if not ordered_channels:
        logger.warning("无频道数据，跳过输出生成")
        return

    demo_categories = {cat for cat, _ in demo_order}
    channels_by_name = {}
    for ch in ordered_channels:
        if ch.get("name"):
            channels_by_name[ch["name"]] = ch
        if ch.get("demo_name"):
            channels_by_name[ch["demo_name"]] = ch

    extra_channels = [
        ch for ch in ordered_channels
        if ch.get("demo_category") and ch.get("demo_category") not in demo_categories
    ]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generate_m3u_by_demo_order(channels_by_name, demo_order, extra_channels, OUTPUT_DIR / M3U_FILE)
    generate_txt_by_demo_order(channels_by_name, demo_order, extra_channels, OUTPUT_DIR / TXT_FILE)
    generate_multi_m3u_by_demo_order(channels_by_name, demo_order, extra_channels, OUTPUT_DIR / "tv_multi.m3u")
