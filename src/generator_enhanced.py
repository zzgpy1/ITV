# src/generator_enhanced.py
"""增强版输出生成器：支持多种输出格式"""

import json
from pathlib import Path
from typing import List, Dict, Tuple
from src.config import OUTPUT_DIR
from src.logger import logger


class EnhancedOutputGenerator:
    """多种输出格式生成器（不依赖 EPG 注入）"""
    
    def generate_all_outputs(
        self, 
        channels: List[Dict], 
        demo_order: List[Tuple[str, str]],
        enable_json: bool = True,
        enable_lite: bool = True,
        enable_epg: bool = True
    ) -> None:
        """生成所有格式的输出文件"""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        if enable_epg:
            self._generate_epg_m3u(channels, demo_order, OUTPUT_DIR / "tv_epg.m3u")
        
        if enable_json:
            self._generate_json_api(channels, OUTPUT_DIR / "channels.json")
        
        if enable_lite:
            self._generate_lite_version(channels, OUTPUT_DIR / "tv_lite.m3u")
        
        logger.info("✅ 所有增强版输出完成")
    
    def _generate_epg_m3u(self, channels: List[Dict], demo_order: List[Tuple[str, str]], path: Path) -> None:
        channels_by_name = {ch["name"]: ch for ch in channels}
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            f.write("# 增强版 - 标准 M3U（EPG 标签已移除）\n")
            
            for cat, demo_name in demo_order:
                channel = channels_by_name.get(demo_name)
                if not channel:
                    for name, ch in channels_by_name.items():
                        if name == demo_name or demo_name in name:
                            channel = ch
                            break
                
                if channel:
                    url = channel.get("urls", [channel.get("url")])[0]
                    f.write(f'#EXTINF:-1 group-title="{cat}",{channel["name"]}\n{url}\n')
        
        logger.info(f"✅ EPG 兼容版已生成: {path}")
    
    def _generate_json_api(self, channels: List[Dict], path: Path) -> None:
        import datetime
        
        api_data = {
            "version": "2.0",
            "total": len(channels),
            "generated": datetime.datetime.now().isoformat(),
            "channels": []
        }
        
        for ch in channels:
            channel_info = {
                "name": ch["name"],
                "urls": ch.get("urls", [ch.get("url")]),
                "latency": ch.get("latency"),
                "codec": ch.get("video_codec", ""),
                "category": ch.get("demo_category", ch.get("group_title", ""))
            }
            channel_info = {k: v for k, v in channel_info.items() if v}
            api_data["channels"].append(channel_info)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(api_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ JSON API 已生成: {path}")
    
    def _generate_lite_version(self, channels: List[Dict], path: Path) -> None:
        lite_channels = []
        cat_counts = {}
        
        for ch in channels:
            cat = ch.get("demo_category", ch.get("group_title", "其他"))
            if cat == "央视" or cat == "CCTV":
                lite_channels.append(ch)
            else:
                if cat_counts.get(cat, 0) < 50:
                    lite_channels.append(ch)
                    cat_counts[cat] = cat_counts.get(cat, 0) + 1
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            f.write("# 精简版 - 仅保留最稳定源，适合移动设备\n")
            f.write(f"# 共 {len(lite_channels)} 个频道\n")
            
            for ch in lite_channels:
                url = ch.get("urls", [ch.get("url")])[0]
                cat = ch.get("demo_category", ch.get("group_title", ""))
                f.write(f'#EXTINF:-1 group-title="{cat}",{ch["name"]}\n{url}\n')
        
        logger.info(f"✅ 精简版已生成: {path}")
