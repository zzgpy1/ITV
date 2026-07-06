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
    category_channels: Dict[str, List[dict]],   # 分类 -> 频道列表
    extra_channels: List[dict],
    output_path: Path
) -> None:
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        # 记录每个分类下已输出的频道名（用于后续补漏）
        outputed_names = set()

        # 1. 按 demo 顺序输出已匹配的频道
        for cat, demo_name in demo_order:
            channel = channels_by_name.get(demo_name)
            if channel:
                url = get_first_url(channel)
                if url:
                    clean_cat = cat.replace(",#genre#", "").strip()
                    f.write(f'#EXTINF:-1 group-title="{clean_cat}",{demo_name}\n{url}\n')
                    outputed_names.add(demo_name)

        # 2. 对于每个分类，输出该分类下尚未输出的其他频道（按频道名排序）
        for cat, channels in category_channels.items():
            if not channels:
                continue
            clean_cat = cat.replace(",#genre#", "").strip()
            # 找出该分类下未被输出的频道
            remaining = [ch for ch in channels if ch.get("demo_name") not in outputed_names]
            if remaining:
                f.write(f"\n# ----- {clean_cat} 补充频道 -----\n")
                for ch in remaining:
                    url = get_first_url(ch)
                    if url:
                        f.write(f'#EXTINF:-1 group-title="{clean_cat}",{ch["name"]}\n{url}\n')

        # 3. 追加无法归类的频道（demo_category 不在 demo_order 中）
        if extra_channels:
            f.write("\n# ===== 以下为自动追加的频道（无法归类） =====\n")
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
    category_channels: Dict[str, List[dict]],
    extra_channels: List[dict],
    output_path: Path
) -> None:
    with open(output_path, 'w', encoding='utf-8') as f:
        current_cat = None
        outputed_names = set()

        # 1. 按 demo 顺序输出
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
                    outputed_names.add(demo_name)

        # 2. 每个分类补充未输出的频道
        for cat, channels in category_channels.items():
            if not channels:
                continue
            clean_cat = cat.replace(",#genre#", "").strip()
            remaining = [ch for ch in channels if ch.get("demo_name") not in outputed_names]
            if remaining:
                f.write(f"\n{clean_cat} 补充,#genre#\n")
                for ch in remaining:
                    url = get_first_url(ch)
                    if url:
                        f.write(f"{ch['name']},{url}\n")

        # 3. 额外频道
        if extra_channels:
            f.write("\n# ===== 以下为自动追加的频道（无法归类） =====\n")
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
    category_channels: Dict[str, List[dict]],
    extra_channels: List[dict],
    output_path: Path
) -> None:
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        outputed_names = set()

        for cat, demo_name in demo_order:
            channel = channels_by_name.get(demo_name)
            if channel:
                urls = get_channel_urls(channel)
                valid = [u for u in urls if u and u.startswith(('http://', 'https://'))]
                if valid:
                    clean_cat = cat.replace(",#genre#", "").strip()
                    f.write(f'#EXTINF:-1 group-title="{clean_cat}",{demo_name}\n{" # ".join(valid)}\n')
                    outputed_names.add(demo_name)

        for cat, channels in category_channels.items():
            if not channels:
                continue
            clean_cat = cat.replace(",#genre#", "").strip()
            remaining = [ch for ch in channels if ch.get("demo_name") not in outputed_names]
            if remaining:
                f.write(f"\n# ----- {clean_cat} 补充频道 -----\n")
                for ch in remaining:
                    urls = get_channel_urls(ch)
                    valid = [u for u in urls if u and u.startswith(('http://', 'https://'))]
                    if valid:
                        f.write(f'#EXTINF:-1 group-title="{clean_cat}",{ch["name"]}\n{" # ".join(valid)}\n')

        if extra_channels:
            f.write("\n# ===== 以下为自动追加的频道（无法归类） =====\n")
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

    # 构建 demo 分类集合
    demo_categories = {cat for cat, _ in demo_order}

    # 构建 channels_by_name（用于快速查找）
    channels_by_name = {}
    # 构建分类->频道列表映射
    category_channels = defaultdict(list)

    for ch in ordered_channels:
        name = ch.get("name")
        demo_name = ch.get("demo_name")
        if name:
            channels_by_name[name] = ch
        if demo_name:
            channels_by_name[demo_name] = ch
        cat = ch.get("demo_category", "其他")
        category_channels[cat].append(ch)

    # 分离 extra_channels（分类不在 demo_order 中）
    extra_channels = []
    for cat, chs in list(category_channels.items()):
        if cat not in demo_categories:
            extra_channels.extend(chs)
            del category_channels[cat]  # 移除，避免重复处理

    # 现在 category_channels 只包含 demo 中存在的分类
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generate_m3u_by_demo_order(channels_by_name, demo_order, category_channels, extra_channels, OUTPUT_DIR / M3U_FILE)
    generate_txt_by_demo_order(channels_by_name, demo_order, category_channels, extra_channels, OUTPUT_DIR / TXT_FILE)
    generate_multi_m3u_by_demo_order(channels_by_name, demo_order, category_channels, extra_channels, OUTPUT_DIR / "tv_multi.m3u")
