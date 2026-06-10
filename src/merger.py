# src/merger.py
# 频道合并模块，H.264优先 + 延迟排序，去除"备用"等后缀

import re
from collections import defaultdict
from src.config import MAX_SOURCES_PER_CHANNEL
from src.logo_matcher import get_logo_matcher
from src.logger import logger


def normalize_channel_name(name: str) -> str:
    """
    标准化频道名用于合并分组。
    只去除清晰度标签和括号内容，不删除数字、连字符或加号。
    """
    # 去除清晰度标签（保留数字，只删除纯标签词）
    name = re.sub(r'\s*(?:1080[pi]|720[pi]|4K|8K|HD|高清|超清|标清|流畅|付费|备\d*|备用\d*|备播|备源)\s*', '', name, flags=re.IGNORECASE)
    # 去除括号及其内容
    name = re.sub(r'[（(][^）)]*[）)]', '', name)
    # 去除“备用”等字眼（不删除数字）
    name = re.sub(r'[备用备播备源]+', '', name)
    # 去除多余空格
    name = re.sub(r'\s+', ' ', name).strip()
    # 保留字母、数字、连字符、加号
    return name


def normalize_cctv_name(name: str) -> str:
    """
    专门处理央视频道名称，确保 CCTV-5 和 CCTV-5+ 正确区分
    """
    name_lower = name.lower()
    
    # 处理 CCTV-5+ / CCTV5+ / CCTV 5+
    if re.search(r'cctv[-\s]*5\s*[＋\+]', name_lower):
        return "CCTV-5+"
    
    # 处理 CCTV-5 / CCTV5 / CCTV 5 (不包含加号)
    if re.search(r'cctv[-\s]*5\b', name_lower) and '+' not in name_lower and '＋' not in name_lower:
        return "CCTV-5"
    
    # 处理其他 CCTV-数字
    match = re.search(r'cctv[-\s]*(\d+)', name_lower)
    if match:
        num = match.group(1)
        return f"CCTV-{num}"
    
    # 处理央视+数字
    match = re.search(r'央视[-\s]*(\d+)', name)
    if match:
        num = match.group(1)
        return f"CCTV-{num}"
    
    return None


def merge_channels_by_name(valid_channels: list) -> list:
    """合并频道，按 H.264 优先 + 延迟排序"""
    groups = defaultdict(list)
    
    for ch in valid_channels:
        raw_name = ch["name"]
        
        # 尝试标准化为央视频道标准名
        cctv_name = normalize_cctv_name(raw_name)
        if cctv_name:
            norm_name = cctv_name
        else:
            # 非央视频道使用通用标准化
            norm_name = normalize_channel_name(raw_name)
            # 防止归一化后变成空字符串
            if not norm_name or norm_name.strip() == "":
                norm_name = raw_name.strip()
        
        groups[norm_name].append(ch)

    logo_matcher = get_logo_matcher()
    matched_logos = 0
    
    merged = []
    for norm_name, ch_list in groups.items():
        # 排序：优先 H.264，然后延迟低
        def sort_key(ch):
            codec = ch.get("video_codec", "").lower()
            if codec == "h264":
                codec_priority = 0
            elif codec in ["hevc", "h265"]:
                codec_priority = 1
            else:
                codec_priority = 2
            latency = ch.get("latency", 9999)
            return (codec_priority, latency)
        
        ch_list.sort(key=sort_key)
        top = ch_list[:MAX_SOURCES_PER_CHANNEL]
        primary = top[0]
        
        # 最终频道名：使用标准化名称
        channel_name = norm_name
        
        logo_url = primary.get("tvg_logo", "")
        if not logo_url:
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
        }
        merged.append(merged_ch)
    
    # 输出调试信息，检查是否有空名称
    empty_names = [ch["name"] for ch in merged if not ch["name"] or len(ch["name"]) < 2]
    if empty_names:
        logger.warning(f"⚠️ 发现异常频道名: {empty_names[:5]}")
    
    logger.info(f"🔄 频道合并完成：{len(valid_channels)} 个源 -> {len(merged)} 个频道")
    logger.info(f"🖼️ 图标匹配：为 {matched_logos} 个频道自动匹配了图标")
    return merged
