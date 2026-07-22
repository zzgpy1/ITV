from pathlib import Path
from typing import List, Dict
from src.settings import settings
from src.logger import logger

def generate_m3u(category_channels: Dict[str, List[dict]], category_order: List[str], path: Path):
    with open(path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for cat in category_order:
            channels = category_channels.get(cat, [])
            for ch in channels:
                url = ch.get('url', '')
                if url:
                    name = ch.get('demo_name', ch.get('name', ''))
                    f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n{url}\n')
    logger.info(f"M3U generated: {path}")

def generate_txt(category_channels, category_order, path):
    with open(path, 'w', encoding='utf-8') as f:
        for cat in category_order:
            channels = category_channels.get(cat, [])
            if channels:
                f.write(f"{cat},#genre#\n")
                for ch in channels:
                    url = ch.get('url', '')
                    if url:
                        name = ch.get('demo_name', ch.get('name', ''))
                        f.write(f"{name},{url}\n")
    logger.info(f"TXT generated: {path}")

def generate_json(channels: list, path: Path):
    import json, datetime
    data = {
        "version": "2.0",
        "total": len(channels),
        "generated": datetime.datetime.now().isoformat(),
        "channels": [{"name": c['name'], "url": c.get('url', ''), "latency": c.get('latency'), "codec": c.get('video_codec', '')} for c in channels]
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f"JSON generated: {path}")

async def generate_outputs(ordered_channels: list, demo_order: List[tuple]):
    if not ordered_channels:
        return
    # 分类
    category_order = []
    seen = set()
    for cat, _ in demo_order:
        if cat not in seen:
            seen.add(cat)
            category_order.append(cat)
    category_channels = {}
    for ch in ordered_channels:
        cat = ch.get('demo_category', '其他')
        category_channels.setdefault(cat, []).append(ch)
    # 确保所有分类都在order中
    for cat in category_channels:
        if cat not in category_order:
            category_order.append(cat)
    output_dir = settings.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    generate_m3u(category_channels, category_order, output_dir / "tv.m3u")
    generate_txt(category_channels, category_order, output_dir / "tv.txt")
    # 生成多源
    with open(output_dir / "tv_multi.m3u", 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for cat in category_order:
            for ch in category_channels.get(cat, []):
                urls = ch.get('urls', [ch.get('url')])
                valid = [u for u in urls if u]
                if valid:
                    name = ch.get('demo_name', ch.get('name', ''))
                    f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n{" # ".join(valid)}\n')
    # JSON
    generate_json(ordered_channels, output_dir / "channels.json")
    logger.info("所有输出生成完成")
