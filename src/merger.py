# src/merger.py
# 频道合并模块，H.264优先 + 延迟排序 + 固定源保护（支持多地址自动择优）

import re
import copy
from collections import defaultdict
from src.config import MAX_SOURCES_PER_CHANNEL
from src.logo_matcher import get_logo_matcher
from src.logger import logger
from src.fixed_sources import CCTV_FIXED_SOURCES, ENABLE_FIXED_SOURCES
from src.constants import CCTV_ORDER  # 用于排序


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
    name_clean = re.sub(r'\s*\([^)]*\)', '', name)
    name_lower = name_clean.lower()
    
    if is_cctv5plus(name_clean):
        return "CCTV-5+"
    if is_cctv5(name_clean):
        return "CCTV-5"
    
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
    """获取频道质量评分（固定源优先级最高）"""
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
    合并频道，支持固定源多地址自动择优。
    对每个频道，优先从 valid_channels 中选取延迟最低的源作为主源，
    同时保留所有备源（包括固定源配置的多个地址和其他有效源）。
    """
    # 1. 按标准化名称分组
    groups = defaultdict(list)
    for ch in valid_channels:
        raw_name = ch["name"]
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
    
    # 2. 处理每个频道组
    for norm_name, ch_list in groups.items():
        # 按质量评分排序（固定源优先，然后按延迟、编码）
        ch_list.sort(key=get_channel_quality_score)
        
        # 取前 MAX_SOURCES_PER_CHANNEL 个作为备源
        top = ch_list[:MAX_SOURCES_PER_CHANNEL]
        primary = top[0] if top else None
        
        if not primary:
            logger.warning(f"⚠️ {norm_name} 没有有效源")
            continue
        
        # 构建频道数据
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
    
    # 3. 处理固定源（确保所有固定源都存在，并自动择优）
    if ENABLE_FIXED_SOURCES:
        merged_names = {ch["name"] for ch in merged}
        
        for fixed_name, fixed_urls in CCTV_FIXED_SOURCES.items():
            if isinstance(fixed_urls, str):
                fixed_urls = [fixed_urls]
            fixed_urls = [u for u in fixed_urls if u and u.strip()]
            if not fixed_urls:
                continue
            
            # 查找该频道在 valid_channels 中的所有有效源
            all_sources_for_fixed = []
            for vch in valid_channels:
                if vch["name"] == fixed_name or get_cctv_standard_name(vch["name"]) == fixed_name:
                    all_sources_for_fixed.append(vch)
            
            # 按延迟排序
            all_sources_for_fixed.sort(key=lambda x: x.get("latency", 9999))
            
            if fixed_name in merged_names:
                # 已有频道，更新其源列表
                for ch in merged:
                    if ch["name"] == fixed_name:
                        # 收集所有候选 URL（包括配置的固定源和有效源）
                        candidate_urls = fixed_urls + [s["url"] for s in all_sources_for_fixed if s["url"] not in fixed_urls]
                        # 去重
                        unique_urls = []
                        seen = set()
                        for u in candidate_urls:
                            if u not in seen:
                                seen.add(u)
                                unique_urls.append(u)
                        # 取前 MAX_SOURCES_PER_CHANNEL 个（先按有效源延迟排序）
                        # 构建带有延迟的候选列表
                        candidates_with_lat = []
                        for u in unique_urls:
                            # 查找该 URL 在 valid_channels 中的延迟
                            lat = 9999
                            for s in all_sources_for_fixed:
                                if s["url"] == u:
                                    lat = s.get("latency", 9999)
                                    break
                            candidates_with_lat.append((u, lat))
                        # 按延迟排序，取前 N 个
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
                # 频道不在 merged 中，新增
                if all_sources_for_fixed:
                    best = all_sources_for_fixed[0]
                    # 合并固定源和有效源 URL
                    all_urls = list(dict.fromkeys(fixed_urls + [s["url"] for s in all_sources_for_fixed]))
                    # 按延迟排序
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
                    # 没有任何有效源，仅使用固定源第一个
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
    
    # ========== 最后确保每个频道的 url 字段为字符串 ==========
    for ch in merged:
        if isinstance(ch.get("url"), list):
            ch["url"] = ch["url"][0] if ch["url"] else ""
        if not isinstance(ch.get("urls"), list):
            ch["urls"] = [ch["url"]] if ch["url"] else []
    
    fixed_count = sum(1 for ch in merged if ch.get("is_fixed"))
    if fixed_count > 0:
        logger.info(f"📌 已使用 {fixed_count} 个固定优质源（含自动择优）")
    
    cctv_channels = [ch for ch in merged if ch["name"].startswith("CCTV-")]
    logger.info(f"📊 合并完成: 共 {len(merged)} 个频道，其中央视 {len(cctv_channels)} 个")
    
    return merged
