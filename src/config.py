# src/config.py
# 配置文件：源地址、分类关键词、全局参数

import os
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "output"
DEMO_FILE = ROOT_DIR / "demo.txt"
ALIAS_FILE = ROOT_DIR / "alias.txt"
BLACKLIST_FILE = ROOT_DIR / "blacklist.txt"
DATABASE_PATH = ROOT_DIR / "iptv_cache.db"

# CDN 加速前缀
GH_PROXY = "https://gh-proxy.19860519.xyz/"

# IPTV 源地址（使用 CDN 加速）
IPTV_SOURCES = [
    GH_PROXY + "https://raw.githubusercontent.com/iptv-org/iptv/refs/heads/master/streams/cn.m3u",
    GH_PROXY + "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt",
    GH_PROXY + "https://raw.githubusercontent.com/zzgpy1/iptv-api/master/output/result.txt",
    GH_PROXY + "https://raw.githubusercontent.com/dogwalkerg/IPTV-collect-tv-txt/main/live.txt",
    GH_PROXY + "https://raw.githubusercontent.com/zzgpy1/Collect-IPTV/main/best_sorted.m3u",
    GH_PROXY + "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u",
    GH_PROXY + "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    GH_PROXY + "https://raw.githubusercontent.com/Kimentanm/aptv/master/m3u/iptv.m3u",
    GH_PROXY + "https://raw.githubusercontent.com/zhanghanyun/backup/main/tv.m3u",
    GH_PROXY + "https://raw.githubusercontent.com/WeiZuoXu/IPTV/main/ipv6.m3u",
]

# 性能配置
MAX_WORKERS = int(os.getenv("MAX_WORKERS", 20))
TIMEOUT = int(os.getenv("TIMEOUT", 8))

# ffmpeg 配置
FFMPEG_ENABLE = os.getenv("FFMPEG_ENABLE", "true").lower() == "true"
FFMPEG_STRICT = os.getenv("FFMPEG_STRICT", "false").lower() == "true"
FFMPEG_WORKERS = min(MAX_WORKERS, 5)

# 重试配置
ENABLE_RETRY = os.getenv("ENABLE_RETRY", "true").lower() == "true"
RETRY_MAX_ATTEMPTS = 3
RETRY_BACKOFF_FACTOR = 2
RETRY_MAX_WAIT = 60

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# 输出分类顺序
OUTPUT_CATEGORY_ORDER = ["央视", "卫视", "地方", "港澳台"]

# 央视频道排序
CCTV_ORDER = [
    "CCTV-1", "CCTV-2", "CCTV-3", "CCTV-4", "CCTV-5", "CCTV-5+", "CCTV-6",
    "CCTV-7", "CCTV-8", "CCTV-9", "CCTV-10", "CCTV-11", "CCTV-12", "CCTV-13",
    "CCTV-14", "CCTV-15", "CCTV-16", "CCTV-17", "CCTV-4K", "CCTV-8K",
    "CCTV世界地理", "CCTV央视台球", "CCTV女性时尚", "CCTV怀旧剧场",
    "CCTV第一剧场", "CCTV风云足球", "CCTV老故事", "CGTN", "CGTN俄语",
    "CGTN法语", "CGTN纪录", "CGTN西语", "CGTN阿语"
]

# 输出文件名
M3U_FILE = "tv.m3u"
TXT_FILE = "tv.txt"

# 缓存时长（小时）
CACHE_HOURS = int(os.getenv("CACHE_HOURS", 24))

# 每个频道保留的源数量（用于自动切换）
MAX_SOURCES_PER_CHANNEL = int(os.getenv("MAX_SOURCES_PER_CHANNEL", 3))

# 功能开关
ENABLE_DEMO_FILTER = os.getenv("ENABLE_DEMO_FILTER", "true").lower() == "true"
ENABLE_ALIAS = os.getenv("ENABLE_ALIAS", "true").lower() == "true"
ENABLE_BLACKLIST = os.getenv("ENABLE_BLACKLIST", "true").lower() == "true"
DATABASE_ENABLE = os.getenv("DATABASE_ENABLE", "true").lower() == "true"

DEMO_MATCH_MODE = os.getenv("DEMO_MATCH_MODE", "contains")
PREFER_H264 = True

# HTTP 服务配置
WEB_SERVER_PORT = int(os.getenv("WEB_SERVER_PORT", 8080))
WEB_SERVER_HOST = os.getenv("WEB_SERVER_HOST", "0.0.0.0")

# 运行模式
RUN_MODE = os.getenv("RUN_MODE", "once")
SCHEDULE_INTERVAL = int(os.getenv("SCHEDULE_INTERVAL", 21600))
