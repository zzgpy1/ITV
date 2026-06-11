# src/merger.py
# 频道合并模块，H.264优先 + 延迟排序

import re
from collections import defaultdict
from src.config import MAX_SOURCES_PER_CHANNEL
from src.logo_matcher import get_logo_matcher
from src.logger import logger


def normalize_channel_name(name: str) -> str:
    """
    标准化频道名，只去除清晰度标签和括号内容
    """
    # 去除清晰度标签
    name = re.sub(r'\s*(?:1080[pi]|720[pi]|4K|8K|HD|高清|超清|标清|流畅|付费|备\d*|备用\d*|备播|备源)\s*', '', name, flags=re.IGNORECASE)
    # 去除括号内容
    name = re.sub(r'[（(][^）)]*[）)]', '', name)
    # 去除多余空格
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def get_cctv_standard_name(name: str) -> str:
    """
    将央视频道名转换为标准格式
    返回标准名称，如果不是央视频道返回 None
    """
    name_original = name
    name_lower = name.lower()
    
    # ========== 1. 处理 CCTV-5+（必须包含加号）==========
    # 匹配模式: CCTV-5+, CCTV5+, CCTV 5+, CCTV-5＋, CCTV5＋
    if re.search(r'cctv[-\s]*5\s*[＋\+]', name_lower):
        logger.debug(f"CCTV-5+ 匹配: {name_original}")
        return "CCTV-5+"
    
    # ========== 2. 处理 CCTV-5（不包含加号）==========
    # 匹配模式: CCTV-5, CCTV5, CCTV 5, CCTV-5高清等
    # 关键：确保不包含加号，且5后面不是加号
    if re.search(r'cctv[-\s]*5\b', name_lower):
        # 检查是否包含加号（排除 CCTV-5+ 的情况）
        if '+' not in name_original and '＋' not in name_original:
            logger.debug(f"CCTV-5 匹配: {name_original}")
            return "CCTV-5"
    
    # ========== 3. 处理其他 CCTV-数字 ==========
    # 匹配 CCTV-1, CCTV-2, CCTV-3, CCTV-4, CCTV-6, CCTV-7, CCTV-8, CCTV-9, CCTV-10 等
    match = re.search(r'cctv[-\s]*(\d+)', name_lower)
    if match:
        num = match.group(1)
        # 排除已经处理过的 5（避免重复处理）
        if num != '5':
            logger.debug(f"CCTV-{num} 匹配: {name_original}")
            return f"CCTV-{num}"
    
    # ========== 4. 处理央视+数字 ==========
    match = re.search(r'央视[-\s]*(\d+)', name_original)
    if match:
        num = match.group(1)
        # 检查是否为 CCTV-5+
        if num == '5' and ('+' in name_original or '＋' in name_original):
            return "CCTV-5+"
        if num == '5':
            return "CCTV-5"
        return f"CCTV-{num}"
    
    # ========== 5. 处理 CGTN 系列 ==========
    if 'cgtn' in name_lower:
        if '俄' in name_original:
            return "CGTN俄语"
        if '法' in name_original:
            return "CGTN法语"
        if '西' in name_original:
            return "CGTN西语"
        if '阿' in name_original:
            return "CGTN阿语"
        if '纪录' in name_original:
            return "CGTN纪录"
        return "CGTN"
    
    return None


def merge_channels_by_name(valid_channels: list) -> list:
    """合并频道，确保 CCTV-5 和 CCTV-5+ 正确分离"""
    groups = defaultdict(list)
    
    # 先输出所有 CCTV-5 相关的原始频道名（调试用）
    cctv5_related = []
    for ch in valid_channels:
        name_lower = ch["name"].lower()
        if 'cctv-5' in name_lower or 'cctv5' in name_lower:
            cctv5_related.append(ch["name"])
    
    if cctv5_related:
        logger.info(f"📡 发现 {len(cctv5_related)} 个 CCTV-5 相关源:")
        for name in cctv5_related[:10]:
            logger.info(f"   - {name}")
    
    # 分组
    for ch in valid_channels:
        raw_name = ch["name"]
        
        # 尝试转换为标准央视频道名
        std_name = get_cctv_standard_name(raw_name)
        if std_name:
            norm_name = std_name
        else:
            norm_name = normalize_channel_name(raw_name)
            # 防止空字符串
            if not norm_name or len(norm_name) < 2:
                norm_name = raw_name
        
        groups[norm_name].append(ch)
    
    # 调试：查看分组情况
    if "CCTV-5" in groups:
        logger.info(f"✅ CCTV-5 分组: {len(groups['CCTV-5'])} 个源")
    if "CCTV-5+" in groups:
        logger.info(f"✅ CCTV-5+ 分组: {len(groups['CCTV-5+'])} 个源")
    
    logo_matcher = get_logo_matcher()
    matched_logos = 0
    
    merged = []
    for norm_name, ch_list in groups.items():
        # 排序：H.264 > H.265 > 其他，然后延迟低优先
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
    
    # 最终统计
    cctv5_count = len([ch for ch in merged if ch["name"] == "CCTV-5"])
    cctv5plus_count = len([ch for ch in merged if ch["name"] == "CCTV-5+"])
    logger.info(f"📊 合并结果: CCTV-5={cctv5_count}, CCTV-5+={cctv5plus_count}")
    
    logger.info(f"🔄 频道合并完成：{len(valid_channels)} 个源 -> {len(merged)} 个频道")
    logger.info(f"🖼️ 图标匹配：为 {matched_logos} 个频道自动匹配了图标")
    
    return merged
