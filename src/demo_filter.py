# src/demo_filter.py
import re
from pathlib import Path
from typing import List, Tuple
from src.config import DEMO_FILE, OUTPUT_DIR, DEMO_MATCH_MODE
from src.classifier import PROVINCES, classify_channel, classify_and_filter
from src.logger import logger

try:
    from pypinyin import lazy_pinyin
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False
    logger.warning("⚠️ pypinyin 未安装，拼音匹配功能将不可用。建议安装: pip install pypinyin")


def parse_demo_order_with_categories(demo_file: Path = DEMO_FILE) -> List[Tuple[str, str]]:
    if not demo_file.exists():
        logger.warning(f"⚠️ Demo 文件不存在: {demo_file}")
        return []
    order = []
    current_category = None
    with open(demo_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.endswith(",#genre#") or line.endswith(", #genre#"):
                current_category = line.replace(",#genre#", "").replace(", #genre#", "").strip()
                continue
            if line.startswith('#'):
                continue
            if current_category is not None:
                order.append((current_category, line))
            else:
                order.append(("其他", line))
    logger.info(f"📋 从 demo.txt 解析到 {len(order)} 个有序频道")
    return order


def to_pinyin(text: str) -> str:
    if not HAS_PYPINYIN:
        return text.lower()
    try:
        return ''.join(lazy_pinyin(text)).lower()
    except:
        return text.lower()


def match_channel_name(channel_name: str, demo_name: str) -> bool:
    """宽松匹配：包含、拼音、去特殊字符、央视频道数字"""
    if DEMO_MATCH_MODE == "exact":
        return channel_name == demo_name

    cn_lower = channel_name.lower()
    dn_lower = demo_name.lower()

    # 央视频道数字匹配（含 4K/8K）
    cctv_pattern = re.compile(r'cctv[-\s]*(\d+(?:k)?)', re.IGNORECASE)
    m1 = cctv_pattern.search(channel_name)
    m2 = cctv_pattern.search(demo_name)
    if m1 and m2 and m1.group(1).lower() == m2.group(1).lower():
        num = m1.group(1).lower()
        # 5 和 5+ 区分
        if num == "5":
            if ('+' in dn_lower or '5plus' in dn_lower) != ('+' in cn_lower or '5plus' in cn_lower):
                return False
        # 4K/8K 直接匹配
        if num in ["4k", "8k"]:
            return True
        # 数字 1-17，检测区域关键词（欧洲/美洲）用于区分 CCTV-4 变体
        if num.isdigit() and 1 <= int(num) <= 17:
            area_keywords = {"欧洲": ["欧洲", "europe"], "美洲": ["美洲", "america", "americas"], "中文国际": ["中文国际"]}
            for kw, variants in area_keywords.items():
                if kw in dn_lower:
                    if not any(v in cn_lower for v in variants):
                        return False
            return True

    # 包含匹配
    if dn_lower in cn_lower or cn_lower in dn_lower:
        return True

    # 拼音
    if HAS_PYPINYIN:
        if to_pinyin(demo_name) in to_pinyin(channel_name) or to_pinyin(channel_name) in to_pinyin(demo_name):
            return True

    # 去特殊字符
    def clean(s):
        return re.sub(r'[^a-zA-Z\u4e00-\u9fa5]', '', s).lower()
    if clean(demo_name) in clean(channel_name) or clean(channel_name) in clean(demo_name):
        return True

    return False


def detect_province(channel_name: str) -> str:
    name = channel_name
    # 日本
    jp_keywords = ["NHK", "Japan", "Tokyo", "Fuji", "TBS", "TV Asahi", "NTV", "日本"]
    for kw in jp_keywords:
        if kw in name:
            return "日本"
    # 港澳台
    hmtj_keywords = ["香港", "澳门", "台湾", "港", "澳", "台"]
    for kw in hmtj_keywords:
        if kw in name:
            return "港澳台"
    # 省份
    for prov in PROVINCES:
        if prov in name:
            return prov
    if "京" in name: return "北京"
    if "沪" in name: return "上海"
    if "津" in name: return "天津"
    if "渝" in name: return "重庆"

    # 城市映射（简化版，可扩展）
    city_map = {
        "广州": "广东", "深圳": "广东", "佛山": "广东", "东莞": "广东",
        "杭州": "浙江", "宁波": "浙江", "温州": "浙江",
        "南京": "江苏", "苏州": "江苏", "无锡": "江苏",
        "济南": "山东", "青岛": "山东",
        "福州": "福建", "厦门": "福建",
        "成都": "四川", "绵阳": "四川",
        "武汉": "湖北", "宜昌": "湖北",
        "长沙": "湖南", "株洲": "湖南",
        "郑州": "河南", "洛阳": "河南",
        "石家庄": "河北", "唐山": "河北",
        "合肥": "安徽", "芜湖": "安徽",
        "南昌": "江西", "九江": "江西",
        "太原": "山西", "大同": "山西",
        "沈阳": "辽宁", "大连": "辽宁",
        "长春": "吉林", "吉林": "吉林",
        "哈尔滨": "黑龙江", "齐齐哈尔": "黑龙江",
        "西安": "陕西", "宝鸡": "陕西",
        "兰州": "甘肃", "天水": "甘肃",
        "南宁": "广西", "柳州": "广西",
        "昆明": "云南", "大理": "云南",
        "贵阳": "贵州", "遵义": "贵州",
        "乌鲁木齐": "新疆", "克拉玛依": "新疆",
        "呼和浩特": "内蒙古", "包头": "内蒙古",
        "拉萨": "西藏",
        "西宁": "青海",
        "银川": "宁夏",
        "海口": "海南", "三亚": "海南",
    }
    for city, prov in city_map.items():
        if city in name:
            return prov
    return None


def get_demo_category_for_province(province: str, demo_order: List[Tuple[str, str]]) -> str:
    if province == "港澳台":
        return "🌊港·澳·台"
    if province == "日本":
        for cat, _ in demo_order:
            if cat == "日本频道" or cat == "日本":
                return cat
        return "日本频道"
    candidates = [
        f"☘️{province}频道",
        f"{province}频道",
        f"☘️{province}",
        f"{province}"
    ]
    for cat, _ in demo_order:
        for cand in candidates:
            if cat.startswith(cand) or cat == cand:
                return cat
    return f"☘️{province}频道"


def filter_and_order_by_demo(channels: list) -> tuple:
    demo_order = parse_demo_order_with_categories()
    if not demo_order:
        classified = classify_and_filter(channels)
        matched = []
        for cat in ["央视", "卫视", "地方", "港澳台"]:
            for ch in classified.get(cat, []):
                ch_copy = ch.copy()
                ch_copy["demo_category"] = cat
                ch_copy["demo_name"] = ch["name"]
                matched.append(ch_copy)
        logger.info(f"📊 demo.txt 为空，按分类输出 {len(matched)} 个频道")
        return matched, []

    name_to_channel = {ch["name"]: ch for ch in channels}
    matched = []
    unmatched = list(channels)
    matched_names = set()

    # 第一遍：匹配 demo
    for category, demo_name in demo_order:
        if demo_name in name_to_channel:
            ch = name_to_channel[demo_name].copy()
            ch["demo_category"] = category
            ch["demo_name"] = demo_name
            if ch["name"] not in matched_names:
                matched.append(ch)
                matched_names.add(ch["name"])
                unmatched = [c for c in unmatched if c["name"] != ch["name"]]
                continue

        for i, ch in enumerate(unmatched[:]):
            if ch["name"] in matched_names:
                continue
            if match_channel_name(ch["name"], demo_name):
                ch_copy = ch.copy()
                ch_copy["demo_category"] = category
                ch_copy["demo_name"] = demo_name
                matched.append(ch_copy)
                matched_names.add(ch["name"])
                unmatched.pop(i)
                logger.debug(f"🎯 匹配: {ch['name']} -> {category}/{demo_name}")
                break

    # 第二遍：所有未匹配的频道，按省份归类，否则归入“其他”
    for ch in unmatched:
        if ch["name"] in matched_names:
            continue
        province = detect_province(ch["name"])
        if province:
            cat = get_demo_category_for_province(province, demo_order)
        else:
            cat = "其他"
        ch_copy = ch.copy()
        ch_copy["demo_category"] = cat
        ch_copy["demo_name"] = ch["name"]
        matched.append(ch_copy)
        matched_names.add(ch["name"])
        if province:
            logger.info(f"🌏 自动追加: {ch['name']} -> {cat}")
        else:
            logger.info(f"📌 未分类频道追加到 '其他': {ch['name']}")

    logger.info(f"🎯 Demo 筛选：原始 {len(channels)} -> 匹配/分类后 {len(matched)} 个频道")
    return matched, []


def write_shai_file(unmatched_channels: list, matched_count: int, total_raw: int):
    # 此函数保留但不使用（因为不再有未匹配频道）
    shai_path = OUTPUT_DIR / "shai.txt"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(shai_path, "w", encoding="utf-8") as f:
        f.write("# Demo筛选丢弃的频道（本系统不再丢弃）\n")
        f.write(f"# 原始频道总数: {total_raw}\n")
        f.write(f"# 匹配/分类后总数: {matched_count}\n")
