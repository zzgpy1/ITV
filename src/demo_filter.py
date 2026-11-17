# src/demo_filter.py
import re
from pathlib import Path
from typing import List, Tuple, Dict, Set
from src.config_loader import config
from src.classifier import PROVINCES, classify_and_filter
from src.logger import logger
from src.city_province import get_province_by_area, get_city_province_map

try:
    from pypinyin import lazy_pinyin
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False
    logger.warning("⚠️ pypinyin未安装，拼音匹配功能不可用")


# ========== 省份简称 -> 完整省份名 ==========
PROVINCE_ALIASES: Dict[str, str] = {
    "粤": "广东", "浙": "浙江", "苏": "江苏", "鲁": "山东", "闽": "福建",
    "川": "四川", "蜀": "四川", "鄂": "湖北", "湘": "湖南", "豫": "河南",
    "冀": "河北", "皖": "安徽", "赣": "江西", "晋": "山西", "辽": "辽宁",
    "吉": "吉林", "黑": "黑龙江", "陕": "陕西", "秦": "陕西", "甘": "甘肃",
    "陇": "甘肃", "云": "云南", "滇": "云南", "贵": "贵州", "黔": "贵州",
    "桂": "广西", "琼": "海南", "蒙": "内蒙古", "新": "新疆", "藏": "西藏",
    "青": "青海", "宁": "宁夏",
}


def parse_demo_order_with_categories(demo_file: Path = None) -> List[Tuple[str, str]]:
    """解析 demo.txt，返回 [(分类, 频道名), ...] 的有序列表"""
    if demo_file is None:
        demo_file = config.demo_file
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
    """转换为拼音（小写），用于模糊匹配"""
    if not HAS_PYPINYIN:
        return text.lower()
    try:
        return ''.join(lazy_pinyin(text)).lower()
    except Exception:
        return text.lower()


def match_channel_name(channel_name: str, demo_name: str) -> bool:
    """
    频道名与 demo 名匹配：
    1. 央视频道数字匹配（含 5+/4K/8K/欧洲/美洲 区分）
    2. 双向包含匹配
    3. 拼音匹配
    4. 去特殊字符匹配
    """
    if not channel_name or not demo_name:
        return False
    if config.demo_match_mode == "exact":
        return channel_name == demo_name

    cn_lower = channel_name.lower()
    dn_lower = demo_name.lower()

    # 央视频道数字匹配
    cctv_pattern = re.compile(r'cctv[-\s]*(\d+(?:k)?)', re.IGNORECASE)
    m1 = cctv_pattern.search(channel_name)
    m2 = cctv_pattern.search(demo_name)
    if m1 and m2 and m1.group(1).lower() == m2.group(1).lower():
        num = m1.group(1).lower()
        # CCTV-5 与 CCTV-5+ 区分
        if num == "5":
            if ('+' in dn_lower or '5plus' in dn_lower) != ('+' in cn_lower or '5plus' in cn_lower):
                return False
        if num in ["4k", "8k"]:
            return True
        if num.isdigit() and 1 <= int(num) <= 17:
            area_keywords = {
                "欧洲": ["欧洲", "europe"],
                "美洲": ["美洲", "america", "americas"],
                "中文国际": ["中文国际"],
            }
            for kw, variants in area_keywords.items():
                if kw in dn_lower:
                    if not any(v in cn_lower for v in variants):
                        return False
            return True

    # 双向包含匹配
    if dn_lower in cn_lower or cn_lower in dn_lower:
        return True

    # 拼音匹配
    if HAS_PYPINYIN:
        cn_py = to_pinyin(channel_name)
        dn_py = to_pinyin(demo_name)
        if dn_py and cn_py and (dn_py in cn_py or cn_py in dn_py):
            return True

    # 去特殊字符匹配
    def clean(s):
        return re.sub(r'[^a-zA-Z\u4e00-\u9fa5]', '', s).lower()

    c_cn = clean(channel_name)
    c_dn = clean(demo_name)
    if c_cn and c_dn and (c_dn in c_cn or c_cn in c_dn):
        return True

    return False


