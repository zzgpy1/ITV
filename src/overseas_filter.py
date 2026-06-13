# src/overseas_filter.py
"""国外频道筛选和分类模块 - 优化版：仅按国家分类，提高匹配精度"""

import re
from collections import defaultdict
from typing import List, Dict, Tuple
from pathlib import Path

from src.config import OUTPUT_DIR
from src.logger import logger

# ========== 国家/地区精确匹配规则（优先级从高到低）==========
# 格式: (显示名称, 匹配关键词列表)
# 注意：更具体的关键词放在前面，避免误匹配

COUNTRY_RULES = [
    # 中国（排除，国内频道已单独处理）
    ("中国", ["cn", "china", "chinese", "cgtn"]),
    
    # 日本 - 精确匹配
    ("日本", [
        "jp", "japan", "japanese", 
        "nhk", "fuji tv", "tv asahi", "tbs", "ntv", "tokyo mx",
        "wowow", "bs11", "bs asahi", "bs-tbs", "bs japan",
        "日テレ", "テレビ朝日", "tbsテレビ", "テレビ東京", "フジテレビ"
    ]),
    
    # 韩国 - 精确匹配
    ("韩国", [
        "kr", "korea", "korean", 
        "kbs", "mbc", "sbs", "tvN", "jtbc", "arirang",
        "韩国放送", "文化放送", "首尔放送", "edaily"
    ]),
    
    # 美国
    ("美国", [
        "us", "usa", "united states", "america", "american",
        "abc", "nbc", "cbs", "cnn", "fox news", "msnbc",
        "hbo", "discovery", "national geographic", "history",
        "a&e", "animal planet", "tlc", "paramount", "showtime",
        "starz", "amc", "syfy", "usa network", "tbs", "tnt",
        "espn", "fox sports", "nfl", "nba tv", "mlb network"
    ]),
    
    # 英国
    ("英国", [
        "uk", "united kingdom", "britain", "british",
        "bbc", "sky news", "itv", "channel 4", "channel 5",
        "sky sports", "bt sport", "euro sport"
    ]),
    
    # 法国
    ("法国", [
        "fr", "france", "french",
        "tf1", "france 2", "france 3", "france 4", "france 5",
        "m6", "canal+", "bfm tv", "french"
    ]),
    
    # 德国
    ("德国", [
        "de", "germany", "german",
        "ard", "zdf", "rtl", "pro7", "sat.1", "vox",
        "n-tv", "welt", "german"
    ]),
    
    # 俄罗斯
    ("俄罗斯", [
        "ru", "russia", "russian",
        "rt ", "russia today", "ntv", "tnt", "russian"
    ]),
    
    # 意大利
    ("意大利", [
        "it", "italy", "italian",
        "rai", "mediaset", "la7", "italian"
    ]),
    
    # 西班牙
    ("西班牙", [
        "es", "spain", "spanish",
        "rtve", "antena 3", "la sexta", "cuatro", "telecinco",
        "spanish", "español"
    ]),
    
    # 印度
    ("印度", [
        "in", "india", "indian",
        "zee", "star plus", "sony tv", "colors", "ndtv",
        "zee tv", "star bharat", "sab tv", "indian"
    ]),
    
    # 澳大利亚
    ("澳大利亚", [
        "au", "australia", "australian",
        "abc australia", "sbs", "seven network", "nine network",
        "10 network", "australian"
    ]),
    
    # 加拿大
    ("加拿大", [
        "ca", "canada", "canadian",
        "cbc", "ctv", "global tv", "citytv", "canadian"
    ]),
    
    # 巴西
    ("巴西", [
        "br", "brazil", "brazilian",
        "globo", "record tv", "band", "sbt", "brazilian"
    ]),
    
    # 中东/阿拉伯
    ("中东", [
        "ae", "saudi", "qatar", "dubai", "abudhabi",
        "al jazeera", "beIN", "middle east", "arab",
        "mbc", "osn", "rotana", "saudi"
    ]),
    
    # 东南亚
    ("泰国", ["th", "thailand", "thai", "channel 3", "channel 7", "workpoint"]),
    ("越南", ["vn", "vietnam", "vietnamese", "vtv", "htv"]),
    ("马来西亚", ["my", "malaysia", "malay", "astro", "rtm", "tv3"]),
    ("印度尼西亚", ["id", "indonesia", "indonesian", "metro tv", "tvri", "rcti"]),
    ("菲律宾", ["ph", "philippines", "filipino", "abs-cbn", "gma", "tv5"]),
    
    # 欧洲其他
    ("荷兰", ["nl", "netherlands", "dutch", "npo", "rtl", "dutch"]),
    ("比利时", ["be", "belgium", "belgian", "vrt", "rtbf"]),
    ("瑞士", ["ch", "switzerland", "swiss", "srf", "rts", "rsi"]),
    ("奥地利", ["at", "austria", "austrian", "orf"]),
    ("瑞典", ["se", "sweden", "swedish", "svt", "tv4"]),
    ("挪威", ["no", "norway", "norwegian", "nrk", "tv2"]),
    ("丹麦", ["dk", "denmark", "danish", "dr", "tv2"]),
    ("芬兰", ["fi", "finland", "finnish", "yle"]),
    ("波兰", ["pl", "poland", "polish", "tvp", "polsat"]),
    ("捷克", ["cz", "czech", "czech republic", "ct", "prima"]),
    ("匈牙利", ["hu", "hungary", "hungarian", "m1", "tv2"]),
    ("希腊", ["gr", "greece", "greek", "ert", "skai", "ant1"]),
    ("土耳其", ["tr", "turkey", "turkish", "trt", "kanal d", "atv"]),
    
    # 非洲
    ("南非", ["za", "south africa", "dstv", "sabc", "etv"]),
    ("尼日利亚", ["ng", "nigeria", "nigerian", "channels tv", "aittv"]),
    
    # 拉丁美洲
    ("墨西哥", ["mx", "mexico", "mexican", "televisa", "tv azteca"]),
    ("阿根廷", ["ar", "argentina", "argentinian", "telefe", "el trece"]),
    ("智利", ["cl", "chile", "chilean", "mega", "tvn", "chilevision"]),
    ("哥伦比亚", ["co", "colombia", "colombian", "caracol", "rcn"]),
    
    # 其他/泛区域
    ("欧洲", ["eu", "europe", "european", "euronews"]),
    ("国际", ["international", "global", "world", "worldwide"]),
]

