import re
from src.settings import settings
from src.constants import CCTV_ORDER, PROVINCES, HK_MACAU_KEYWORDS

CCTV_PAT = re.compile(r'(cctv|央视|中央电视|cntv)', re.I)
HK_PAT = re.compile('|'.join(re.escape(k) for k in HK_MACAU_KEYWORDS), re.I)
PROV_PAT = re.compile('|'.join(re.escape(p) for p in PROVINCES))

def classify(channel: dict) -> str:
    name = channel.get('name', '')
    group = channel.get('group_title', '')
    text = f"{name} {group}".lower()
    if CCTV_PAT.search(text):
        return "央视"
    if HK_PAT.search(text):
        return "港澳台"
    if "卫视" in text:
        return "卫视"
    if PROV_PAT.search(text):
        return "地方"
    if any(k in text for k in ["电视台", "综合频道", "公共频道", "生活频道"]):
        return "地方"
    return "其他"

def extract_subcategory(channel: dict) -> str:
    name = channel.get('name', '')
    group = channel.get('group_title', '')
    for prov in PROVINCES:
        if prov in name or prov in group:
            return f"{prov}频道"
    return "地方频道"

def classify_and_group(channels: list) -> dict:
    groups = {"央视": [], "卫视": [], "地方": [], "港澳台": []}
    for ch in channels:
        cat = classify(ch)
        if cat in groups:
            if cat == "地方":
                ch["subcategory"] = extract_subcategory(ch)
            groups[cat].append(ch)
    return groups
