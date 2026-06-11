# src/demo_filter.py
# Demo 频道筛选与排序模块，支持地方频道和港澳台频道的自动归类

from pathlib import Path
from typing import List, Tuple
from src.config import DEMO_FILE, OUTPUT_DIR, DEMO_MATCH_MODE
from src.alias_matcher import get_alias_matcher
from src.classifier import PROVINCES, classify_channel
from src.logger import logger


def parse_demo_order_with_categories(demo_file: Path = DEMO_FILE) -> List[Tuple[str, str]]:
    """解析 demo.txt，返回 [(分类, 频道名), ...] 保持原始顺序"""
    if not demo_file.exists():
        logger.warning(f"⚠️ Demo 文件不存在: {demo_file}")
        return []
    
    matcher = get_alias_matcher()
    order = []
    current_category = None
    
    with open(demo_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            # 检测分类行（格式：分类名,#genre# 或 分类名, #genre#）
            if line.endswith(",#genre#") or line.endswith(", #genre#"):
                current_category = line.replace(", #genre#", "").replace(", #genre#", "").strip()
                continue
            
            # 跳过注释行
            if line.startswith('#'):
                continue
            
            # 处理频道行
            if current_category is not None:
                demo_name = line
                # 应用别名标准化
                if matcher:
                    demo_name = matcher.normalize(demo_name)
                order.append((current_category, demo_name))
            else:
                order.append(("其他", line))
    
    logger.info(f"📋 从 demo.txt 解析到 {len(order)} 个有序频道，共 {len(set(c for c, _ in order))} 个分类")
    
    # 调试：打印前30个 demo 项，确认 CCTV-5+ 是否存在
    logger.info("📋 Demo 顺序预览（前30项）：")
    for i, (cat, name) in enumerate(order[:30]):
        marker = " ← CCTV-5+" if name == "CCTV-5+" else ""
        logger.info(f"   {i+1}. [{cat}] {name}{marker}")
    
    return order


def match_channel_name(channel_name: str, demo_name: str) -> bool:
    """
    匹配频道名，正确处理 CCTV-5 和 CCTV-5+ 的区别
    """
    if DEMO_MATCH_MODE == "exact":
        return channel_name == demo_name
    
    # contains 模式
    cn_lower = channel_name.lower()
    dn_lower = demo_name.lower()
    
    # ========== CCTV-5+ 精确匹配（必须包含加号）==========
    if dn_lower == "cctv-5+":
        # 匹配任何包含 CCTV-5+ 或 CCTV5+ 的频道名
        result = ('cctv-5+' in cn_lower or 
                  'cctv5+' in cn_lower or 
                  'cctv-5＋' in cn_lower or
                  'cctv5＋' in cn_lower or
                  ('cctv-5' in cn_lower and ('+' in channel_name or '＋' in channel_name)))
        if result:
            logger.debug(f"✅ CCTV-5+ 匹配: '{channel_name}' -> '{demo_name}'")
        return result
    
    # ========== CCTV-5 匹配（排除 CCTV-5+）==========
    if dn_lower == "cctv-5":
        # 如果频道名包含加号，则不匹配 CCTV-5
        if '+' in channel_name or '＋' in channel_name:
            return False
        result = ('cctv-5' in cn_lower or 
                  'cctv5' in cn_lower or 
                  '央视5' in channel_name or
                  '中央5' in channel_name)
        if result:
            logger.debug(f"✅ CCTV-5 匹配: '{channel_name}' -> '{demo_name}'")
        return result
    
    # ========== CGTN 系列 ==========
    if dn_lower.startswith("cgtn"):
        if dn_lower == "cgtn":
            return 'cgtn' in cn_lower and 'cgtn俄' not in cn_lower and 'cgtn法' not in cn_lower
        return dn_lower in cn_lower
    
    # 普通匹配
    return dn_lower in cn_lower or cn_lower in dn_lower


def find_matching_demo_category(channel_name: str, demo_order: List[Tuple[str, str]]) -> str:
    """
    根据频道名查找最匹配的 demo 分类。
    优先匹配 demo 中的频道名，否则根据省份/地级市/关键词匹配分类。
    """
    # 1. 直接匹配 demo 中的频道名
    for category, demo_name in demo_order:
        if match_channel_name(channel_name, demo_name):
            return category

    # 2. 省份匹配
    for prov in PROVINCES:
        if prov in channel_name:
            for category, _ in demo_order:
                if prov in category and ("频道" in category or "☘️" in category):
                    return category

    # 3. 地级市 -> 省份 映射（大幅提升地方台匹配率）
    city_to_province = {
        # 浙江
        "杭州": "浙江", "宁波": "浙江", "温州": "浙江", "绍兴": "浙江", "嘉兴": "浙江",
        "湖州": "浙江", "金华": "浙江", "衢州": "浙江", "舟山": "浙江", "台州": "浙江",
        "丽水": "浙江", "义乌": "浙江", "余姚": "浙江", "慈溪": "浙江", "诸暨": "浙江",
        "乐清": "浙江", "瑞安": "浙江", "海宁": "浙江", "桐乡": "浙江", "平湖": "浙江",
        "东阳": "浙江", "永康": "浙江", "临海": "浙江", "温岭": "浙江", "龙泉": "浙江",
        # 广东
        "广州": "广东", "深圳": "广东", "佛山": "广东", "东莞": "广东", "中山": "广东",
        "珠海": "广东", "江门": "广东", "肇庆": "广东", "惠州": "广东", "汕头": "广东",
        "潮州": "广东", "揭阳": "广东", "汕尾": "广东", "湛江": "广东", "茂名": "广东",
        "阳江": "广东", "清远": "广东", "韶关": "广东", "河源": "广东", "梅州": "广东",
        "云浮": "广东",
        # 江苏
        "南京": "江苏", "苏州": "江苏", "无锡": "江苏", "常州": "江苏", "镇江": "江苏",
        "南通": "江苏", "扬州": "江苏", "徐州": "江苏", "盐城": "江苏", "淮安": "江苏",
        "连云港": "江苏", "泰州": "江苏", "宿迁": "江苏", "昆山": "江苏", "常熟": "江苏",
        # 山东
        "济南": "山东", "青岛": "山东", "淄博": "山东", "烟台": "山东", "潍坊": "山东",
        "济宁": "山东", "泰安": "山东", "威海": "山东", "日照": "山东", "临沂": "山东",
        "德州": "山东", "聊城": "山东", "滨州": "山东", "菏泽": "山东", "枣庄": "山东",
        # 福建
        "福州": "福建", "厦门": "福建", "泉州": "福建", "漳州": "福建", "莆田": "福建",
        "龙岩": "福建", "三明": "福建", "南平": "福建", "宁德": "福建",
        # 四川
        "成都": "四川", "绵阳": "四川", "德阳": "四川", "宜宾": "四川", "自贡": "四川",
        "攀枝花": "四川", "泸州": "四川", "广元": "四川", "遂宁": "四川", "内江": "四川",
        "乐山": "四川", "资阳": "四川", "南充": "四川", "眉山": "四川", "达州": "四川",
        # 湖北
        "武汉": "湖北", "宜昌": "湖北", "襄阳": "湖北", "黄石": "湖北", "十堰": "湖北",
        "荆州": "湖北", "荆门": "湖北", "鄂州": "湖北", "孝感": "湖北", "黄冈": "湖北",
        "咸宁": "湖北", "随州": "湖北", "恩施": "湖北",
        # 湖南
        "长沙": "湖南", "株洲": "湖南", "湘潭": "湖南", "衡阳": "湖南", "邵阳": "湖南",
        "岳阳": "湖南", "常德": "湖南", "张家界": "湖南", "益阳": "湖南", "郴州": "湖南",
        "永州": "湖南", "怀化": "湖南", "娄底": "湖南", "湘西": "湖南",
        # 河南
        "郑州": "河南", "开封": "河南", "洛阳": "河南", "平顶山": "河南", "安阳": "河南",
        "鹤壁": "河南", "新乡": "河南", "焦作": "河南", "濮阳": "河南", "许昌": "河南",
        "漯河": "河南", "三门峡": "河南", "南阳": "河南", "商丘": "河南", "信阳": "河南",
        "周口": "河南", "驻马店": "河南", "济源": "河南",
        # 河北
        "石家庄": "河北", "唐山": "河北", "秦皇岛": "河北", "邯郸": "河北", "邢台": "河北",
        "保定": "河北", "张家口": "河北", "承德": "河北", "沧州": "河北", "廊坊": "河北",
        "衡水": "河北",
        # 安徽
        "合肥": "安徽", "芜湖": "安徽", "蚌埠": "安徽", "淮南": "安徽", "马鞍山": "安徽",
        "淮北": "安徽", "铜陵": "安徽", "安庆": "安徽", "黄山": "安徽", "滁州": "安徽",
        "阜阳": "安徽", "宿州": "安徽", "六安": "安徽", "亳州": "安徽", "池州": "安徽",
        "宣城": "安徽",
        # 江西
        "南昌": "江西", "景德镇": "江西", "萍乡": "江西", "九江": "江西", "新余": "江西",
        "鹰潭": "江西", "赣州": "江西", "吉安": "江西", "宜春": "江西", "抚州": "江西",
        "上饶": "江西",
        # 广西
        "南宁": "广西", "柳州": "广西", "桂林": "广西", "梧州": "广西", "北海": "广西",
        "防城港": "广西", "钦州": "广西", "贵港": "广西", "玉林": "广西", "百色": "广西",
        "贺州": "广西", "河池": "广西", "来宾": "广西", "崇左": "广西",
        # 山西
        "太原": "山西", "大同": "山西", "阳泉": "山西", "长治": "山西", "晋城": "山西",
        "朔州": "山西", "晋中": "山西", "运城": "山西", "忻州": "山西", "临汾": "山西",
        "吕梁": "山西",
        # 内蒙古
        "呼和浩特": "内蒙古", "包头": "内蒙古", "乌海": "内蒙古", "赤峰": "内蒙古",
        "通辽": "内蒙古", "鄂尔多斯": "内蒙古", "呼伦贝尔": "内蒙古", "巴彦淖尔": "内蒙古",
        "乌兰察布": "内蒙古", "兴安": "内蒙古", "锡林郭勒": "内蒙古", "阿拉善": "内蒙古",
        # 辽宁
        "沈阳": "辽宁", "大连": "辽宁", "鞍山": "辽宁", "抚顺": "辽宁", "本溪": "辽宁",
        "丹东": "辽宁", "锦州": "辽宁", "营口": "辽宁", "阜新": "辽宁", "辽阳": "辽宁",
        "盘锦": "辽宁", "铁岭": "辽宁", "朝阳": "辽宁", "葫芦岛": "辽宁",
        # 吉林
        "长春": "吉林", "吉林": "吉林", "四平": "吉林", "辽源": "吉林", "通化": "吉林",
        "白山": "吉林", "松原": "吉林", "白城": "吉林", "延边": "吉林",
        # 黑龙江
        "哈尔滨": "黑龙江", "齐齐哈尔": "黑龙江", "鸡西": "黑龙江", "鹤岗": "黑龙江",
        "双鸭山": "黑龙江", "大庆": "黑龙江", "伊春": "黑龙江", "佳木斯": "黑龙江",
        "七台河": "黑龙江", "牡丹江": "黑龙江", "黑河": "黑龙江", "绥化": "黑龙江",
        # 贵州
        "贵阳": "贵州", "六盘水": "贵州", "遵义": "贵州", "安顺": "贵州", "铜仁": "贵州",
        "黔西南": "贵州", "毕节": "贵州", "黔东南": "贵州", "黔南": "贵州",
        # 云南
        "昆明": "云南", "曲靖": "云南", "玉溪": "云南", "保山": "云南", "昭通": "云南",
        "丽江": "云南", "普洱": "云南", "临沧": "云南", "楚雄": "云南", "红河": "云南",
        "文山": "云南", "西双版纳": "云南", "大理": "云南", "德宏": "云南", "怒江": "云南",
        "迪庆": "云南",
        # 陕西
        "西安": "陕西", "铜川": "陕西", "宝鸡": "陕西", "咸阳": "陕西", "渭南": "陕西",
        "延安": "陕西", "汉中": "陕西", "榆林": "陕西", "安康": "陕西", "商洛": "陕西",
        # 甘肃
        "兰州": "甘肃", "嘉峪关": "甘肃", "金昌": "甘肃", "白银": "甘肃", "天水": "甘肃",
        "武威": "甘肃", "张掖": "甘肃", "平凉": "甘肃", "酒泉": "甘肃", "庆阳": "甘肃",
        "定西": "甘肃", "陇南": "甘肃", "临夏": "甘肃", "甘南": "甘肃",
        # 青海
        "西宁": "青海", "海东": "青海", "海北": "青海", "黄南": "青海", "海南": "青海",
        "果洛": "青海", "玉树": "青海", "海西": "青海",
        # 宁夏
        "银川": "宁夏", "石嘴山": "宁夏", "吴忠": "宁夏", "固原": "宁夏", "中卫": "宁夏",
        # 新疆
        "乌鲁木齐": "新疆", "克拉玛依": "新疆", "吐鲁番": "新疆", "哈密": "新疆",
        "昌吉": "新疆", "博尔塔拉": "新疆", "巴音郭楞": "新疆", "阿克苏": "新疆",
        "克孜勒苏": "新疆", "喀什": "新疆", "和田": "新疆", "伊犁": "新疆", "塔城": "新疆",
        "阿勒泰": "新疆", "石河子": "新疆", "阿拉尔": "新疆", "图木舒克": "新疆",
        "五家渠": "新疆", "北屯": "新疆", "铁门关": "新疆", "双河": "新疆", "可克达拉": "新疆",
        "昆玉": "新疆", "胡杨河": "新疆", "新星": "新疆",
    }
    
    for city, prov in city_to_province.items():
        if city in channel_name:
            for category, _ in demo_order:
                if prov in category and ("频道" in category or "☘️" in category):
                    return category

    # 4. 关键词匹配
    for category, _ in demo_order:
        if "地方" in category or "频道" in category:
            if any(kw in channel_name.lower() for kw in ["新闻", "综合", "生活", "影视", "少儿", "公共", "经济", "文艺", "教育"]):
                return category

    # 5. 港澳台关键词匹配
    hk_tw_keywords = ["港", "澳", "台", "香港", "澳门", "台湾", "翡翠", "明珠", "凤凰", "tvb", "无线", "rthk", "hoy", "viu", "tvbs", "东森", "民视", "台视", "华视", "中视", "三立", "纬来", "靖天", "星空", "澳视"]
    for kw in hk_tw_keywords:
        if kw.lower() in channel_name.lower():
            for category, _ in demo_order:
                if "港" in category or "澳" in category or "台" in category or "港澳台" in category:
                    return category

    return None


def filter_and_order_by_demo(channels: list) -> tuple:
    """
    根据 demo.txt 筛选和排序频道。
    返回 (匹配的频道列表, 未匹配的频道列表)
    每个匹配的频道会添加字段：demo_category 和 demo_name
    """
    demo_order = parse_demo_order_with_categories()
    if not demo_order:
        logger.warning("⚠️ demo.txt 为空，跳过筛选")
        return channels, []

    name_to_channel = {ch["name"]: ch for ch in channels}
    matched = []
    unmatched = list(channels)
    matched_names = set()
    
    # 统计 CCTV-5+ 的匹配情况
    cctv5plus_matched = False
    cctv5_matched = False

    # 第一遍：精确/包含匹配 demo 中的频道名
    for category, demo_name in demo_order:
        # 尝试精确匹配
        if demo_name in name_to_channel:
            ch = name_to_channel[demo_name].copy()
            ch["demo_category"] = category
            ch["demo_name"] = demo_name
            if ch["name"] not in matched_names:
                matched.append(ch)
                matched_names.add(ch["name"])
                unmatched = [c for c in unmatched if c["name"] != ch["name"]]
                if demo_name == "CCTV-5+":
                    cctv5plus_matched = True
                    logger.info(f"🎯 精确匹配到 CCTV-5+")
                if demo_name == "CCTV-5":
                    cctv5_matched = True
                continue
        
        # 尝试模糊匹配
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
                if demo_name == "CCTV-5+":
                    cctv5plus_matched = True
                    logger.info(f"🎯 模糊匹配到 CCTV-5+: {ch['name']}")
                if demo_name == "CCTV-5":
                    cctv5_matched = True
                break
        
        if not found and demo_name in ["CCTV-5", "CCTV-5+"]:
            logger.warning(f"⚠️ 未找到匹配的频道: {demo_name}")

    # 输出匹配结果
    logger.info(f"📊 CCTV-5 匹配: {'成功' if cctv5_matched else '失败'}")
    logger.info(f"📊 CCTV-5+ 匹配: {'成功' if cctv5plus_matched else '失败'}")

    # 第二遍：处理剩余未匹配的频道，自动归类
    remaining = []
    for ch in unmatched:
        cat = classify_channel(ch)
        if cat in ["地方", "港澳台"]:
            demo_cat = find_matching_demo_category(ch["name"], demo_order)
            if demo_cat:
                ch_copy = ch.copy()
                ch_copy["demo_category"] = demo_cat
                ch_copy["demo_name"] = ch["name"]
                matched.append(ch_copy)
                matched_names.add(ch["name"])
                continue
        remaining.append(ch)

    logger.info(f"🎯 Demo 筛选：原始 {len(channels)} 个频道 -> 匹配 {len(matched)} 个频道，未匹配 {len(remaining)} 个")
    
    # 输出未匹配的样例
    if remaining:
        logger.info("未匹配频道样例（前10个）：")
        for ch in remaining[:10]:
            logger.info(f"  - {ch['name']}")

    return matched, remaining


def write_shai_file(unmatched_channels: list, matched_count: int, total_raw: int):
    """保存未匹配的频道列表到 shai.txt"""
    shai_path = OUTPUT_DIR / "shai.txt"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(shai_path, "w", encoding="utf-8") as f:
        f.write("# Demo筛选丢弃的频道\n")
        f.write(f"# 原始频道总数: {total_raw}\n")
        f.write(f"# Demo匹配成功: {matched_count}\n")
        f.write(f"# 丢弃数量: {len(unmatched_channels)}\n")
        f.write("# 格式: 频道名,URL\n\n")
        
        for ch in unmatched_channels:
            url = ch["urls"][0] if ch.get("urls") else ch["url"]
            f.write(f"{ch['name']},{url}\n")
    
    logger.info(f"📄 未匹配频道列表已保存到: {shai_path}")
