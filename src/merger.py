# src/merger.py
import re
from collections import defaultdict
from src.settings import settings
from src.logger import logger
from src.constants import CCTV_ORDER
from src.fixed_sources import CCTV_FIXED_SOURCES, ENABLE_FIXED_SOURCES

def normalize_name(name: str) -> str:
    name = re.sub(r'\s*(?:1080[pi]|720[pi]|4K|8K|HD|高清|超清|标清|流畅|付费|备\d*)\s*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[（(][^）)]*[）)]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def get_standard_cctv(name: str) -> str:
    name_lower = name.lower()
    # 检查5+
    if '+' in name or '＋' in name or '5plus' in name_lower:
        return "CCTV-5+"
    # 匹配数字
    m = re.search(r'cctv[-\s]*(\d+)', name_lower)
    if m:
        num = int(m.group(1))
        if 1 <= num <= 17:
            return f"CCTV-{num}"
    # 4K/8K
    if '4k' in name_lower:
        return "CCTV-4K"
    if '8k' in name_lower:
        return "CCTV-8K"
    return None

def merge_channels_by_name(valid_channels: list) -> list:
    groups = defaultdict(list)
    for ch in valid_channels:
        raw = ch["name"]
        std = get_standard_cctv(raw)
        if std:
            norm = std
        else:
            norm = normalize_name(raw)
        groups[norm].append(ch)

    merged = []
    for name, chs in groups.items():
        chs.sort(key=lambda x: x.get("latency", 9999))
        top = chs[:settings.max_sources_per_channel]
        primary = top[0]
        merged.append({
            "name": name,
            "urls": [c["url"] for c in top],
            "url": primary["url"],
            "latency": primary.get("latency", 9999),
            "video_codec": primary.get("video_codec", ""),
            "is_fixed": False
        })

    # 应用固定源（覆盖）
    if ENABLE_FIXED_SOURCES:
        fixed_names = {ch["name"] for ch in merged}
        for fixed_name, urls in CCTV_FIXED_SOURCES.items():
            if isinstance(urls, list):
                url = urls[0] if urls else None
            else:
                url = urls
            if not url:
                continue
            # 如果已在合并列表中，更新
            found = False
            for ch in merged:
                if ch["name"] == fixed_name:
                    ch["url"] = url
                    ch["urls"] = [url] + [u for u in ch["urls"] if u != url][:settings.max_sources_per_channel-1]
                    ch["latency"] = 50
                    ch["is_fixed"] = True
                    found = True
                    break
            if not found:
                merged.append({
                    "name": fixed_name,
                    "urls": [url],
                    "url": url,
                    "latency": 50,
                    "video_codec": "h264",
                    "is_fixed": True
                })
        logger.info(f"固定源应用 {len(CCTV_FIXED_SOURCES)} 个")

    logger.info(f"合并后 {len(merged)} 个频道")
    return merged
