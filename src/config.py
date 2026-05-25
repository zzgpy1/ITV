# src/config.py
# 配置文件：源地址、分类关键词、全局参数、数据库配置

import os
from pathlib import Path

# ==================== 路径配置 ====================
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "output"
DEMO_FILE = ROOT_DIR / "demo.txt"
ALIAS_FILE = ROOT_DIR / "alias.txt"
BLACKLIST_FILE = ROOT_DIR / "blacklist.txt"
IP_DATABASE_FILE = ROOT_DIR / "qqwry.dat"
DATABASE_PATH = ROOT_DIR / "iptv_cache.db"

# ==================== IPTV 源列表 ====================
IPTV_SOURCES = [
    "https://raw.githubusercontent.com/iptv-org/iptv/gh-pages/countries/cn.m3u",
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/cn.m3u",
    "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt",
    "https://raw.githubusercontent.com/zzgpy1/Collect-IPTV/main/best_sorted.m3u",
    "https://raw.githubusercontent.com/zzgpy1/UniIPTV/gh-pages/tv.m3u",
    "https://tv.19860519.xyz/abc123",
]

# ==================== 性能配置 ====================
MAX_WORKERS = int(os.getenv("MAX_WORKERS", 10))
TIMEOUT = int(os.getenv("TIMEOUT", 10))

# ==================== 验证配置 ====================
FFMPEG_ENABLE = os.getenv("FFMPEG_ENABLE", "true").lower() == "true"
FFMPEG_STRICT = os.getenv("FFMPEG_STRICT", "false").lower() == "true"
ENABLE_RETRY = os.getenv("ENABLE_RETRY", "true").lower() == "true"

# ==================== HTTP 请求头 ====================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# ==================== 输出分类顺序 ====================
OUTPUT_CATEGORY_ORDER = ["央视", "卫视", "地方", "港澳台"]

# ==================== 央视频道固定顺序 ====================
CCTV_ORDER = [
    "CCTV-1", "CCTV-2", "CCTV-3", "CCTV-4", "CCTV-5", "CCTV-5+", "CCTV-6",
    "CCTV-7", "CCTV-8", "CCTV-9", "CCTV-10", "CCTV-11", "CCTV-12", "CCTV-13",
    "CCTV-14", "CCTV-15", "CCTV-16", "CCTV-17", "CCTV-4K", "CCTV-8K",
    "CCTV世界地理", "CCTV央视台球", "CCTV女性时尚", "CCTV怀旧剧场",
    "CCTV第一剧场", "CCTV风云足球", "CCTV老故事", "CGTN", "CGTN俄语",
    "CGTN法语", "CGTN纪录", "CGTN西语", "CGTN阿语"
]

# ==================== 输出配置 ====================
M3U_FILE = "tv.m3u"
TXT_FILE = "tv.txt"

# ==================== 重试配置 ====================
RETRY_MAX_ATTEMPTS = 3
RETRY_BACKOFF_FACTOR = 2
RETRY_MAX_WAIT = 60

# ==================== IP 解析与地域筛选 ====================
ENABLE_IP_RESOLVE = os.getenv("ENABLE_IP_RESOLVE", "true").lower() == "true"
ENABLE_REGION_FILTER = os.getenv("ENABLE_REGION_FILTER", "false").lower() == "true"
PREFERRED_LOCATION = os.getenv("PREFERRED_LOCATION", "")
PREFERRED_ISP = os.getenv("PREFERRED_ISP", "")

# ==================== 数据库配置 ====================
DATABASE_ENABLE = os.getenv("DATABASE_ENABLE", "true").lower() == "true"
DATABASE_TABLE = "channel_cache"
CACHE_EXPIRY_SECONDS = 3 * 24 * 3600   # 缓存有效期3天

# ==================== 频道合并配置 ====================
MAX_SOURCES_PER_CHANNEL = 5
PREFER_H264 = True
PREFER_LOCAL_ISP = True

# ==================== 增强过滤配置 ====================
ENABLE_DEMO_FILTER = os.getenv("ENABLE_DEMO_FILTER", "true").lower() == "true"
ENABLE_ALIAS = os.getenv("ENABLE_ALIAS", "true").lower() == "true"
ENABLE_BLACKLIST = os.getenv("ENABLE_BLACKLIST", "true").lower() == "true"

# ==================== Demo 匹配模式 ====================
DEMO_MATCH_MODE = "exact"   # 可选 "exact" 或 "contains"

# 缓存有效期（秒），用于判断数据库中的测速结果是否过期
CACHE_EXPIRY_SECONDS = 7 * 24 * 3600   # 7天