# 需要排除的关键词（避免误匹配）
EXCLUDE_KEYWORDS = [
    "cctv", "央视", "中央", "卫视", "电视台", "综合", "频道",
    "广东", "浙江", "江苏", "北京", "上海", "湖南", "湖北",
]


def detect_country_accurate(channel_name: str) -> str:
    """精确检测频道所属国家（优先级匹配）"""
    name_lower = channel_name.lower()
    
    # 首先排除国内频道
    for exclude in EXCLUDE_KEYWORDS:
        if exclude in name_lower:
            return "国内频道"
    
    # 按优先级匹配
    for country, keywords in COUNTRY_RULES:
        for kw in keywords:
            # 精确匹配词边界（避免部分匹配）
            patterns = [
                r'\b' + re.escape(kw) + r'\b',  # 完整单词
                r'\b' + re.escape(kw) + r's\b',  # 复数形式
                r'^' + re.escape(kw) + r'\b',    # 开头
            ]
            for pattern in patterns:
                if re.search(pattern, name_lower, re.IGNORECASE):
                    return country
    
    return "其他地区"


def is_domestic_channel(channel_name: str) -> bool:
    """判断是否为国内频道"""
    name = channel_name.lower()
    
    # 中文关键词
    if any(kw in name for kw in ["央视", "cctv", "卫视", "电视台", "综合", "频道"]):
        # 但排除 CGTN（国际频道）
        if "cgtn" in name:
            return False
        return True
    
    # 国内省份和城市
    provinces = [
        "北京", "上海", "天津", "重庆", "广东", "浙江", "江苏", "山东", "河南",
        "湖北", "湖南", "四川", "福建", "安徽", "辽宁", "陕西", "河北", "江西",
        "黑龙江", "吉林", "山西", "云南", "贵州", "甘肃", "海南", "青海", "宁夏",
        "新疆", "西藏", "广西", "内蒙古", "香港", "澳门", "台湾"
    ]
    if any(prov in name for prov in provinces):
        return True
    
    return False


