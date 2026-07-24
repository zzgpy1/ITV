# src/services/generator.py
"""生成服务"""

import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime

from src.core.config import get_config
from src.core.constants import OUTPUT_CATEGORY_ORDER
from src.infrastructure.logger import get_logger

logger = get_logger(__name__)


class Generator:
    """输出生成器"""
    
    def __init__(self):
        self.config = get_config()
    
    def generate_all(self, channels: List[Dict], demo_order: List[Tuple[str, str]] = None) -> None:
        """生成所有输出"""
        output_dir = self.config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 按 demo 分类
        if demo_order:
            categorized = self._categorize_by_demo(channels, demo_order)
        else:
            categorized = self._categorize_by_group(channels)
        
        # 生成 M3U
        self._generate_m3u(categorized, output_dir / "tv.m3u")
        
        # 生成 TXT
        self._generate_txt(categorized, output_dir / "tv.txt")
        
        # 生成多源 M3U
        self._generate_multi_m3u(categorized, output_dir / "tv_multi.m3u")
        
        # 生成 JSON
        self._generate_json(channels, output_dir / "channels.json")
        
        logger.info("✅ 所有输出文件已生成")
    
    def _categorize_by_demo(self, channels: List[Dict], demo_order: List[Tuple[str, str]]) -> Dict[str, List[Dict]]:
        """按 demo 分类"""
        result = {}
        name_to_channel = {ch["name"]: ch for ch in channels}
        
        for cat, demo_name in demo_order:
            if cat not in result:
                result[cat] = []
            
            if demo_name in name_to_channel:
                ch = name_to_channel[demo_name]
                if ch not in result[cat]:
                    result[cat].append(ch)
        
        # 未分类的频道
        categorized_names = set()
        for cat, ch_list in result.items():
            for ch in ch_list:
                categorized_names.add(ch["name"])
        
        for ch in channels:
            if ch["name"] not in categorized_names:
                cat = ch.get("demo_category", ch.get("group_title", "其他"))
                if cat not in result:
                    result[cat] = []
                result[cat].append(ch)
        
        return result
    
    def _categorize_by_group(self, channels: List[Dict]) -> Dict[str, List[Dict]]:
        """按 group_title 分类"""
        result = {}
        for ch in channels:
            cat = ch.get("group_title", "其他")
            if cat not in result:
                result[cat] = []
            result[cat].append(ch)
        return result
    
    def _generate_m3u(self, categorized: Dict[str, List[Dict]], path: Path) -> None:
        """生成 M3U"""
        with open(path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            
            for cat, channels in categorized.items():
                if not channels:
                    continue
                for ch in channels:
                    url = ch.get("url", "")
                    if url:
                        name = ch.get("name", "未知频道")
                        f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n{url}\n')
        
        logger.info(f"✅ M3U 文件已生成: {path}")
    
    def _generate_txt(self, categorized: Dict[str, List[Dict]], path: Path) -> None:
        """生成 TXT"""
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            
            for cat, channels in categorized.items():
                if not channels:
                    continue
                f.write(f"{cat},#genre#\n")
                for ch in channels:
                    url = ch.get("url", "")
                    if url:
                        name = ch.get("name", "未知频道")
                        f.write(f"{name},{url}\n")
        
        logger.info(f"✅ TXT 文件已生成: {path}")
    
    def _generate_multi_m3u(self, categorized: Dict[str, List[Dict]], path: Path) -> None:
        """生成多源 M3U"""
        with open(path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            
            for cat, channels in categorized.items():
                if not channels:
                    continue
                for ch in channels:
                    urls = ch.get("urls", [ch.get("url", "")])
                    valid_urls = [u for u in urls if u and u.startswith(('http://', 'https://'))]
                    if valid_urls:
                        name = ch.get("name", "未知频道")
                        f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n{" # ".join(valid_urls)}\n')
        
        logger.info(f"✅ 多源 M3U 文件已生成: {path}")
    
    def _generate_json(self, channels: List[Dict], path: Path) -> None:
        """生成 JSON"""
        data = {
            "version": "2.0",
            "total": len(channels),
            "generated": datetime.now().isoformat(),
            "channels": []
        }
        
        for ch in channels:
            channel_info = {
                "name": ch.get("name", ""),
                "url": ch.get("url", ""),
                "urls": ch.get("urls", []),
                "latency": ch.get("latency"),
                "codec": ch.get("video_codec", ""),
                "category": ch.get("group_title", ""),
                "is_fixed": ch.get("is_fixed", False),
            }
            channel_info = {k: v for k, v in channel_info.items() if v}
            data["channels"].append(channel_info)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ JSON 文件已生成: {path}")
