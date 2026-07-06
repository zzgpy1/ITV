# src/demo_filter.py
# Demo 频道筛选与排序模块，支持拼音匹配和省份自动归类
# 港澳台统一归入 🌊港·澳·台 分类
# 日本频道归入 日本频道 分类
# 未匹配频道按省份自动分配到对应分类

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

# 内部分类名到 Demo 分类名的映射（确保与 demo.txt 中一致）
CATEGORY_NAME_MAP = {
    "港澳台": "🌊港·澳·台",
    # 如有其他分类需要映射，可在此添加
}


def parse_demo_order_with_categories(demo_file: Path = DEMO_FILE) -> List[Tuple[str, str]]:
    """解析 demo.txt，返回 [(分类, 频道名), ...]"""
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
    """将中文转换为拼音（小写，无空格）"""
    if not HAS_PYPINYIN:
        return text.lower()
    try:
        return ''.join(lazy_pinyin(text)).lower()
    except:
        return text.lower()


def match_channel_name(channel_name: str, demo_name: str) -> bool:
    """
    增强匹配：支持中文/拼音/子串匹配
    """
    if DEMO_MATCH_MODE == "exact":
        return channel_name == demo_name
    
    cn_lower = channel_name.lower()
    dn_lower = demo_name.lower()
    
    # 1. 直接包含匹配
    if dn_lower in cn_lower or cn_lower in dn_lower:
        return True
    
    # 2. 拼音匹配
    if HAS_PYPINYIN:
        demo_pinyin = to_pinyin(demo_name)
        channel_pinyin = to_pinyin(channel_name)
        if demo_pinyin in channel_pinyin or channel_pinyin in demo_pinyin:
            return True
    
    # 3. 去除特殊字符后的匹配
    def clean(s):
        return re.sub(r'[^a-zA-Z\u4e00-\u9fa5]', '', s).lower()
    if clean(demo_name) in clean(channel_name) or clean(channel_name) in clean(demo_name):
        return True
    
    return False


