# src/constants.py
"""全局常量定义"""

# 分类名称（用于 classifier 和输出）
CATEGORY_CCTV = "央视"
CATEGORY_SATELLITE = "卫视"
CATEGORY_LOCAL = "地方"
CATEGORY_HKMT = "港澳台"
CATEGORY_OTHER = "其他"
CATEGORY_SPORTS = "体育赛事"

# 输出文件分类顺序（与 demo.txt 对应）
OUTPUT_CATEGORY_ORDER = [CATEGORY_CCTV, CATEGORY_SATELLITE, CATEGORY_LOCAL, CATEGORY_HKMT]

# 央视标准顺序（用于排序）
CCTV_ORDER = [
    "CCTV-1", "CCTV-2", "CCTV-3", "CCTV-4", "CCTV-5", "CCTV-5+", "CCTV-6",
    "CCTV-7", "CCTV-8", "CCTV-9", "CCTV-10", "CCTV-11", "CCTV-12", "CCTV-13",
    "CCTV-14", "CCTV-15", "CCTV-16", "CCTV-17", "CCTV-4K", "CCTV-8K",
    "CCTV世界地理", "CCTV央视台球", "CCTV女性时尚", "CCTV怀旧剧场",
    "CCTV第一剧场", "CCTV风云足球", "CCTV老故事", "CGTN", "CGTN俄语",
    "CGTN法语", "CGTN纪录", "CGTN西语", "CGTN阿语"
]

# 省份列表（用于分类和地区检测）
PROVINCES = [
    "北京", "天津", "上海", "重庆",
    "河北", "山西", "辽宁", "吉林", "黑龙江",
    "江苏", "浙江", "安徽", "福建", "江西", "山东",
    "河南", "湖北", "湖南", "广东", "海南", "四川",
    "贵州", "云南", "陕西", "甘肃", "青海", "台湾",
    "内蒙古", "广西", "西藏", "宁夏", "新疆",
    "香港", "澳门"
]

# 港澳台关键词（用于分类）
HK_MACAU_TAIWAN_KEYWORDS = [
    "港", "澳", "台", "香港", "澳门", "台湾", "翡翠", "明珠", "凤凰", "tvb", "无线",
    "rthk", "hoy", "viu", "tvbs", "东森", "民视", "台视", "华视", "中视", "三立",
    "纬来", "靖天", "星空", "澳视", "澳门卫视", "香港卫视", "凤凰卫视", "TVB",
    "中天", "年代", "壹电视", "非凡", "寰宇", "华娱", "澳亚", "澳广视", "香港开电视",
    "公视", "台视新闻", "华视新闻", "中视新闻", "民视新闻", "TVBS新闻", "东森新闻",
    "中天新闻", "三立新闻", "非凡新闻", "寰宇新闻", "华视综合", "中视综合", "台视综合"
]

# 文件路径（由 settings 决定，但为了兼容旧代码，保持 config 中的变量）
# 这些在 config.py 中定义，此处不重复
