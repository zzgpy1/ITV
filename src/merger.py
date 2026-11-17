import re
from collections import defaultdict
from src.config_loader import config
from src.logo_matcher import get_logo_matcher
from src.logger import logger
from src.constants import CCTV_ORDER


def normalize_channel_name(name: str) -> str:
    name = re.sub(r'\s*(?:1080[pi]|720[pi]|4K|8K|HD|高清|超清|标清|流畅|付费|备\d*|备用\d*|备播|备源)\s*',
                  '', name, flags=re.IGNORECASE)
    name = re.sub(r'[（(][^）)]*[）)]', '', name)
    name = re.sub(r'[备用备播备源]+', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def is_cctv5plus(name: str) -> bool:
    return '+' in name or '＋' in name or '5plus' in name.lower()


def is_cctv5(name: str) -> bool:
    if is_cctv5plus(name):
        return False
    return bool(re.search(r'cctv[-\s]*5\b', name.lower())) or '央视5' in name or '中央5' in name


def get_cctv_standard_name(name: str) -> str:
    name_clean = re.sub(r'\s*\([^)]*\)', '', name)
    name_lower = name_clean.lower()
    exact = re.match(r'^cctv[-\s]*(\d+)(?:\+|plus)?', name_lower)
    if exact:
        num = exact.group(1)
        if num.isdigit():
            num_int = int(num)
            if 1 <= num_int <= 17:
                if '+' in name_lower or 'plus' in name_lower:
                    return f"CCTV-{num_int}+"
                return f"CCTV-{num_int}"
        if '4k' in name_lower: return "CCTV-4K"
        if '8k' in name_lower: return "CCTV-8K"
    if is_cctv5plus(name_clean): return "CCTV-5+"
    if is_cctv5(name_clean): return "CCTV-5"
    match = re.search(r'cctv[-\s]*(\d+)', name_lower)
    if match:
        num = int(match.group(1))
        if 1 <= num <= 17:
            return f"CCTV-{num}"
    match = re.search(r'央视[-\s]*(\d+)', name_clean)
    if match:
        num = int(match.group(1))
        if 1 <= num <= 17:
            return f"CCTV-{num}"
    return None


def get_channel_quality_score(channel: dict) -> tuple:
    if channel.get("is_fixed"):
        return (0, 0, 0, 0)
    priority = int(channel.get("source_priority", 5))
    codec = channel.get("video_codec", "").lower()
    codec_priority = 1 if codec == "h264" else 2 if codec in ["hevc", "h265"] else 3
    latency = channel.get("latency", 9999)
    url = channel.get("url", "").lower()
    url_bonus = 0 if ".m3u8" in url else 1 if ".ts" in url else 2
    return (priority, codec_priority, latency, url_bonus)


def merge_channels_by_name(valid_channels: list, fixed_sources: dict = None,
                           stable_sources: dict = None) -> list:
    """
    valid_channels: 本轮测速通过的源
    fixed_sources: 数据库中的稳定源（含 is_fixed / auto_optimize）
    stable_sources: 上一轮所有稳定源（用于兜底，等同 fixed_sources）
    """
    groups = defaultdict(list)
    for ch in valid_channels:
        raw_name = ch["name"]
        if raw_name.startswith("CCTV-") and re.match(r'^CCTV-\d+', raw_name):
            norm = raw_name
        else:
            std = get_cctv_standard_name(raw_name)
            norm = std if std else normalize_channel_name(raw_name)
            if not norm or len(norm) < 2:
                norm = raw_name
        groups[norm].append(ch)

    logo = get_logo_matcher()
    merged = []

    for norm, ch_list in groups.items():
        ch_list.sort(key=get_channel_quality_score)
        top = ch_list[:config.max_sources_per_channel]
        primary = top[0] if top else None
        if not primary:
            continue
        merged.append({
            "name": norm,
            "urls": [c["url"] for c in top],
            "url": primary["url"],
            "latency": primary.get("latency", 9999),
            "video_codec": primary.get("video_codec", ""),
            "group_title": primary.get("group_title", ""),
            "id": primary.get("tvg_id", ""),
            "logo": logo.get_logo_url(norm) if not primary.get("tvg_logo") else primary.get("tvg_logo"),
            "is_fixed": primary.get("is_fixed", False),
            "source_state": "fresh",
        })

    # 固定源应用
    fs_map = fixed_sources or {}
    if fs_map:
        covered_names = {ch["name"] for ch in merged}
        for ch in merged:
            name = ch["name"]
            if name in fs_map:
                fs = fs_map[name]
                if not fs.get("auto_optimize", True):
                    ch["url"] = fs["url"]
                    ch["latency"] = fs.get("latency", 50)
                    ch["video_codec"] = fs.get("video_codec", "h264")
                    ch["is_fixed"] = True
                    if fs["url"] not in ch["urls"]:
                        ch["urls"] = [fs["url"]] + ch["urls"]
                else:
                    # 允许优化：若本轮存在更低延迟的候选
                    best = None
                    for candidate in ch_list:
                        if candidate.get("latency", 9999) < fs.get("latency", 9999):
                            best = candidate
                            break
                    if best:
                        ch["url"] = best["url"]
                        ch["latency"] = best.get("latency", 9999)
                        ch["video_codec"] = best.get("video_codec", "")
                        ch["is_fixed"] = True
                        ch["urls"] = [best["url"]] + [u for u in ch["urls"] if u != best["url"]]
                    else:
                        ch["url"] = fs["url"]
                        ch["latency"] = fs.get("latency", 50)
                        ch["video_codec"] = fs.get("video_codec", "h264")
                        ch["is_fixed"] = True
                        if fs["url"] not in ch["urls"]:
                            ch["urls"] = [fs["url"]] + ch["urls"]

    # === 缓存兜底：用稳定源补齐本轮缺失的频道 ===
    if fs_map:
        covered_names = {ch["name"] for ch in merged}
        added_from_cache = 0
        for name, fs in fs_map.items():
            if name in covered_names:
                continue
            if not fs.get("url"):
                continue
            if fs.get("status") not in (None, "active"):
                continue
            merged.append({
                "name": name,
                "urls": [fs["url"]],
                "url": fs["url"],
                "latency": fs.get("latency", 0),
                "video_codec": fs.get("video_codec", ""),
                "group_title": "",
                "id": "",
                "logo": logo.get_logo_url(name),
                "is_fixed": bool(fs.get("is_fixed", False)),
                "source_state": "from_cache",
            })
            covered_names.add(name)
            added_from_cache += 1
        if added_from_cache:
            logger.info(f"📦 缓存兜底：从稳定源补充 {added_from_cache} 个频道")

    for ch in merged:
        if isinstance(ch.get("url"), list):
            ch["url"] = ch["url"][0] if ch["url"] else ""
        if not isinstance(ch.get("urls"), list):
            ch["urls"] = [ch["url"]] if ch["url"] else []

    fixed_count = sum(1 for ch in merged if ch.get("is_fixed"))
    cached_count = sum(1 for ch in merged if ch.get("source_state") == "from_cache")
    logger.info(f"📊 合并完成: {len(merged)} 个频道（固定 {fixed_count}，缓存兜底 {cached_count}）")
    return merged
