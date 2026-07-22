import re
from src.settings import settings
from src.constants import CCTV_ORDER, PROVINCES, HK_MACAU_TAIWAN_KEYWORDS

# 预编译正则
_CCTV_PATTERN = re.compile(r'(?:cctv|央视|中央电视|中央-|中央台|cntv)', re.IGNORECASE)
_HK_PATTERN = re.compile(r'|'.join(re.escape(kw) for kw in HK_MACAU_TAIWAN_KEYWORDS), re.IGNORECASE)
_PROVINCE_PATTERN = re.compile(r'|'.join(re.escape(prov) for prov in PROVINCES))

def classify_channel(channel: dict) -> str:
    name = channel.get("name", "")
    group = channel.get("group_title", "")
    name_lower = name.lower()

    if _CCTV_PATTERN.search(name_lower):
        return "央视"
    if _HK_PATTERN.search(name_lower) or _HK_PATTERN.search(group.lower()):
        return "港澳台"
    if "卫视" in name:
        return "卫视"
    if _PROVINCE_PATTERN.search(name):
        return "地方"
    if any(kw in name for kw in ["电视台", "综合频道", "公共频道", "生活频道", "新闻综合"]):
        return "地方"
    return "其他"

def classify_and_filter(channels: list) -> dict:
    result = {"央视": [], "卫视": [], "地方": [], "港澳台": []}
    for ch in channels:
        cat = classify_channel(ch)
        if cat in result:
            result[cat].append(ch)
    return result
