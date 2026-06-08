# src/merger.py
# 频道合并模块，增加图标自动匹配

import re
from collections import defaultdict
from src.config import MAX_SOURCES_PER_CHANNEL
from src.logo_matcher import get_logo_matcher
from src.logger import logger

def normalize_channel_name(name: str) -> str:
    """
    标准化频道名用于合并分组。
    只去除清晰度标签和括号内容，不做任何字符转换。
    特别保留 "CCTV-1" 和 "CCTV-17" 的差异。
    """
    # 去除清晰度标签（但保留数字和连字符）
    name = re.sub(r'\s*(?:1080[pi]|720[pi]|4K|8K|HD|高清|超清|标清|流畅|付费|备\d*)\s*', '', name, flags=re.IGNORECASE)
    # 去除括号内容
    name = re.sub(r'[（(][^）)]*[）)]', '', name)
    # 去除多余空格
    name = re.sub(r'\s+', ' ', name).strip()
    # 关键：不做任何 "CCTV1" -> "CCTV-1" 的转换，保持原样
    return name

def merge_channels_by_name(valid_channels: list) -> list:
    groups = defaultdict(list)
    for ch in valid_channels:
        norm_name = normalize_channel_name(ch["name"])
        groups[norm_name].append(ch)

    # 初始化图标匹配器
    logo_matcher = get_logo_matcher()
    matched_logos = 0
    
    merged = []
    for norm_name, ch_list in groups.items():
        # 排序：优先 H.264，然后延迟低
        def sort_key(ch):
            codec = ch.get("video_codec", "")
            codec_priority = 0 if codec == "h264" else 1 if codec == "hevc" else 2
            latency = ch.get("latency", 9999)
            return (codec_priority, latency)
        ch_list.sort(key=sort_key)
        top = ch_list[:MAX_SOURCES_PER_CHANNEL]
        primary = top[0]
        
        # 获取频道图标
        channel_name = primary["name"]
        logo_url = primary.get("tvg_logo", "")
        
        # 如果原数据没有图标，尝试自动匹配
        if not logo_url or logo_url == "":
            logo_url = logo_matcher.get_logo_url(channel_name)
            matched_logos += 1
        
        merged_ch = {
            "name": channel_name,
            "urls": [c["url"] for c in top],
            "url": primary["url"],
            "latency": primary["latency"],
            "video_codec": primary["video_codec"],
            "group_title": primary.get("group_title", ""),
            "id": primary.get("tvg_id", ""),
            "logo": logo_url,
            "ip_info": primary.get("ip_info")
        }
        merged.append(merged_ch)
    
    logger.info(f"🔄 频道合并完成：{len(valid_channels)} 个源 -> {len(merged)} 个频道")
    logger.info(f"🖼️ 图标匹配：为 {matched_logos} 个频道自动匹配了图标")
    return merged