def detect_province(channel_name: str) -> str:
    """
    从频道名提取省份。优先级：
    1. 港澳台关键词
    2. 完整省份名
    3. 县市/区映射（来自 src.city_province 模块，含外部扩展）
    4. 省份简称（独立字符才匹配，避免误伤）

    返回值：
    - 省份名（如 "浙江"、"重庆"）
    - "港澳台"（特殊）
    - None（无法识别）
    """
    name = channel_name.strip()
    if not name:
        return None

    # 1. 港澳台关键词
    for kw in ["香港", "澳门", "台湾", "港台", "TVB", "翡翠", "明珠", "凤凰", "澳视"]:
        if kw in name:
            return "港澳台"

    # 2. 完整省份名
    for prov in PROVINCES:
        if prov in name:
            return prov

    # 3. 县市/区映射（调用 city_province 模块）
    prov = get_province_by_area(name)
    if prov:
        return prov

    # 4. 省份简称（必须独立字符，防止 "吉" 误匹配 "吉木萨尔" 之类）
    for alias, prov in PROVINCE_ALIASES.items():
        if re.search(rf'(?<![a-zA-Z\u4e00-\u9fa5]){alias}(?![a-zA-Z\u4e00-\u9fa5])', name):
            return prov

    return None


def get_demo_category_for_province(province: str, demo_order: List[Tuple[str, str]]) -> str:
    """根据省份找到 demo.txt 中对应的分类名（如 "☘️浙江频道"）"""
    if province == "港澳台":
        return "🌊港·澳·台"

    candidates = [
        f"☘️{province}频道",
        f"{province}频道",
        f"☘️{province}",
        f"{province}",
    ]
    for cat, _ in demo_order:
        for cand in candidates:
            if cat.startswith(cand) or cat == cand:
                return cat

    # 未在 demo 中出现，回退到默认命名
    return f"☘️{province}频道"


def filter_and_order_by_demo(channels: list) -> tuple:
    """
    按 demo.txt 顺序过滤/排序：
    第一轮：精确匹配（channel name == demo name）
    第二轮：模糊匹配（match_channel_name，允许多个采集频道匹配同一 demo 项）
    第三轮：未匹配频道按省份自动归类

    返回：(matched_channels, [])
    """
    demo_order = parse_demo_order_with_categories()
    if not demo_order:
        # demo 为空时按 classify_and_filter 分类
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
    matched: List[Dict] = []
    matched_channel_names: Set[str] = set()
    unmatched: List[Dict] = list(channels)

    # ===== 第一轮：精确匹配 =====
    for category, demo_name in demo_order:
        key = demo_name.strip()
        if not key:
            continue
        if key in name_to_channel:
            ch = name_to_channel[key]
            if ch["name"] not in matched_channel_names:
                ch_copy = ch.copy()
                ch_copy["demo_category"] = category
                ch_copy["demo_name"] = key
                matched.append(ch_copy)
                matched_channel_names.add(ch["name"])
                unmatched = [c for c in unmatched if c["name"] != ch["name"]]

    # ===== 第二轮：模糊匹配 =====
    # 注意：这一轮不跳过已匹配的 demo_name，允许同一 demo 项匹配多个采集频道
    for category, demo_name in demo_order:
        key = demo_name.strip()
        if not key:
            continue
        for ch in list(unmatched):
            if ch["name"] in matched_channel_names:
                continue
            if match_channel_name(ch["name"], key):
                ch_copy = ch.copy()
                ch_copy["demo_category"] = category
                ch_copy["demo_name"] = key
                matched.append(ch_copy)
                matched_channel_names.add(ch["name"])
                unmatched.remove(ch)
                logger.debug(f"🎯 模糊匹配: {ch['name']} -> {category}/{key}")

    # ===== 第三轮：未匹配频道按省份自动归类 =====
    for ch in list(unmatched):
        if ch["name"] in matched_channel_names:
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
        matched_channel_names.add(ch["name"])

        if province:
            logger.info(f"🌏 省份兜底: {ch['name']} -> {cat}")
        else:
            logger.info(f"📌 未分类: {ch['name']}")

    logger.info(f"🎯 Demo 筛选：原始 {len(channels)} -> 匹配/分类后 {len(matched)} 个频道")
    return matched, []


# ========== 调试辅助：查看当前县市映射情况 ==========
def _debug_city_map():
    """
    供开发调试使用：在 Python REPL 中执行
        from src.demo_filter import _debug_city_map
        _debug_city_map()
    可快速查看当前加载的县市映射数量与来源。
    """
    city_map = get_city_province_map()
    print(f"📊 当前县市/区映射总数: {len(city_map)}")
    # 统计每个省份的映射数量
    stats: Dict[str, int] = {}
    for city, prov in city_map.items():
        stats[prov] = stats.get(prov, 0) + 1
    for prov, cnt in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"   {prov}: {cnt} 个")
