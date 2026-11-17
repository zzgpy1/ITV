# src/demo_filter.py
import re
from pathlib import Path
from typing import List, Tuple, Dict, Set
from src.config_loader import config
from src.classifier import PROVINCES, classify_and_filter
from src.logger import logger

try:
    from pypinyin import lazy_pinyin
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False
    logger.warning("⚠️ pypinyin未安装，拼音匹配功能不可用")


# ========== 城市/区县 -> 省份映射（大幅扩展县级市/市辖区） ==========
CITY_TO_PROVINCE: Dict[str, str] = {
    # 直辖市
    "北京": "北京", "上海": "上海", "天津": "天津", "重庆": "重庆",
    # 重庆区县
    "江津": "重庆", "荣昌": "重庆", "璧山": "重庆", "铜梁": "重庆",
    "潼南": "重庆", "大足": "重庆", "垫江": "重庆", "武隆": "重庆",
    "万州": "重庆", "涪陵": "重庆", "长寿": "重庆", "合川": "重庆",
    "永川": "重庆", "南川": "重庆", "綦江": "重庆", "黔江": "重庆",
    "梁平": "重庆", "城口": "重庆", "丰都": "重庆", "忠县": "重庆",
    "云阳": "重庆", "奉节": "重庆", "巫山": "重庆", "巫溪": "重庆",
    "石柱": "重庆", "秀山": "重庆", "酉阳": "重庆", "彭水": "重庆",
    "开州": "重庆", "北碚": "重庆",
    # 广东省（地级市 + 区县）
    "广州": "广东", "深圳": "广东", "佛山": "广东", "东莞": "广东",
    "中山": "广东", "珠海": "广东", "惠州": "广东", "江门": "广东",
    "汕头": "广东", "湛江": "广东", "茂名": "广东", "肇庆": "广东",
    "韶关": "广东", "梅州": "广东", "汕尾": "广东", "河源": "广东",
    "阳江": "广东", "清远": "广东", "潮州": "广东", "揭阳": "广东",
    "云浮": "广东", "番禺": "广东", "顺德": "广东", "南海": "广东",
    "增城": "广东", "从化": "广东", "花都": "广东",
    "龙门": "广东", "博罗": "广东", "惠东": "广东",
    "台山": "广东", "开平": "广东", "恩平": "广东", "鹤山": "广东",
    # 浙江省（地级市 + 区县）
    "杭州": "浙江", "宁波": "浙江", "温州": "浙江", "嘉兴": "浙江",
    "湖州": "浙江", "绍兴": "浙江", "金华": "浙江", "衢州": "浙江",
    "舟山": "浙江", "台州": "浙江", "丽水": "浙江",
    "上虞": "浙江", "余杭": "浙江", "萧山": "浙江", "衢江": "浙江",
    "象山": "浙江", "遂昌": "浙江", "嵊州": "浙江", "新昌": "浙江",
    "义乌": "浙江", "东阳": "浙江", "永康": "浙江", "兰溪": "浙江",
    "诸暨": "浙江", "余姚": "浙江", "慈溪": "浙江", "奉化": "浙江",
    "苍南": "浙江", "乐清": "浙江", "瑞安": "浙江", "永嘉": "浙江",
    "洞头": "浙江", "文成": "浙江", "平阳": "浙江", "泰顺": "浙江",
    "海宁": "浙江", "海盐": "浙江", "平湖": "浙江", "桐乡": "浙江",
    "德清": "浙江", "长兴": "浙江", "安吉": "浙江",
    "武义": "浙江", "浦江": "浙江", "磐安": "浙江",
    "龙游": "浙江", "江山": "浙江", "常山": "浙江", "开化": "浙江",
    "定海": "浙江", "普陀": "浙江", "岱山": "浙江", "嵊泗": "浙江",
    "临海": "浙江", "温岭": "浙江", "玉环": "浙江", "天台": "浙江",
    "仙居": "浙江", "三门": "浙江",
    "龙泉": "浙江", "青田": "浙江", "云和": "浙江", "庆元": "浙江",
    "缙云": "浙江", "松阳": "浙江", "景宁": "浙江",
    # 江苏省
    "南京": "江苏", "苏州": "江苏", "无锡": "江苏", "常州": "江苏",
    "徐州": "江苏", "南通": "江苏", "扬州": "江苏", "镇江": "江苏",
    "泰州": "江苏", "盐城": "江苏", "淮安": "江苏", "连云港": "江苏",
    "宿迁": "江苏", "武进": "江苏", "金坛": "江苏", "溧阳": "江苏",
    "常熟": "江苏", "张家港": "江苏", "昆山": "江苏", "太仓": "江苏",
    "靖江": "江苏", "海安": "江苏", "如东": "江苏", "启东": "江苏",
    "如皋": "江苏", "海门": "江苏", "赣榆": "江苏", "东海": "江苏",
    "灌云": "江苏", "灌南": "江苏", "淮阴": "江苏", "涟水": "江苏",
    "楚州": "江苏", "洪泽": "江苏", "盱眙": "江苏", "金湖": "江苏",
    "盐都": "江苏", "响水": "江苏", "滨海": "江苏", "阜宁": "江苏",
    "射阳": "江苏", "建湖": "江苏", "东台": "江苏", "大丰": "江苏",
    "宝应": "江苏", "仪征": "江苏", "高邮": "江苏", "江都": "江苏",
    "丹阳": "江苏", "扬中": "江苏", "句容": "江苏", "泰兴": "江苏",
    "姜堰": "江苏", "兴化": "江苏", "沭阳": "江苏", "泗阳": "江苏",
    "泗洪": "江苏",
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
    # 湖北省（含区县）
    "武汉": "湖北", "黄石": "湖北", "十堰": "湖北", "宜昌": "湖北",
    "襄阳": "湖北", "鄂州": "湖北", "荆门": "湖北", "孝感": "湖北",
    "荆州": "湖北", "黄冈": "湖北", "咸宁": "湖北", "随州": "湖北",
    "江夏": "湖北", "黄陂": "湖北", "新洲": "湖北",
    "郧阳": "湖北", "郧西": "湖北", "竹山": "湖北", "竹溪": "湖北",
    "房县": "湖北", "丹江口": "湖北", "麻城": "湖北", "武穴": "湖北",
    "广水": "湖北", "恩施": "湖北", "利川": "湖北", "建始": "湖北",
    "巴东": "湖北", "宣恩": "湖北", "咸丰": "湖北", "来凤": "湖北",
    "鹤峰": "湖北", "仙桃": "湖北", "潜江": "湖北", "天门": "湖北",
    "神农架": "湖北",
    # 湖南省
    "长沙": "湖南", "株洲": "湖南", "湘潭": "湖南", "衡阳": "湖南",
    "邵阳": "湖南", "岳阳": "湖南", "常德": "湖南", "张家界": "湖南",
    "益阳": "湖南", "郴州": "湖南", "永州": "湖南", "怀化": "湖南",
    "娄底": "湖南", "湘西": "湖南",
    # 河南省
    "郑州": "河南", "开封": "河南", "洛阳": "河南", "平顶山": "河南",
    "安阳": "河南", "鹤壁": "河南", "新乡": "河南", "焦作": "河南",
    "濮阳": "河南", "许昌": "河南", "漯河": "河南", "三门峡": "河南",
    "南阳": "河南", "商丘": "河南", "信阳": "河南", "周口": "河南",
    "驻马店": "河南", "济源": "河南",
    # 河北省
    "石家庄": "河北", "唐山": "河北", "秦皇岛": "河北", "邯郸": "河北",
    "邢台": "河北", "保定": "河北", "张家口": "河北", "承德": "河北",
    "沧州": "河北", "廊坊": "河北", "衡水": "河北", "兴隆": "河北",
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
    # 吉林省（含区县）
    "长春": "吉林", "吉林": "吉林", "四平": "吉林", "辽源": "吉林",
    "通化": "吉林", "白山": "吉林", "松原": "吉林", "白城": "吉林",
    "延边": "吉林", "双辽": "吉林", "九台": "吉林", "汪清": "吉林",
    "磐石": "吉林", "舒兰": "吉林", "辉南": "吉林", "龙井": "吉林",
    "通化县": "吉林", "长白山": "吉林", "敦化": "吉林", "珲春": "吉林",
    "图们": "吉林", "和龙": "吉林", "安图": "吉林",
    # 黑龙江省
    "哈尔滨": "黑龙江", "齐齐哈尔": "黑龙江", "鸡西": "黑龙江",
    "鹤岗": "黑龙江", "双鸭山": "黑龙江", "大庆": "黑龙江",
    "伊春": "黑龙江", "佳木斯": "黑龙江", "七台河": "黑龙江",
    "牡丹江": "黑龙江", "黑河": "黑龙江", "绥化": "黑龙江",
    "大兴安岭": "黑龙江",
    # 陕西省
    "西安": "陕西", "铜川": "陕西", "宝鸡": "陕西", "咸阳": "陕西",
    "渭南": "陕西", "延安": "陕西", "汉中": "陕西", "榆林": "陕西",
    "安康": "陕西", "商洛": "陕西",
    # 甘肃省
    "兰州": "甘肃", "嘉峪关": "甘肃", "金昌": "甘肃", "白银": "甘肃",
    "天水": "甘肃", "武威": "甘肃", "张掖": "甘肃", "平凉": "甘肃",
    "酒泉": "甘肃", "庆阳": "甘肃", "定西": "甘肃", "陇南": "甘肃",
    "临夏": "甘肃", "甘南": "甘肃",
    # 云南省
    "昆明": "云南", "曲靖": "云南", "玉溪": "云南", "保山": "云南",
    "昭通": "云南", "丽江": "云南", "普洱": "云南", "临沧": "云南",
    "楚雄": "云南", "红河": "云南", "文山": "云南", "西双版纳": "云南",
    "大理": "云南", "德宏": "云南", "怒江": "云南", "迪庆": "云南",
    "通海": "云南",
    # 贵州省
    "贵阳": "贵州", "六盘水": "贵州", "遵义": "贵州", "安顺": "贵州",
    "毕节": "贵州", "铜仁": "贵州", "黔西南": "贵州", "黔东南": "贵州",
    "黔南": "贵州",
    # 广西
    "南宁": "广西", "柳州": "广西", "桂林": "广西", "梧州": "广西",
    "北海": "广西", "防城港": "广西", "钦州": "广西", "贵港": "广西",
    "玉林": "广西", "百色": "广西", "贺州": "广西", "河池": "广西",
    "来宾": "广西", "崇左": "广西",
    # 海南省
    "海口": "海南", "三亚": "海南", "三沙": "海南", "儋州": "海南",
    # 内蒙古
    "呼和浩特": "内蒙古", "包头": "内蒙古", "乌海": "内蒙古",
    "赤峰": "内蒙古", "通辽": "内蒙古", "鄂尔多斯": "内蒙古",
    "呼伦贝尔": "内蒙古", "巴彦淖尔": "内蒙古", "乌兰察布": "内蒙古",
    "兴安": "内蒙古", "锡林郭勒": "内蒙古", "阿拉善": "内蒙古",
    # 新疆（含区县/兵团市）
    "乌鲁木齐": "新疆", "克拉玛依": "新疆", "吐鲁番": "新疆",
    "哈密": "新疆", "昌吉": "新疆", "博尔塔拉": "新疆",
    "巴音郭楞": "新疆", "阿克苏": "新疆", "克孜勒苏": "新疆",
    "喀什": "新疆", "和田": "新疆", "伊犁": "新疆", "塔城": "新疆",
    "阿勒泰": "新疆", "石河子": "新疆", "阿拉尔": "新疆",
    "图木舒克": "新疆", "五家渠": "新疆", "北屯": "新疆",
    "铁门关": "新疆", "双河": "新疆", "可克达拉": "新疆",
    "昆玉": "新疆", "胡杨河": "新疆", "新星": "新疆",
    "奎屯": "新疆", "玛纳斯": "新疆", "五师": "新疆", "四师": "新疆",
    # 西藏
    "拉萨": "西藏", "日喀则": "西藏", "昌都": "西藏", "林芝": "西藏",
    "山南": "西藏", "那曲": "西藏", "阿里": "西藏",
    # 青海
    "西宁": "青海", "海东": "青海", "海北": "青海", "黄南": "青海",
    "果洛": "青海", "玉树": "青海", "海西": "青海",
    # 宁夏
    "银川": "宁夏", "石嘴山": "宁夏", "吴忠": "宁夏", "固原": "宁夏",
    "中卫": "宁夏",
}

