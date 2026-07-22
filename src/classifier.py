# src/classifier.py
import re
from src.constants import PROVINCES, HK_MACAU_TAIWAN_KEYWORDS, CCTV_ORDER

_CCTV_PATTERN = re.compile(r'(?:cctv|央视|中央电视|中央-|中央台|cntv)', re.IGNORECASE)
_HKMT_PATTERN = re.compile('|'.join(re.escape(kw) for kw in HK_MACAU_TAIWAN_KEYWORDS), re.IGNORECASE)
_PROVINCE_PATTERN = re.compile('|'.join(re.escape(p) for p in PROVINCES))

def classify_channel(channel: dict) -> str:
    name = channel.get("name", "")
    name_lower = name.lower()
    group = channel.get("group_title", "").lower()
    if _CCTV_PATTERN.search(name_lower):
        return "央视"
    if _HKMT_PATTERN.search(name_lower) or _HKMT_PATTERN.search(group):
        return "港澳台"
    if "卫视" in name:
        return "卫视"
    if _PROVINCE_PATTERN.search(name):
        return "地方"
    if any(kw in name for kw in ["电视台", "综合频道", "公共频道", "生活频道", "新闻综合"]):
        return "地方"
    return "其他"

def extract_subcategory(channel: dict) -> str:
    name = channel.get("name", "")
    for prov in PROVINCES:
        if prov in name:
            return f"{prov}频道"
    return "地方频道"
