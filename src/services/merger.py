# src/services/merger.py
"""合并服务"""

import re
from collections import defaultdict
from typing import List, Dict

from src.core.config import get_config
from src.core.constants import CCTV_ORDER
from src.infrastructure.logger import get_logger

logger = get_logger(__name__)


class Merger:
    """频道合并器"""
    
    def __init__(self):
        self.config = get_config()
    
    def normalize_channel_name(self, name: str) -> str:
        """标准化频道名"""
        name = re.sub(r'\s*(?:1080[pi]|720[pi]|4K|8K|HD|高清|超清|标清)\s*', '', name, flags=re.IGNORECASE)
        name = re.sub(r'[（(][^）)]*[）)]', '', name)
        name = re.sub(r'\s+', ' ', name).strip()
        return name
    
    def get_cctv_standard_name(self, name: str) -> str:
        """获取央视频道标准名"""
        name_clean = re.sub(r'\s*\([^)]*\)', '', name)
        name_lower = name_clean.lower()
        
        # 匹配 CCTV-数字
        match = re.match(r'^cctv[-\s]*(\d+)(?:\+|plus)?', name_lower)
        if match:
            num = match.group(1)
            if num.isdigit():
                num_int = int(num)
                if 1 <= num_int <= 17:
                    if '+' in name_lower or 'plus' in name_lower:
                        return f"CCTV-{num_int}+"
                    return f"CCTV-{num_int}"
        
        # 匹配 央视数字
        match = re.search(r'央视[-\s]*(\d+)', name_clean)
        if match:
            num = int(match.group(1))
            if 1 <= num <= 17:
                return f"CCTV-{num}"
        
        return None
    
    def get_channel_quality_score(self, channel: Dict) -> tuple:
        """获取频道质量分数"""
        if channel.get("is_fixed"):
            return (0, 0, 0)
        
        codec = channel.get("video_codec", "").lower()
        codec_priority = 1 if codec == "h264" else 2 if codec in ["hevc", "h265"] else 3
        
        latency = channel.get("latency", 9999)
        url = channel.get("url", "").lower()
        url_bonus = 0 if ".m3u8" in url else 1 if ".ts" in url else 2
        
        return (codec_priority, latency, url_bonus)
    
    def merge(self, channels: List[Dict]) -> List[Dict]:
        """合并频道"""
        groups = defaultdict(list)
        
        for ch in channels:
            # 获取标准名
            raw_name = ch.get("name", "")
            std_name = self.get_cctv_standard_name(raw_name)
            if std_name:
                norm_name = std_name
            else:
                norm_name = self.normalize_channel_name(raw_name)
                if not norm_name or len(norm_name) < 2:
                    norm_name = raw_name
            
            groups[norm_name].append(ch)
        
        merged = []
        for norm_name, ch_list in groups.items():
            # 按质量排序
            ch_list.sort(key=self.get_channel_quality_score)
            top = ch_list[:self.config.max_sources_per_channel]
            primary = top[0] if top else None
            
            if not primary:
                continue
            
            merged.append({
                "name": norm_name,
                "url": primary["url"],
                "urls": [c["url"] for c in top],
                "latency": primary.get("latency", 9999),
                "video_codec": primary.get("video_codec", ""),
                "group_title": primary.get("group_title", ""),
                "is_fixed": primary.get("is_fixed", False),
            })
        
        logger.info(f"📊 合并完成: {len(merged)} 个频道")
        return merged
