# src/classifier.py
import re
from src.constants import CCTV_ORDER, PROVINCES, HK_MACAU_TAIWAN_KEYWORDS

_CCTV_PATTERN = re.compile(r'(?:cctv|央视|中央电视|中央-|中央台|cntv)', re.IGNORECASE)
_HK_MACAU_PATTERN = re.compile(r'|'.join(re.escape(kw) for kw in HK_MACAU_TAIWAN_KEYWORDS), re.IGNORECASE)
_PROVINCE_PATTERN = re.compile(r'|'.join(re.escape(prov) for prov in PROVINCES))


def classify_channel(channel: dict) -> str:
    name = channel.get("name", "")
    name_lower = name.lower()
    group = channel.get("group_title", "").lower()

    if _CCTV_PATTERN.search(name_lower):
        return "央视"

    if _HK_MACAU_PATTERN.search(name_lower) or _HK_MACAU_PATTERN.search(group):
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
    group = channel.get("group_title", "")
    for prov in PROVINCES:
        if prov in name:
            return f"{prov}频道"
    for prov in PROVINCES:
        if prov in group:
            return f"{prov}频道"
    return "地方频道"


def classify_and_filter(channels: list) -> dict:
    result = {"央视": [], "卫视": [], "地方": [], "港澳台": []}
    other_count = 0
    for ch in channels:
        cat = classify_channel(ch)
        if cat in result:
            if cat == "地方":
                ch["subcategory"] = extract_subcategory(ch)
            result[cat].append(ch)
        else:
            other_count += 1

    # 央视排序
    if result["央视"]:
        def ctv_key(ch):
            name = ch.get("name", "")
            if name in ["CCTV-5+", "CCTV5+"]:
                return 5
            match = re.search(r'CCTV[-\s]*(\d+)', name, re.IGNORECASE)
            if match:
                num = int(match.group(1))
                if 1 <= num <= 17:
                    return num - 1
            for idx, std in enumerate(CCTV_ORDER):
                if name == std or name.startswith(std):
                    return idx
            return len(CCTV_ORDER)
        result["央视"].sort(key=ctv_key)

    for cat in ["卫视", "地方", "港澳台"]:
        if result[cat]:
            result[cat].sort(key=lambda x: x.get("name", ""))

    from src.logger import logger
    logger.info("📊 分类统计（央视/卫视/地方/港澳台）：")
    for cat, lst in result.items():
        if lst:
            logger.info(f"  {cat}: {len(lst)} 个频道")
    logger.info(f"  （其他分类被过滤: {other_count} 个频道）")
    return result
