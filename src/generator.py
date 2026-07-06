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


def generate_m3u(
    category_channels: Dict[str, List[dict]],
    category_order: List[str],
    output_path: Path
) -> None:
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for cat in category_order:
            channels = category_channels.get(cat, [])
            if not channels:
                continue
            # 每个分类只输出一次，所有频道都在这里
            for ch in channels:
                url = get_first_url(ch)
                if url:
                    name = ch.get("demo_name") or ch.get("name", "未知频道")
                    f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n{url}\n')
    logger.info(f"✅ M3U 文件已生成: {output_path}")


def generate_txt(
    category_channels: Dict[str, List[dict]],
    category_order: List[str],
    output_path: Path
) -> None:
    with open(output_path, 'w', encoding='utf-8') as f:
        for cat in category_order:
            channels = category_channels.get(cat, [])
            if not channels:
                continue
            f.write(f"{cat},#genre#\n")
            for ch in channels:
                url = get_first_url(ch)
                if url:
                    name = ch.get("demo_name") or ch.get("name", "未知频道")
                    f.write(f"{name},{url}\n")
    logger.info(f"✅ TXT 文件已生成: {output_path}")


def generate_multi_m3u(
    category_channels: Dict[str, List[dict]],
    category_order: List[str],
    output_path: Path
) -> None:
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for cat in category_order:
            channels = category_channels.get(cat, [])
            if not channels:
                continue
            for ch in channels:
                urls = get_channel_urls(ch)
                valid = [u for u in urls if u and u.startswith(('http://', 'https://'))]
                if valid:
                    name = ch.get("demo_name") or ch.get("name", "未知频道")
                    f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n{" # ".join(valid)}\n')
    logger.info(f"✅ 多源 M3U 文件已生成: {output_path}")


def generate_outputs_from_demo(ordered_channels: List[dict], demo_order: List[Tuple[str, str]]) -> None:
    if not ordered_channels:
        logger.warning("无频道数据，跳过输出生成")
        return

    # 1. 提取 demo 中分类的顺序（去重保留顺序）
    demo_category_order = []
    seen = set()
    for cat, _ in demo_order:
        if cat not in seen:
            seen.add(cat)
            demo_category_order.append(cat)

    # 2. 按 demo_category 分组所有频道
    category_channels = defaultdict(list)
    for ch in ordered_channels:
        cat = ch.get("demo_category", "其他")
        category_channels[cat].append(ch)

    # 3. 构建最终分类顺序：先 demo 中的分类，再追加其他未在 demo 中出现的分类（排序）
    final_order = list(demo_category_order)
    extra_cats = [cat for cat in category_channels.keys() if cat not in seen]
    final_order.extend(sorted(extra_cats))

    # 4. 生成文件
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generate_m3u(category_channels, final_order, OUTPUT_DIR / M3U_FILE)
    generate_txt(category_channels, final_order, OUTPUT_DIR / TXT_FILE)
    generate_multi_m3u(category_channels, final_order, OUTPUT_DIR / "tv_multi.m3u")
