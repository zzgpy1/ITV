import re
from pathlib import Path
from typing import List, Tuple
from src.settings import settings
from src.classifier import PROVINCES
from src.logger import logger

try:
    from pypinyin import lazy_pinyin
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False

def parse_demo_order() -> List[Tuple[str, str]]:
    if not settings.demo_file.exists():
        return []
    order = []
    cur = "其他"
    with open(settings.demo_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.endswith(",#genre#") or line.endswith(", #genre#"):
                cur = line.replace(",#genre#", "").replace(", #genre#", "").strip()
                continue
            order.append((cur, line))
    return order

def to_pinyin(text: str) -> str:
    if not HAS_PYPINYIN:
        return text.lower()
    try:
        return ''.join(lazy_pinyin(text)).lower()
    except:
        return text.lower()

def match_channel(channel_name: str, demo_name: str) -> bool:
    if settings.demo_match_mode == "exact":
        return channel_name == demo_name
    cn_l = channel_name.lower()
    dn_l = demo_name.lower()
    # 央视数字匹配
    m1 = re.search(r'cctv[-\s]*(\d+(?:k)?)', cn_l, re.I)
    m2 = re.search(r'cctv[-\s]*(\d+(?:k)?)', dn_l, re.I)
    if m1 and m2 and m1.group(1).lower() == m2.group(1).lower():
        return True
    if dn_l in cn_l or cn_l in dn_l:
        return True
    if HAS_PYPINYIN:
        if to_pinyin(demo_name) in to_pinyin(channel_name) or to_pinyin(channel_name) in to_pinyin(demo_name):
            return True
    # 去特殊字符
    def clean(s): return re.sub(r'[^a-zA-Z\u4e00-\u9fa5]', '', s).lower()
    if clean(demo_name) in clean(channel_name) or clean(channel_name) in clean(demo_name):
        return True
    return False

def detect_province(name: str) -> str:
    for prov in PROVINCES:
        if re.search(rf'(?<![a-zA-Z\u4e00-\u9fa5]){prov}(?![a-zA-Z\u4e00-\u9fa5])', name):
            return prov
    # 城市映射（简化）
    city_map = {"北京":"北京","上海":"上海","广州":"广东","深圳":"广东","杭州":"浙江","南京":"江苏","武汉":"湖北","成都":"四川"}
    for city, prov in city_map.items():
        if city in name:
            return prov
    return None

def get_demo_category_for_province(prov: str, demo_order: List[Tuple[str,str]]) -> str:
    candidates = [f"☘️{prov}频道", f"{prov}频道", f"☘️{prov}", prov]
    for cat, _ in demo_order:
        for cand in candidates:
            if cat.startswith(cand) or cat == cand:
                return cat
    return f"☘️{prov}频道"

def filter_and_order_by_demo(channels: list) -> list:
    demo_order = parse_demo_order()
    if not demo_order:
        return channels  # 不筛选
    name_to_ch = {ch["name"]: ch for ch in channels}
    matched = []
    matched_names = set()
    for cat, demo_name in demo_order:
        if demo_name in name_to_ch and demo_name not in matched_names:
            ch = name_to_ch[demo_name].copy()
            ch["demo_category"] = cat
            matched.append(ch)
            matched_names.add(demo_name)
            continue
        # 模糊匹配
        for ch in channels:
            if ch["name"] in matched_names:
                continue
            if match_channel(ch["name"], demo_name):
                ch_copy = ch.copy()
                ch_copy["demo_category"] = cat
                matched.append(ch_copy)
                matched_names.add(ch["name"])
                break
    # 未匹配的按省份归类
    for ch in channels:
        if ch["name"] in matched_names:
            continue
        prov = detect_province(ch["name"])
        if prov:
            cat = get_demo_category_for_province(prov, demo_order)
        else:
            cat = "其他"
        ch_copy = ch.copy()
        ch_copy["demo_category"] = cat
        matched.append(ch_copy)
        matched_names.add(ch["name"])
    return matched
