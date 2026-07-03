# src/hmtj_source.py
"""处理 http://1080p.19860519.de5.net/ 源的采集与分类（JSON API 版）"""

import aiohttp
import json
import re
from typing import List, Dict, Optional
from src.logger import logger


# 分类映射：源中的 group_xxx 映射到 demo 分类
CATEGORY_MAP = {
    "group_央视": "央视",
    "group_卫视": "卫视",
    "group_地方": "地方",
}

# 体育赛事关键词（用于从频道名中识别体育赛事）
SPORTS_KEYWORDS = [
    "体育", "赛事", "竞技", "比赛", "运动",
    "nba", "英超", "中超", "世界杯", "奥运",
    "足球", "篮球", "排球", "乒乓球", "羽毛球",
    "网球", "高尔夫", "台球", "斯诺克", "F1"
]


async def fetch_hmtj_source() -> List[Dict]:
    """
    拉取新源的 JSON 数据并解析为频道列表
    返回格式与现有 parser 兼容的频道字典列表
    """
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
                    # 跳过引流/广告条目
                    if item.get("vod_id") == "live_promo":
                        continue
                    
                    # 解析播放地址
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
    """
    从 "主线路$http://xxx.xxx.xxx.xxx:port/xxxxx" 格式中提取真实 URL
    如果有多个线路，取第一个
    """
    if not play_url_raw:
        return None
    # 格式: "主线路$http://..." 或 "备用线路$http://..."
    parts = play_url_raw.split("$")
    if len(parts) >= 2:
        # 取第一个非空 URL（通常第一个是主线路）
        for part in parts[1:]:
            if part.startswith(("http://", "https://")):
                return part
    return None


def classify_hmtj_channel(channel: Dict, category_map: Dict) -> str:
    """
    对频道进行分类
    优先使用源自带的 group_title 映射，其次根据频道名关键词判断
    """
    group_title = channel.get("group_title", "")
    
    # 1. 优先使用源自带的分类
    for src_cat, demo_cat in category_map.items():
        # 源中 group_title 可能是 "央视" 或 "group_央视"
        if group_title == src_cat or group_title == demo_cat:
            return demo_cat
    
    # 2. 根据频道名判断是否为体育赛事
    name = channel.get("name", "")
    name_lower = name.lower()
    for kw in SPORTS_KEYWORDS:
        if kw in name_lower:
            return "体育赛事"
    
    # 3. 如果都不匹配，返回 None（不采集）
    return None


async def integrate_hmtj_source() -> Dict[str, List[Dict]]:
    """
    主函数：拉取新源、分类、返回分类字典
    """
    channels = await fetch_hmtj_source()
    if not channels:
        return {}
    
    classified = {
        "央视": [],
        "卫视": [],
        "地方": [],
        "体育赛事": [],
    }
    unknown = []
    
    for ch in channels:
        cat = classify_hmtj_channel(ch, CATEGORY_MAP)
        if cat and cat in classified:
            ch["urls"] = [ch.get("url", "")]
            ch["demo_category"] = cat
            ch["group_title"] = cat
            classified[cat].append(ch)
        else:
            unknown.append(ch)
    
    logger.info(f"📊 新源分类统计: 央视 {len(classified['央视'])}，卫视 {len(classified['卫视'])}，地方 {len(classified['地方'])}，体育赛事 {len(classified['体育赛事'])}，未分类 {len(unknown)}")
    if unknown:
        logger.debug(f"未分类频道示例: {[ch['name'] for ch in unknown[:5]]}")
    
    return {k: v for k, v in classified.items() if v}
