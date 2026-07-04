# src/hmtj_source.py
"""处理 http://1080p.19860519.de5.net/ 源的采集与分类（JSON API 版）"""

import aiohttp
import json
import re
from typing import List, Dict, Optional
from src.logger import logger


CATEGORY_MAP = {
    "group_央视": "央视",
    "group_卫视": "卫视",
    "group_地方": "地方",
}

async def fetch_hmtj_source() -> List[Dict]:
    """拉取 JSON 数据并解析为频道列表"""
    source_url = "http://1080p.19860519.de5.net/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Referer": "http://1080p.19860519.de5.net/",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(source_url, timeout=15, headers=headers) as resp:
                if resp.status != 200:
                    logger.warning(f"⚠️ 新源返回 HTTP {resp.status}")
                    return []
                content = await resp.text()
                data = json.loads(content)

                channels = []
                for item in data.get("list", []):
                    if item.get("vod_id") == "live_promo":
                        continue
                    play_url_raw = item.get("vod_play_url", "")
                    url = extract_play_url(play_url_raw)
                    if not url:
                        continue
                    channels.append({
                        "name": item.get("vod_name", ""),
                        "url": url,
                        "group_title": item.get("vod_remarks", ""),
                        "tvg_id": "",
                        "tvg_logo": item.get("vod_pic", ""),
                        "vod_id": item.get("vod_id", ""),
                    })

                logger.info(f"✅ 从新源解析到 {len(channels)} 个频道")
                return channels
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON 解析失败: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ 拉取新源失败: {e}")
        return []


def extract_play_url(play_url_raw: str) -> Optional[str]:
    if not play_url_raw:
        return None
    parts = play_url_raw.split("$")
    if len(parts) >= 2:
        for part in parts[1:]:
            if part.startswith(("http://", "https://")):
                return part
    return None

async def integrate_hmtj_source() -> Dict[str, List[Dict]]:
    """拉取并分类，返回分类字典（值均为频道列表）"""
    channels = await fetch_hmtj_source()
    if not channels:
        return {}

    classified = {
        "央视": [],
        "卫视": [],
        "地方": [],
    }
    unknown = []

    for ch in channels:
        cat = classify_hmtj_channel(ch)
        if cat and cat in classified:
            ch["urls"] = [ch.get("url", "")]
            ch["demo_category"] = cat
            ch["group_title"] = cat
            classified[cat].append(ch)
        else:
            unknown.append(ch)

    # 记录统计信息（仅日志）
    for cat, channels in classified.items():
        logger.info(f"📊 新源分类 {cat}: {len(channels)} 个频道")
    if unknown:
        logger.debug(f"未分类频道示例: {[ch['name'] for ch in unknown[:5]]}")

    # 返回只包含非空分类的字典
    return {k: v for k, v in classified.items() if v}
