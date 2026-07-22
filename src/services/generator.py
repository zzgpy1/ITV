# src/services/generator.py
from pathlib import Path
from typing import List, Dict, Tuple
from src.settings import settings
from src.logger import logger
from src.demo_filter import parse_demo_order_with_categories
from src.classifier import classify_and_filter

async def generate_outputs(channels: List[Dict]):
    """生成所有输出文件"""
    output_dir = settings.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # 分类
    classified = classify_and_filter(channels)
    demo_order = parse_demo_order_with_categories() if settings.enable_demo_filter else []

    # 生成 M3U, TXT, 多源
    generate_m3u(classified, demo_order, output_dir / "tv.m3u")
    generate_txt(classified, demo_order, output_dir / "tv.txt")
    generate_multi_m3u(classified, demo_order, output_dir / "tv_multi.m3u")

    # JSON API
    generate_json(channels, output_dir / "channels.json")

    # 精简版
    generate_lite(channels, output_dir / "tv_lite.m3u")

    logger.info("所有输出生成完成")

def generate_m3u(category_channels, demo_order, path):
    # 与原有逻辑相同，略
    pass

def generate_txt(category_channels, demo_order, path):
    # 略
    pass

def generate_multi_m3u(category_channels, demo_order, path):
    # 略
    pass

def generate_json(channels, path):
    import json, datetime
    data = {
        "version": "2.0",
        "total": len(channels),
        "generated": datetime.datetime.now().isoformat(),
        "channels": [
            {
                "name": ch["name"],
                "url": ch.get("url"),
                "urls": ch.get("urls", [ch.get("url")]),
                "latency": ch.get("latency"),
                "category": ch.get("demo_category", "")
            } for ch in channels
        ]
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def generate_lite(channels, path):
    # 精简版逻辑
    pass
