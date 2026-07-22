import re
from collections import defaultdict
from src.settings import settings
from src.logger import logger
from src.services.alias_matcher import get_alias_matcher

def normalize_channel_name(name: str) -> str:
    name = re.sub(r'\s*(?:1080[pi]|720[pi]|4K|8K|HD|高清|超清|标清|流畅|付费|备\d*|备用\d*|备播|备源)\s*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[（(][^）)]*[）)]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def get_channel_quality(channel: dict) -> tuple:
    codec = channel.get("video_codec", "").lower()
    codec_score = 0 if codec in ("h264", "h265", "hevc") else 1
    latency = channel.get("latency", 9999)
    return (codec_score, latency)

def merge_channels_by_name(valid_channels: list) -> list:
    groups = defaultdict(list)
    matcher = get_alias_matcher()
    for ch in valid_channels:
        raw_name = ch["name"]
        if matcher:
            std = matcher.normalize(raw_name)
        else:
            std = normalize_channel_name(raw_name)
        groups[std].append(ch)

    merged = []
    for name, ch_list in groups.items():
        ch_list.sort(key=get_channel_quality)
        top = ch_list[:settings.max_sources_per_channel]
        primary = top[0]
        merged.append({
            "name": name,
            "url": primary["url"],
            "urls": [c["url"] for c in top],
            "latency": primary.get("latency", 9999),
            "video_codec": primary.get("video_codec", ""),
            "group_title": primary.get("group_title", ""),
        })
    logger.info(f"📊 合并后 {len(merged)} 个频道")
    return merged