def classify_overseas_channels(unmatched_channels: List[Dict]) -> Dict[str, List[Dict]]:
    """对未匹配的频道进行分类（仅按国家分类）"""
    classified = defaultdict(list)
    
    for ch in unmatched_channels:
        name = ch.get("name", "")
        
        # 跳过国内频道
        if is_domestic_channel(name):
            continue
        
        # 检测国家
        country = detect_country_accurate(name)
        
        # 跳过被误判为国内的频道
        if country == "国内频道":
            continue
        
        # 存储分类信息
        ch["country"] = country
        classified[country].append(ch)
    
    # 每个国家内按频道名 A-Z 排序
    for country in classified:
        classified[country].sort(key=lambda x: x["name"].lower())
    
    # 按国家名称排序
    return dict(sorted(classified.items()))


def generate_overseas_output(classified_channels: Dict[str, List[Dict]], output_dir: Path = OUTPUT_DIR):
    """生成国外频道输出文件（仅按国家分类）"""
    if not classified_channels:
        logger.info("没有国外频道需要输出")
        return
    
    total_channels = sum(len(ch) for ch in classified_channels.values())
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. 生成 M3U 文件（group-title 仅使用国家名）
    m3u_path = output_dir / "guowai.m3u"
    with open(m3u_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        f.write("# 国外频道合集 (Overseas Channels)\n")
        f.write(f"# 共 {total_channels} 个频道\n")
        f.write("# 按国家/地区分类，频道名 A-Z 排序\n\n")
        
        for country, channels in classified_channels.items():
            f.write(f"\n# ========== {country} ({len(channels)}个频道) ==========\n")
            for ch in channels:
                url = ch.get("urls", [ch.get("url")])[0]
                # group-title 仅使用国家名
                f.write(f'#EXTINF:-1 group-title="{country}",{ch["name"]}\n{url}\n')
    
    logger.info(f"✅ 国外频道 M3U 已生成: {m3u_path}")
    
    # 2. 生成 TXT 文件（按国家分节）
    txt_path = output_dir / "guowai.txt"
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write("# 国外频道列表 (按国家分类)\n")
        f.write(f"# 共 {total_channels} 个频道\n")
        f.write("# 格式: 频道名,URL\n\n")
        
        for country, channels in classified_channels.items():
            f.write(f"\n{country}频道,#genre#\n")
            for ch in channels:
                url = ch.get("urls", [ch.get("url")])[0]
                f.write(f"{ch['name']},{url}\n")
    
    logger.info(f"✅ 国外频道 TXT 已生成: {txt_path}")
    
    # 3. 生成 JSON 统计文件
    json_path = output_dir / "guowai_stats.json"
    import json
    import datetime
    
    stats = {
        "total": total_channels,
        "generated": datetime.datetime.now().isoformat(),
        "by_country": {country: len(channels) for country, channels in classified_channels.items()}
    }
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    
    logger.info(f"✅ 国外频道统计已生成: {json_path}")
    
    # 4. 打印统计信息
    logger.info("\n🌍 国外频道统计:")
    for country, channels in classified_channels.items():
        logger.info(f"  {country}: {len(channels)} 个频道")
    
    # 打印前10个日本频道的样例（用于验证）
    if "日本" in classified_channels:
        logger.info("\n🇯🇵 日本频道样例（前10个）:")
        for ch in classified_channels["日本"][:10]:
            logger.info(f"    - {ch['name']}")


def process_overseas_channels(unmatched_channels: List[Dict], output_dir: Path = OUTPUT_DIR) -> Dict:
    """处理国外频道：分类并输出"""
    if not unmatched_channels:
        logger.info("没有未匹配的频道")
        return {}
    
    logger.info(f"🌍 正在处理 {len(unmatched_channels)} 个未匹配频道...")
    
    # 分类
    classified = classify_overseas_channels(unmatched_channels)
    
    # 输出
    generate_overseas_output(classified, output_dir)
    
    return classified
