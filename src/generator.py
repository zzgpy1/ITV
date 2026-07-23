# src/generator.py
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict
from src.settings import settings
from src.logger import logger
import json


class OutputGenerator:
    def generate_all(self, channels: List[Dict], demo_order: List[Tuple[str, str]]):
        output_dir = settings.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        # 按 demo_category 分组
        category_channels = defaultdict(list)
        for ch in channels:
            cat = ch.get("demo_category", "其他")
            category_channels[cat].append(ch)

        # 确定分类顺序
        demo_cats = [cat for cat, _ in demo_order] if demo_order else list(category_channels.keys())

        self._generate_m3u(category_channels, demo_cats, output_dir / "tv.m3u")
        self._generate_txt(category_channels, demo_cats, output_dir / "tv.txt")
        self._generate_multi_m3u(category_channels, demo_cats, output_dir / "tv_multi.m3u")

        if settings.enable_json_output:
            self._generate_json(channels, output_dir / "channels.json")
        if settings.enable_lite_version:
            self._generate_lite(channels, output_dir / "tv_lite.m3u")

        logger.info("✅ 输出生成完成")

    def _get_url(self, ch: dict) -> str:
        url = ch.get("url")
        if isinstance(url, list):
            return url[0] if url else ""
        return url or ""

    def _generate_m3u(self, category_channels: Dict, category_order: List[str], path: Path):
        with open(path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for cat in category_order:
                channels = category_channels.get(cat, [])
                for ch in channels:
                    url = self._get_url(ch)
                    if url:
                        name = ch.get("demo_name") or ch.get("name", "未知频道")
                        f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n{url}\n')
        logger.info(f"✅ M3U 文件已生成: {path}")

    def _generate_txt(self, category_channels: Dict, category_order: List[str], path: Path):
        with open(path, 'w', encoding='utf-8') as f:
            for cat in category_order:
                channels = category_channels.get(cat, [])
                if not channels:
                    continue
                f.write(f"{cat},#genre#\n")
                for ch in channels:
                    url = self._get_url(ch)
                    if url:
                        name = ch.get("demo_name") or ch.get("name", "未知频道")
                        f.write(f"{name},{url}\n")
        logger.info(f"✅ TXT 文件已生成: {path}")

    def _generate_multi_m3u(self, category_channels: Dict, category_order: List[str], path: Path):
        with open(path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for cat in category_order:
                channels = category_channels.get(cat, [])
                for ch in channels:
                    urls = ch.get("urls", [])
                    valid = [u for u in urls if u and isinstance(u, str) and u.startswith(('http://', 'https://'))]
                    if valid:
                        name = ch.get("demo_name") or ch.get("name", "未知频道")
                        f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n{" # ".join(valid)}\n')
        logger.info(f"✅ 多源 M3U 文件已生成: {path}")

    def _generate_json(self, channels: List[Dict], path: Path):
        import datetime
        data = {
            "version": "2.0",
            "total": len(channels),
            "generated": datetime.datetime.now().isoformat(),
            "channels": []
        }
        for ch in channels:
            data["channels"].append({
                "name": ch.get("name", ""),
                "urls": ch.get("urls", [ch.get("url")]),
                "latency": ch.get("latency"),
                "codec": ch.get("video_codec", ""),
                "category": ch.get("demo_category", ""),
                "logo": ch.get("logo", "")
            })
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ JSON 文件已生成: {path}")

    def _generate_lite(self, channels: List[Dict], path: Path):
        groups = defaultdict(list)
        for ch in channels:
            cat = ch.get("demo_category", "其他")
            groups[cat].append(ch)

        lite = []
        for cat, items in groups.items():
            items.sort(key=lambda x: x.get("latency", 9999))
            lite.extend(items[:50])

        with open(path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n# 精简版 - 仅保留最稳定源\n")
            for ch in lite:
                url = self._get_url(ch)
                if url:
                    cat = ch.get("demo_category", "")
                    name = ch.get("demo_name") or ch.get("name", "未知频道")
                    f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n{url}\n')
        logger.info(f"✅ 精简版已生成: {path}")


def generate_outputs_from_demo(ordered_channels: List[dict], demo_order: List[Tuple[str, str]]) -> None:
    if not ordered_channels:
        logger.warning("无频道数据，跳过输出生成")
        return
    generator = OutputGenerator()
    generator.generate_all(ordered_channels, demo_order)
