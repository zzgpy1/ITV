# src/merger.py
import re
from collections import defaultdict
from src.settings import settings
from src.logo_matcher import get_logo_matcher
from src.logger import logger
from src.fixed_sources import CCTV_FIXED_SOURCES, ENABLE_FIXED_SOURCES
from src.constants import CCTV_ORDER


def normalize_channel_name(name: str) -> str:
    name = re.sub(r'\s*(?:1080[pi]|720[pi]|4K|8K|HD|高清|超清|标清|流畅|付费|备\d*|备用\d*|备播|备源)\s*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[（(][^）)]*[）)]', '', name)
    name = re.sub(r'[备用备播备源]+', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def is_cctv5plus(name: str) -> bool:
    name_lower = name.lower()
    return '+' in name or '＋' in name or '5plus' in name_lower


def get_cctv_standard_name(name: str) -> str:
    name_clean = re.sub(r'\s*\([^)]*\)', '', name)
    name_lower = name_clean.lower()

    exact_match = re.match(r'^cctv[-\s]*(\d+)(?:\+|plus)?', name_lower)
    if exact_match:
        num = exact_match.group(1)
        if num.isdigit():
            num_int = int(num)
            if 1 <= num_int <= 17:
                if '+' in name_lower or 'plus' in name_lower:
                    return f"CCTV-{num_int}+"
                return f"CCTV-{num_int}"
        if '4k' in name_lower:
            return "CCTV-4K"
        if '8k' in name_lower:
            return "CCTV-8K"

    if is_cctv5plus(name_clean):
        return "CCTV-5+"

    match = re.search(r'cctv[-\s]*(\d+)', name_lower)
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
    return (codec_priority, latency, 0)


def merge_channels_by_name(valid_channels: list) -> list:
    """合并频道，确保固定源不覆盖其他频道"""
    if not valid_channels:
        logger.warning("⚠️ 没有有效频道，返回空列表")
        return []

    groups = defaultdict(list)
    for ch in valid_channels:
        raw_name = ch.get("name", "未知频道")
        if raw_name.startswith("CCTV-") and re.match(r'^CCTV-\d+', raw_name):
            norm_name = raw_name
        else:
            std_name = get_cctv_standard_name(raw_name)
            norm_name = std_name if std_name else normalize_channel_name(raw_name)
            if not norm_name or len(norm_name) < 2:
                norm_name = raw_name
        groups[norm_name].append(ch)

    logo_matcher = get_logo_matcher()
    merged = []

    for norm_name, ch_list in groups.items():
        ch_list.sort(key=get_channel_quality_score)
        top = ch_list[:settings.max_sources_per_channel]
        primary = top[0] if top else None
        if not primary:
            continue
        merged.append({
            "name": norm_name,
            "urls": [c.get("url", "") for c in top],
            "url": primary.get("url", ""),
            "latency": primary.get("latency", 9999),
            "video_codec": primary.get("video_codec", ""),
            "group_title": primary.get("group_title", ""),
            "id": primary.get("tvg_id", ""),
            "logo": primary.get("tvg_logo") or logo_matcher.get_logo_url(norm_name),
            "is_fixed": primary.get("is_fixed", False),
        })

    # 固定源处理 - 只更新已存在的固定源频道，不添加新的固定源
    if ENABLE_FIXED_SOURCES and merged:
        merged_names = {ch["name"] for ch in merged}
        for fixed_name, fixed_urls in CCTV_FIXED_SOURCES.items():
            if isinstance(fixed_urls, str):
                fixed_urls = [fixed_urls]
            fixed_urls = [u for u in fixed_urls if u and u.strip()]
            if not fixed_urls or fixed_name not in merged_names:
                continue

            for ch in merged:
                if ch["name"] == fixed_name:
                    # 收集所有可用的源
                    all_sources = []
                    for vch in valid_channels:
                        vch_name = vch.get("name", "")
                        if vch_name == fixed_name or get_cctv_standard_name(vch_name) == fixed_name:
                            all_sources.append(vch)
                    all_sources.sort(key=lambda x: x.get("latency", 9999))

                    candidate_urls = fixed_urls + [s.get("url", "") for s in all_sources if s.get("url") not in fixed_urls]
                    unique_urls = list(dict.fromkeys([u for u in candidate_urls if u]))

                    candidates_with_lat = []
                    for u in unique_urls:
                        lat = next((s.get("latency", 9999) for s in all_sources if s.get("url") == u), 9999)
                        candidates_with_lat.append((u, lat))
                    candidates_with_lat.sort(key=lambda x: x[1])

                    if candidates_with_lat:
                        ch["url"] = candidates_with_lat[0][0]
                        ch["urls"] = [u for u, _ in candidates_with_lat[:settings.max_sources_per_channel]]
                        ch["latency"] = candidates_with_lat[0][1]
                        ch["video_codec"] = "h264"
                        ch["is_fixed"] = True
                    break

    # 确保 url 字段为字符串
    for ch in merged:
        if isinstance(ch.get("url"), list):
            ch["url"] = ch["url"][0] if ch["url"] else ""
        if not ch.get("url"):
            ch["url"] = ch.get("urls", [""])[0] if ch.get("urls") else ""
        if not isinstance(ch.get("urls"), list):
            ch["urls"] = [ch["url"]] if ch["url"] else []

    fixed_count = sum(1 for ch in merged if ch.get("is_fixed"))
    if fixed_count > 0:
        logger.info(f"📌 固定源: {fixed_count} 个")
    logger.info(f"📊 合并完成: 共 {len(merged)} 个频道")
    return merged
