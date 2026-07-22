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
    """
    精确检测频道所属省份，避免误判。
    返回省份名称（如"北京"、"江苏"），若无法识别则返回 None。
    """
    name = channel_name.strip()
    if not name:
        return None

    # 1. 精确匹配港澳台（这些词必须独立，避免“电视台”误判）
    hk_macau_taiwan = ["香港", "澳门", "台湾", "港台"]
    for kw in hk_macau_taiwan:
        if kw in name:
            return "港澳台"

    # 2. 省份匹配（要求省份作为独立词出现，避免“北京”被“京”误匹配）
    # 使用正则，确保省份前后不是字母数字，防止部分匹配
    for prov in PROVINCES:
        # 如果省份是“北京”，则匹配“北京”但不匹配“北京大学”
        if re.search(rf'(?<![a-zA-Z\u4e00-\u9fa5]){prov}(?![a-zA-Z\u4e00-\u9fa5])', name):
            return prov

    # 3. 城市映射（补充常见地级市，注意避免误判）
    city_map = {
        # 直辖市
        "北京": "北京", "上海": "上海", "天津": "天津", "重庆": "重庆",
        # 广东省
        "广州": "广东", "深圳": "广东", "佛山": "广东", "东莞": "广东",
        "中山": "广东", "珠海": "广东", "惠州": "广东", "江门": "广东",
        "汕头": "广东", "湛江": "广东", "茂名": "广东", "肇庆": "广东",
        # 浙江省
        "杭州": "浙江", "宁波": "浙江", "温州": "浙江", "嘉兴": "浙江",
        "湖州": "浙江", "绍兴": "浙江", "金华": "浙江", "衢州": "浙江",
        "舟山": "浙江", "台州": "浙江", "丽水": "浙江",
        # 江苏省
        "南京": "江苏", "苏州": "江苏", "无锡": "江苏", "常州": "江苏",
        "徐州": "江苏", "南通": "江苏", "扬州": "江苏", "镇江": "江苏",
        "泰州": "江苏", "盐城": "江苏", "淮安": "江苏", "连云港": "江苏",
        "宿迁": "江苏",
        # 山东省
        "济南": "山东", "青岛": "山东", "淄博": "山东", "枣庄": "山东",
        "东营": "山东", "烟台": "山东", "潍坊": "山东", "济宁": "山东",
        "泰安": "山东", "威海": "山东", "日照": "山东", "临沂": "山东",
        "德州": "山东", "聊城": "山东", "滨州": "山东", "菏泽": "山东",
        # 福建省
        "福州": "福建", "厦门": "福建", "莆田": "福建", "三明": "福建",
        "泉州": "福建", "漳州": "福建", "南平": "福建", "龙岩": "福建",
        "宁德": "福建",
        # 四川省
        "成都": "四川", "绵阳": "四川", "德阳": "四川", "宜宾": "四川",
        "自贡": "四川", "攀枝花": "四川", "泸州": "四川", "广元": "四川",
        "遂宁": "四川", "内江": "四川", "乐山": "四川", "南充": "四川",
        "眉山": "四川", "广安": "四川", "达州": "四川", "雅安": "四川",
        "巴中": "四川", "资阳": "四川",
        # 湖北省
        "武汉": "湖北", "黄石": "湖北", "十堰": "湖北", "宜昌": "湖北",
        "襄阳": "湖北", "鄂州": "湖北", "荆门": "湖北", "孝感": "湖北",
        "荆州": "湖北", "黄冈": "湖北", "咸宁": "湖北", "随州": "湖北",
        # 湖南省
        "长沙": "湖南", "株洲": "湖南", "湘潭": "湖南", "衡阳": "湖南",
        "邵阳": "湖南", "岳阳": "湖南", "常德": "湖南", "张家界": "湖南",
        "益阳": "湖南", "郴州": "湖南", "永州": "湖南", "怀化": "湖南",
        "娄底": "湖南",
        # 河南省
        "郑州": "河南", "开封": "河南", "洛阳": "河南", "平顶山": "河南",
        "安阳": "河南", "鹤壁": "河南", "新乡": "河南", "焦作": "河南",
        "濮阳": "河南", "许昌": "河南", "漯河": "河南", "三门峡": "河南",
        "南阳": "河南", "商丘": "河南", "信阳": "河南", "周口": "河南",
        "驻马店": "河南",
        # 河北省
        "石家庄": "河北", "唐山": "河北", "秦皇岛": "河北", "邯郸": "河北",
        "邢台": "河北", "保定": "河北", "张家口": "河北", "承德": "河北",
        "沧州": "河北", "廊坊": "河北", "衡水": "河北",
        # 安徽省
        "合肥": "安徽", "芜湖": "安徽", "蚌埠": "安徽", "淮南": "安徽",
        "马鞍山": "安徽", "淮北": "安徽", "铜陵": "安徽", "安庆": "安徽",
        "黄山": "安徽", "滁州": "安徽", "阜阳": "安徽", "宿州": "安徽",
        "六安": "安徽", "亳州": "安徽", "池州": "安徽", "宣城": "安徽",
        # 江西省
        "南昌": "江西", "景德镇": "江西", "萍乡": "江西", "九江": "江西",
        "新余": "江西", "鹰潭": "江西", "赣州": "江西", "吉安": "江西",
        "宜春": "江西", "抚州": "江西", "上饶": "江西",
        # 山西省
        "太原": "山西", "大同": "山西", "阳泉": "山西", "长治": "山西",
        "晋城": "山西", "朔州": "山西", "晋中": "山西", "运城": "山西",
        "忻州": "山西", "临汾": "山西", "吕梁": "山西",
        # 辽宁省
        "沈阳": "辽宁", "大连": "辽宁", "鞍山": "辽宁", "抚顺": "辽宁",
        "本溪": "辽宁", "丹东": "辽宁", "锦州": "辽宁", "营口": "辽宁",
        "阜新": "辽宁", "辽阳": "辽宁", "盘锦": "辽宁", "铁岭": "辽宁",
        "朝阳": "辽宁", "葫芦岛": "辽宁",
        # 吉林省
        "长春": "吉林", "吉林": "吉林", "四平": "吉林", "辽源": "吉林",
        "通化": "吉林", "白山": "吉林", "松原": "吉林", "白城": "吉林",
        # 黑龙江省
        "哈尔滨": "黑龙江", "齐齐哈尔": "黑龙江", "鸡西": "黑龙江",
        "鹤岗": "黑龙江", "双鸭山": "黑龙江", "大庆": "黑龙江",
        "伊春": "黑龙江", "佳木斯": "黑龙江", "七台河": "黑龙江",
        "牡丹江": "黑龙江", "黑河": "黑龙江", "绥化": "黑龙江",
        # 陕西省
        "西安": "陕西", "铜川": "陕西", "宝鸡": "陕西", "咸阳": "陕西",
        "渭南": "陕西", "延安": "陕西", "汉中": "陕西", "榆林": "陕西",
        "安康": "陕西", "商洛": "陕西",
        # 甘肃省
        "兰州": "甘肃", "嘉峪关": "甘肃", "金昌": "甘肃", "白银": "甘肃",
        "天水": "甘肃", "武威": "甘肃", "张掖": "甘肃", "平凉": "甘肃",
        "酒泉": "甘肃", "庆阳": "甘肃", "定西": "甘肃", "陇南": "甘肃",
        # 其他省份略...
    }
    for city, prov in city_map.items():
        if city in name:
            return prov

    # 4. 如果含有“电视台”且前面没有省份信息，则归为“地方”或“其他”
    if "电视台" in name:
        # 若无法识别省份，但属于地方台，返回 None 以便调用方归为“其他”
        return None

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