# 省份简称 -> 完整省份名
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
    if not HAS_PYPINYIN:
        return text.lower()
    try:
        return ''.join(lazy_pinyin(text)).lower()
    except:
        return text.lower()


def match_channel_name(channel_name: str, demo_name: str) -> bool:
    """频道名与 demo 名匹配（双向包含 + 拼音 + 去特殊字符）"""
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
        if num == "5":
            if ('+' in dn_lower or '5plus' in dn_lower) != ('+' in cn_lower or '5plus' in cn_lower):
                return False
        if num in ["4k", "8k"]:
            return True
        if num.isdigit() and 1 <= int(num) <= 17:
            area_keywords = {"欧洲": ["欧洲", "europe"], "美洲": ["美洲", "america", "americas"], "中文国际": ["中文国际"]}
            for kw, variants in area_keywords.items():
                if kw in dn_lower:
                    if not any(v in cn_lower for v in variants):
                        return False
            return True

    # 双向包含
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
    3. 城市/区县映射（长词优先）
    4. 省份简称
    """
    name = channel_name.strip()
    if not name:
        return None

    # 1. 港澳台
    for kw in ["香港", "澳门", "台湾", "港台", "TVB", "翡翠", "明珠", "凤凰", "澳视"]:
        if kw in name:
            return "港澳台"

    # 2. 完整省份名
    for prov in PROVINCES:
        if prov in name:
            return prov

    # 3. 城市/区县映射（长词优先，避免"海南"误匹配"海南藏族自治州"）
    sorted_cities = sorted(CITY_TO_PROVINCE.keys(), key=len, reverse=True)
    for city in sorted_cities:
        if city in name:
            return CITY_TO_PROVINCE[city]

    # 4. 省份简称（独立字符才匹配）
    for alias, prov in PROVINCE_ALIASES.items():
        if re.search(rf'(?<![a-zA-Z\u4e00-\u9fa5]){alias}(?![a-zA-Z\u4e00-\u9fa5])', name):
            return prov

    return None


def get_demo_category_for_province(province: str, demo_order: List[Tuple[str, str]]) -> str:
    if province == "港澳台":
        return "🌊港·澳·台"
    candidates = [f"☘️{province}频道", f"{province}频道", f"☘️{province}", f"{province}"]
    for cat, _ in demo_order:
        for cand in candidates:
            if cat.startswith(cand) or cat == cand:
                return cat
    return f"☘️{province}频道"


def filter_and_order_by_demo(channels: list) -> tuple:
    """
    按 demo.txt 顺序过滤/排序，未匹配的按省份自动归类。
    """
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

    # ===== 第二轮：模糊匹配（允许同一 demo_name 匹配多个采集频道，不跳过） =====
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

    # ===== 第三轮：未匹配按省份自动归类 =====
    for ch in list(unmatched):
        if ch["name"] in matched_channel_names:
            continue
        province = detect_province(ch["name"])
        cat = get_demo_category_for_province(province, demo_order) if province else "其他"
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
