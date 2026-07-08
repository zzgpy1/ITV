# src/merger.py
import re
from collections import defaultdict
from src.config import MAX_SOURCES_PER_CHANNEL
from src.logo_matcher import get_logo_matcher
from src.logger import logger
from src.fixed_sources import CCTV_FIXED_SOURCES, ENABLE_FIXED_SOURCES


def normalize_channel_name(name: str) -> str:
    """标准化频道名，去除清晰度标签和括号内容"""
    name = re.sub(r'\s*(?:1080[pi]|720[pi]|4K|8K|HD|高清|超清|标清|流畅|付费|备\d*|备用\d*|备播|备源)\s*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[（(][^）)]*[）)]', '', name)
    name = re.sub(r'[备用备播备源]+', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def is_cctv5plus(name: str) -> bool:
    name_lower = name.lower()
    if '+' in name or '＋' in name:
        return True
    if '5plus' in name_lower or '5+' in name_lower:
        return True
    if '央视5+' in name or '中央5+' in name:
        return True
    return False


def is_cctv5(name: str) -> bool:
    name_lower = name.lower()
    if '+' in name or '＋' in name:
        return False
    if '5plus' in name_lower:
        return False
    if re.search(r'cctv[-\s]*5\b', name_lower):
        return True
    if '央视5' in name or '中央5' in name:
        return True
    return False


def get_cctv_standard_name(name: str) -> str:
    """
    获取央视频道的标准名称，优先精确匹配，避免误将 CCTV-15 判为 CCTV-1。
    """
    name_clean = re.sub(r'\s*\([^)]*\)', '', name)
    name_lower = name_clean.lower()

    # 1. 如果已经是 "CCTV-数字" 格式，直接返回
    exact_match = re.match(r'^cctv[-\s]*(\d+)(?:\+|plus)?', name_lower)
    if exact_match:
        num = exact_match.group(1)
        if num.isdigit():
            num_int = int(num)
            if 1 <= num_int <= 17:
                if '+' in name_lower or 'plus' in name_lower:
                    return f"CCTV-{num_int}+"
                return f"CCTV-{num_int}"
        # 处理 4K/8K
        if '4k' in name_lower:
            return "CCTV-4K"
        if '8k' in name_lower:
            return "CCTV-8K"

    # 2. 特殊处理 CCTV-5+ 和 CCTV-5
    if is_cctv5plus(name_clean):
        return "CCTV-5+"
    if is_cctv5(name_clean):
        return "CCTV-5"

    # 3. 降级：正则搜索数字（但已由第一步规避）
    match = re.search(r'cctv[-\s]*(\d+)', name_lower)
    if match:
        num = int(match.group(1))
        if 1 <= num <= 17:
            return f"CCTV-{num}"

    # 4. 中文 "央视数字"
    match = re.search(r'央视[-\s]*(\d+)', name_clean)
    if match:
        num = int(match.group(1))
        if 1 <= num <= 17:
            return f"CCTV-{num}"

    return None


def get_channel_quality_score(channel: dict) -> tuple:
    if channel.get("is_fixed"):
        return (0, 0, 0)
    codec = channel.get("video_codec", "").lower()
    if codec == "h264":
        codec_priority = 1
    elif codec in ["hevc", "h265"]:
        codec_priority = 2
    else:
        codec_priority = 3
    latency = channel.get("latency", 9999)
    url = channel.get("url", "").lower()
    url_bonus = 0
    if ".m3u8" in url:
        url_bonus = 0
    elif ".ts" in url:
        url_bonus = 1
    else:
        url_bonus = 2
    return (codec_priority, latency, url_bonus)


def merge_channels_by_name(valid_channels: list) -> list:
    """
    合并频道，修复央视频道分组错误：优先使用已标准化的名称。
    """
    groups = defaultdict(list)
    for ch in valid_channels:
        raw_name = ch["name"]
        
        # 优先使用已标准化的名称（如果已以 "CCTV-" 开头）
        if raw_name.startswith("CCTV-") and re.match(r'^CCTV-\d+', raw_name):
            norm_name = raw_name
        else:
            std_name = get_cctv_standard_name(raw_name)
            if std_name:
                norm_name = std_name
            else:
                norm_name = normalize_channel_name(raw_name)
                if not norm_name or len(norm_name) < 2:
                    norm_name = raw_name
        groups[norm_name].append(ch)

    logo_matcher = get_logo_matcher()
    merged = []

    for norm_name, ch_list in groups.items():
        ch_list.sort(key=get_channel_quality_score)
        top = ch_list[:MAX_SOURCES_PER_CHANNEL]
        primary = top[0] if top else None
        if not primary:
            continue
        merged.append({
            "name": norm_name,
            "urls": [c["url"] for c in top],
            "url": primary["url"],
            "latency": primary.get("latency", 9999),
            "video_codec": primary.get("video_codec", ""),
            "group_title": primary.get("group_title", ""),
            "id": primary.get("tvg_id", ""),
            "logo": logo_matcher.get_logo_url(norm_name) if not primary.get("tvg_logo") else primary.get("tvg_logo"),
            "is_fixed": primary.get("is_fixed", False),
        })

    # 固定源处理
    if ENABLE_FIXED_SOURCES:
        merged_names = {ch["name"] for ch in merged}
        for fixed_name, fixed_urls in CCTV_FIXED_SOURCES.items():
            if isinstance(fixed_urls, str):
                fixed_urls = [fixed_urls]
            fixed_urls = [u for u in fixed_urls if u and u.strip()]
            if not fixed_urls:
                continue
            all_sources_for_fixed = []
            for vch in valid_channels:
                if vch["name"] == fixed_name or get_cctv_standard_name(vch["name"]) == fixed_name:
                    all_sources_for_fixed.append(vch)
            all_sources_for_fixed.sort(key=lambda x: x.get("latency", 9999))
            if fixed_name in merged_names:
                for ch in merged:
                    if ch["name"] == fixed_name:
                        candidate_urls = fixed_urls + [s["url"] for s in all_sources_for_fixed if s["url"] not in fixed_urls]
                        unique_urls = []
                        seen = set()
                        for u in candidate_urls:
                            if u not in seen:
                                seen.add(u)
                                unique_urls.append(u)
                        candidates_with_lat = []
                        for u in unique_urls:
                            lat = 9999
                            for s in all_sources_for_fixed:
                                if s["url"] == u:
                                    lat = s.get("latency", 9999)
                                    break
                            candidates_with_lat.append((u, lat))
                        candidates_with_lat.sort(key=lambda x: x[1])
                        best_url = candidates_with_lat[0][0] if candidates_with_lat else fixed_urls[0]
                        ch["url"] = best_url
                        ch["urls"] = [u for u, _ in candidates_with_lat[:MAX_SOURCES_PER_CHANNEL]]
                        if candidates_with_lat:
                            ch["latency"] = candidates_with_lat[0][1]
                        else:
                            ch["latency"] = 50
                        ch["video_codec"] = "h264"
                        ch["is_fixed"] = True
                        break
            else:
                if all_sources_for_fixed:
                    best = all_sources_for_fixed[0]
                    all_urls = list(dict.fromkeys(fixed_urls + [s["url"] for s in all_sources_for_fixed]))
                    candidates_with_lat = []
                    for u in all_urls:
                        lat = 9999
                        for s in all_sources_for_fixed:
                            if s["url"] == u:
                                lat = s.get("latency", 9999)
                                break
                        candidates_with_lat.append((u, lat))
                    candidates_with_lat.sort(key=lambda x: x[1])
                    best_url = candidates_with_lat[0][0]
                    merged.append({
                        "name": fixed_name,
                        "urls": [u for u, _ in candidates_with_lat[:MAX_SOURCES_PER_CHANNEL]],
                        "url": best_url,
                        "latency": candidates_with_lat[0][1] if candidates_with_lat else 50,
                        "video_codec": "h264",
                        "group_title": "央视",
                        "id": "",
                        "logo": logo_matcher.get_logo_url(fixed_name),
                        "is_fixed": True,
                    })
                else:
                    merged.append({
                        "name": fixed_name,
                        "urls": fixed_urls,
                        "url": fixed_urls[0],
                        "latency": 50,
                        "video_codec": "h264",
                        "group_title": "央视",
                        "id": "",
                        "logo": logo_matcher.get_logo_url(fixed_name),
                        "is_fixed": True,
                    })

    # 确保 url 字段为字符串
    for ch in merged:
        if isinstance(ch.get("url"), list):
            ch["url"] = ch["url"][0] if ch["url"] else ""
        if not isinstance(ch.get("urls"), list):
            ch["urls"] = [ch["url"]] if ch["url"] else []

    fixed_count = sum(1 for ch in merged if ch.get("is_fixed"))
    if fixed_count > 0:
        logger.info(f"📌 已使用 {fixed_count} 个固定优质源（含自动择优）")
    logger.info(f"📊 合并完成: 共 {len(merged)} 个频道")
    return merged
