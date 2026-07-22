# src/generator.py
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict
from src.settings import settings
from src.logger import logger
import json
import datetime

class OutputGenerator:
    def generate_all(self, channels: List[Dict], demo_order: List[Tuple[str, str]]):
        output_dir = settings.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        # 按 demo_order 构建分类
        cat_channels = defaultdict(list)
        for ch in channels:
            cat = ch.get("demo_category", "其他")
            cat_channels[cat].append(ch)
        # 保证顺序
        ordered_cats = []
        seen = set()
        for cat, _ in demo_order:
            if cat not in seen:
                seen.add(cat)
                ordered_cats.append(cat)
        # 添加未在 demo 中的分类
        for cat in cat_channels:
            if cat not in seen:
                ordered_cats.append(cat)
        self._generate_m3u(cat_channels, ordered_cats, output_dir / "tv.m3u")
        self._generate_txt(cat_channels, ordered_cats, output_dir / "tv.txt")
        self._generate_multi_m3u(cat_channels, ordered_cats, output_dir / "tv_multi.m3u")
        if settings.enable_json_output:
            self._generate_json(channels, output_dir / "channels.json")
        if settings.enable_lite_version:
            self._generate_lite(cat_channels, output_dir / "tv_lite.m3u")
        logger.info("✅ 输出生成完成")

    def _generate_m3u(self, cat_channels, ordered_cats, path):
        with open(path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for cat in ordered_cats:
                for ch in cat_channels.get(cat, []):
                    url = ch.get("url", "")
                    if url:
                        name = ch.get("demo_name", ch["name"])
                        f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n{url}\n')

    def _generate_txt(self, cat_channels, ordered_cats, path):
        with open(path, 'w', encoding='utf-8') as f:
            for cat in ordered_cats:
                chs = cat_channels.get(cat, [])
                if not chs:
                    continue
                f.write(f"{cat},#genre#\n")
                for ch in chs:
                    url = ch.get("url", "")
                    if url:
                        name = ch.get("demo_name", ch["name"])
                        f.write(f"{name},{url}\n")

    def _generate_multi_m3u(self, cat_channels, ordered_cats, path):
        with open(path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for cat in ordered_cats:
                for ch in cat_channels.get(cat, []):
                    urls = ch.get("urls", [ch.get("url")])
                    valid = [u for u in urls if u]
                    if valid:
                        name = ch.get("demo_name", ch["name"])
                        f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n{" # ".join(valid)}\n')

    def _generate_json(self, channels, path):
        data = {
            "version": "2.0",
            "total": len(channels),
            "generated": datetime.datetime.now().isoformat(),
            "channels": [
                {
                    "name": ch["name"],
                    "urls": ch.get("urls", [ch.get("url")]),
                    "latency": ch.get("latency"),
                    "codec": ch.get("video_codec", ""),
                    "category": ch.get("demo_category", "")
                }
                for ch in channels
            ]
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _generate_lite(self, cat_channels, path):
        lite = []
        for cat, chs in cat_channels.items():
            sorted_chs = sorted(chs, key=lambda x: x.get("latency", 9999))
            lite.extend(sorted_chs[:50])  # 每分类最多50
        with open(path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n# 精简版\n")
            for ch in lite:
                url = ch.get("url", "")
                if url:
                    cat = ch.get("demo_category", "")
                    name = ch.get("demo_name", ch["name"])
                    f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n{url}\n')