def detect_province(channel_name: str) -> str:
    """
    检测频道名中的省份/城市，返回省份名（如"北京"）
    港澳台返回 "港澳台" 以便统一归类
    日本返回 "日本"
    """
    name = channel_name
    
    # 先检测日本（关键词：NHK, Japan, Tokyo, Fuji, TBS, TV Asahi, NTV, 日本等）
    jp_keywords = ["NHK", "Japan", "Tokyo", "Fuji", "TBS", "TV Asahi", "NTV", "日本"]
    for kw in jp_keywords:
        if kw in name:
            return "日本"
    
    # 检测港澳台
    hmtj_keywords = ["香港", "澳门", "台湾", "港", "澳", "台"]
    for kw in hmtj_keywords:
        if kw in name:
            return "港澳台"
    
    # 检测省份
    for prov in PROVINCES:
        if prov in name:
            return prov
    # 直辖市简称
    if "京" in name: return "北京"
    if "沪" in name: return "上海"
    if "津" in name: return "天津"
    if "渝" in name: return "重庆"
    
    # 常见地级市映射到省份（扩展）
    city_to_province = {
        # 广东
        "广州": "广东", "深圳": "广东", "佛山": "广东", "东莞": "广东", 
        "中山": "广东", "珠海": "广东", "江门": "广东", "肇庆": "广东",
        "惠州": "广东", "汕头": "广东", "潮州": "广东", "揭阳": "广东",
        "湛江": "广东", "茂名": "广东", "阳江": "广东", "清远": "广东",
        "韶关": "广东", "河源": "广东", "梅州": "广东", "云浮": "广东",
        # 浙江
        "杭州": "浙江", "宁波": "浙江", "温州": "浙江", "绍兴": "浙江",
        "嘉兴": "浙江", "湖州": "浙江", "金华": "浙江", "衢州": "浙江",
        "舟山": "浙江", "台州": "浙江", "丽水": "浙江",
        # 江苏
        "南京": "江苏", "苏州": "江苏", "无锡": "江苏", "常州": "江苏",
        "镇江": "江苏", "南通": "江苏", "扬州": "江苏", "徐州": "江苏",
        "盐城": "江苏", "淮安": "江苏", "连云港": "江苏", "泰州": "江苏",
        "宿迁": "江苏",
        # 山东
        "济南": "山东", "青岛": "山东", "淄博": "山东", "烟台": "山东",
        "潍坊": "山东", "济宁": "山东", "泰安": "山东", "威海": "山东",
        "日照": "山东", "临沂": "山东", "德州": "山东", "聊城": "山东",
        "滨州": "山东", "菏泽": "山东", "枣庄": "山东",
        # 福建
        "福州": "福建", "厦门": "福建", "泉州": "福建", "漳州": "福建",
        "莆田": "福建", "龙岩": "福建", "三明": "福建", "南平": "福建",
        "宁德": "福建",
        # 四川
        "成都": "四川", "绵阳": "四川", "德阳": "四川", "宜宾": "四川",
        "自贡": "四川", "攀枝花": "四川", "泸州": "四川", "广元": "四川",
        "遂宁": "四川", "内江": "四川", "乐山": "四川", "资阳": "四川",
        "南充": "四川", "眉山": "四川", "达州": "四川",
        # 湖北
        "武汉": "湖北", "宜昌": "湖北", "襄阳": "湖北", "黄石": "湖北",
        "十堰": "湖北", "荆州": "湖北", "荆门": "湖北", "鄂州": "湖北",
        "孝感": "湖北", "黄冈": "湖北", "咸宁": "湖北", "随州": "湖北",
        "恩施": "湖北",
        # 湖南
        "长沙": "湖南", "株洲": "湖南", "湘潭": "湖南", "衡阳": "湖南",
        "邵阳": "湖南", "岳阳": "湖南", "常德": "湖南", "张家界": "湖南",
        "益阳": "湖南", "郴州": "湖南", "永州": "湖南", "怀化": "湖南",
        "娄底": "湖南",
        # 河南
        "郑州": "河南", "开封": "河南", "洛阳": "河南", "平顶山": "河南",
        "安阳": "河南", "鹤壁": "河南", "新乡": "河南", "焦作": "河南",
        "濮阳": "河南", "许昌": "河南", "漯河": "河南", "三门峡": "河南",
        "南阳": "河南", "商丘": "河南", "信阳": "河南", "周口": "河南",
        "驻马店": "河南",
        # 河北
        "石家庄": "河北", "唐山": "河北", "秦皇岛": "河北", "邯郸": "河北",
        "邢台": "河北", "保定": "河北", "张家口": "河北", "承德": "河北",
        "沧州": "河北", "廊坊": "河北", "衡水": "河北",
        # 安徽
        "合肥": "安徽", "芜湖": "安徽", "蚌埠": "安徽", "淮南": "安徽",
        "马鞍山": "安徽", "淮北": "安徽", "铜陵": "安徽", "安庆": "安徽",
        "黄山": "安徽", "滁州": "安徽", "阜阳": "安徽", "宿州": "安徽",
        "六安": "安徽", "亳州": "安徽", "池州": "安徽", "宣城": "安徽",
        # 江西
        "南昌": "江西", "景德镇": "江西", "萍乡": "江西", "九江": "江西",
        "新余": "江西", "鹰潭": "江西", "赣州": "江西", "吉安": "江西",
        "宜春": "江西", "抚州": "江西", "上饶": "江西",
        # 广西
        "南宁": "广西", "柳州": "广西", "桂林": "广西", "梧州": "广西",
        "北海": "广西", "防城港": "广西", "钦州": "广西", "贵港": "广西",
        "玉林": "广西", "百色": "广西", "贺州": "广西", "河池": "广西",
        "来宾": "广西", "崇左": "广西",
        # 山西
        "太原": "山西", "大同": "山西", "阳泉": "山西", "长治": "山西",
        "晋城": "山西", "朔州": "山西", "晋中": "山西", "运城": "山西",
        "忻州": "山西", "临汾": "山西", "吕梁": "山西",
        # 内蒙古
        "呼和浩特": "内蒙古", "包头": "内蒙古", "乌海": "内蒙古", "赤峰": "内蒙古",
        "通辽": "内蒙古", "鄂尔多斯": "内蒙古", "呼伦贝尔": "内蒙古", 
        "巴彦淖尔": "内蒙古", "乌兰察布": "内蒙古",
        # 辽宁
        "沈阳": "辽宁", "大连": "辽宁", "鞍山": "辽宁", "抚顺": "辽宁",
        "本溪": "辽宁", "丹东": "辽宁", "锦州": "辽宁", "营口": "辽宁",
        "阜新": "辽宁", "辽阳": "辽宁", "盘锦": "辽宁", "铁岭": "辽宁",
        "朝阳": "辽宁", "葫芦岛": "辽宁",
        # 吉林
        "长春": "吉林", "吉林": "吉林", "四平": "吉林", "辽源": "吉林",
        "通化": "吉林", "白山": "吉林", "松原": "吉林", "白城": "吉林",
        "延边": "吉林",
        # 黑龙江
        "哈尔滨": "黑龙江", "齐齐哈尔": "黑龙江", "鸡西": "黑龙江",
        "鹤岗": "黑龙江", "双鸭山": "黑龙江", "大庆": "黑龙江",
        "伊春": "黑龙江", "佳木斯": "黑龙江", "七台河": "黑龙江",
        "牡丹江": "黑龙江", "黑河": "黑龙江", "绥化": "黑龙江",
        # 贵州
        "贵阳": "贵州", "六盘水": "贵州", "遵义": "贵州", "安顺": "贵州",
        "铜仁": "贵州", "毕节": "贵州", "黔东南": "贵州", "黔南": "贵州",
        # 云南
        "昆明": "云南", "曲靖": "云南", "玉溪": "云南", "保山": "云南",
        "昭通": "云南", "丽江": "云南", "普洱": "云南", "临沧": "云南",
        "红河": "云南", "文山": "云南", "西双版纳": "云南", "大理": "云南",
        "德宏": "云南",
        # 陕西
        "西安": "陕西", "铜川": "陕西", "宝鸡": "陕西", "咸阳": "陕西",
        "渭南": "陕西", "延安": "陕西", "汉中": "陕西", "榆林": "陕西",
        "安康": "陕西", "商洛": "陕西",
        # 甘肃
        "兰州": "甘肃", "嘉峪关": "甘肃", "金昌": "甘肃", "白银": "甘肃",
        "天水": "甘肃", "武威": "甘肃", "张掖": "甘肃", "平凉": "甘肃",
        "酒泉": "甘肃", "庆阳": "甘肃", "定西": "甘肃", "陇南": "甘肃",
        # 新疆
        "乌鲁木齐": "新疆", "克拉玛依": "新疆", "吐鲁番": "新疆",
        "哈密": "新疆", "昌吉": "新疆", "伊犁": "新疆", "塔城": "新疆",
        "阿勒泰": "新疆", "石河子": "新疆",
    }
    
    for city, prov in city_to_province.items():
        if city in name:
            return prov
    
    return None


def get_demo_category_for_province(province: str, demo_order: List[Tuple[str, str]]) -> str:
    """
    根据省份名生成对应的 demo 分类名
    若 demo 中有 "☘️北京频道,#genre#" 则返回 "☘️北京频道"
    否则返回 "☘️北京频道"
    港澳台统一返回 "🌊港·澳·台"
    日本返回 "日本频道"
    """
    # 港澳台特殊处理
    if province == "港澳台":
        return "🌊港·澳·台"
    # 日本特殊处理
    if province == "日本":
        # 尝试在 demo 中查找 "日本频道" 或 "日本"
        for cat, _ in demo_order:
            if cat == "日本频道" or cat == "日本":
                return cat
        # 若没有，返回默认 "日本频道"
        return "日本频道"
    # 其他省份
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


def normalize_demo_category(cat: str) -> str:
    """将内部分类名映射到 Demo 中的分类名"""
    return CATEGORY_NAME_MAP.get(cat, cat)


def filter_and_order_by_demo(channels: list) -> tuple:
    """
    增强筛选 + 智能追加：
    1. 匹配 demo 中的频道（支持拼音）
    2. 未匹配的但测速有效的频道，按省份/城市自动追加到对应分类
    3. 港澳台统一归入 🌊港·澳·台
    4. 日本归入 日本频道
    5. 如果 demo_order 为空，则使用 classify_and_filter 按分类输出所有频道（仅保留四大类）
    """
    demo_order = parse_demo_order_with_categories()
    if not demo_order:
        logger.warning("⚠️ demo.txt 为空，按分类筛选所有频道（仅保留央视/卫视/地方/港澳台）")
        # 使用 classifier 分类并只保留主要分类
        classified = classify_and_filter(channels)
        # 保留的类别
        keep_cats = ["央视", "卫视", "地方", "港澳台"]
        matched = []
        for cat in keep_cats:
            for ch in classified.get(cat, []):
                ch_copy = ch.copy()
                # 应用分类名映射
                ch_copy["demo_category"] = normalize_demo_category(cat)
                ch_copy["demo_name"] = ch["name"]
                matched.append(ch_copy)
        # 按分类顺序排序：央视、卫视、地方、港澳台
        # 每个分类内频道已由 classify_and_filter 排序
        logger.info(f"📊 按分类筛选后，保留 {len(matched)} 个频道")
        return matched, []

    name_to_channel = {ch["name"]: ch for ch in channels}
    matched = []
    unmatched = list(channels)
    matched_names = set()
    
    # 第一遍：匹配 demo 中的频道名（支持拼音）
    for category, demo_name in demo_order:
        # 精确匹配
        if demo_name in name_to_channel:
            ch = name_to_channel[demo_name].copy()
            ch["demo_category"] = category
            ch["demo_name"] = demo_name
            if ch["name"] not in matched_names:
                matched.append(ch)
                matched_names.add(ch["name"])
                unmatched = [c for c in unmatched if c["name"] != ch["name"]]
                continue
        
        # 模糊/拼音匹配
        found = False
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
                found = True
                logger.debug(f"🎯 匹配: {ch['name']} -> {category}/{demo_name}")
                break

    # 第二遍：未匹配频道自动归类到省份分类（港澳台统一归入 🌊港·澳·台，日本归入 日本频道）
    remaining = []
    province_appended = {}
    appended_names = set()
    
    for ch in unmatched:
        # 如果该频道已经在 matched 中（通过名字），跳过
        if ch["name"] in matched_names:
            continue
        province = detect_province(ch["name"])
        if province:
            cat = get_demo_category_for_province(province, demo_order)
            ch_copy = ch.copy()
            ch_copy["demo_category"] = cat
            ch_copy["demo_name"] = ch["name"]
            matched.append(ch_copy)
            matched_names.add(ch["name"])
            appended_names.add(ch["name"])
            province_appended[province] = province_appended.get(province, 0) + 1
            logger.info(f"🌏 自动追加: {ch['name']} -> {cat}")
        else:
            remaining.append(ch)
    
    if province_appended:
        logger.info(f"📊 自动追加统计: {dict(province_appended)}")
    
    # 对所有匹配的频道，确保 demo_category 经过映射（以防万一）
    for ch in matched:
        ch["demo_category"] = normalize_demo_category(ch.get("demo_category", "其他"))
    
    logger.info(f"🎯 Demo 筛选：原始 {len(channels)} -> 匹配 {len(matched)}，未匹配 {len(remaining)}")
    return matched, remaining


def write_shai_file(unmatched_channels: list, matched_count: int, total_raw: int):
    """保存未匹配的频道列表"""
    shai_path = OUTPUT_DIR / "shai.txt"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(shai_path, "w", encoding="utf-8") as f:
        f.write("# Demo筛选丢弃的频道\n")
        f.write(f"# 原始频道总数: {total_raw}\n")
        f.write(f"# Demo匹配成功: {matched_count}\n")
        f.write(f"# 丢弃数量: {len(unmatched_channels)}\n\n")
        
        for ch in unmatched_channels:
            url = ch["urls"][0] if ch.get("urls") else ch["url"]
            f.write(f"{ch['name']},{url}\n")
    
    logger.info(f"📄 未匹配频道列表已保存: {shai_path}")
