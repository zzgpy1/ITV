# src/config.py
import os
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "output"
DEMO_FILE = ROOT_DIR / "demo.txt"
ALIAS_FILE = ROOT_DIR / "alias.txt"
BLACKLIST_FILE = ROOT_DIR / "blacklist.txt"
DATABASE_PATH = ROOT_DIR / "iptv_cache.db"

# ========== IPTV 源地址配置 ==========
RAW_SOURCES = [
    "https://raw.githubusercontent.com/iptv-org/iptv/refs/heads/master/streams/cn.m3u",
    "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt",
    "https://raw.githubusercontent.com/zzgpy1/iptv-api/master/output/result.txt",
    "https://raw.githubusercontent.com/dogwalkerg/IPTV-collect-tv-txt/main/live.txt",
    "https://raw.githubusercontent.com/zzgpy1/Collect-IPTV/main/best_sorted.m3u",
    "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u",
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    "https://raw.githubusercontent.com/Kimentanm/aptv/master/m3u/iptv.m3u",
]
DIRECT_SOURCES = [
    "https://tv.19860519.xyz/abc123",
]

# ========== GitHub 代理配置（用于拉取 raw.githubusercontent.com 源） ==========
ENABLE_GITHUB_PROXY = os.getenv("ENABLE_GITHUB_PROXY", "false").lower() == "true"
GITHUB_RAW_PROXIES = [
    "https://ghproxy.net/",
    "https://gh-proxy.19860519.xyz/",
    "https://raw.kkgithub.com/",
]
GITHUB_PROXY_TIMEOUT = 15

# 简单的代理支持（可在 GitHub Actions 中禁用）
PROXY = os.getenv("GITHUB_ACTIONS", "false") == "true" and "" or "https://gh-proxy.19860519.xyz/"
IPTV_SOURCES = []
for src in RAW_SOURCES:
    IPTV_SOURCES.append(PROXY + src if PROXY else src)
IPTV_SOURCES.extend(DIRECT_SOURCES)
IPTV_SOURCES.extend(JP_SOURCES)

# ========== 性能配置 ==========
MAX_WORKERS = int(os.getenv("MAX_WORKERS", 20))
TIMEOUT = int(os.getenv("TIMEOUT", 8))

# ffmpeg 配置
FFMPEG_ENABLE = os.getenv("FFMPEG_ENABLE", "true").lower() == "true"
FFMPEG_MODE = os.getenv("FFMPEG_MODE", "deep")
FFPROBE_CACHE_HOURS = int(os.getenv("FFPROBE_CACHE_HOURS", 168))
FFMPEG_WORKERS = min(MAX_WORKERS, 5)

# 重试配置
ENABLE_RETRY = True
RETRY_MAX_ATTEMPTS = 3
RETRY_BACKOFF_FACTOR = 2
RETRY_MAX_WAIT = 60

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# 输出分类顺序
OUTPUT_CATEGORY_ORDER = ["央视", "卫视", "地方", "港澳台"]
CCTV_ORDER = [
    "CCTV-1", "CCTV-2", "CCTV-3", "CCTV-4", "CCTV-5", "CCTV-5+", "CCTV-6",
    "CCTV-7", "CCTV-8", "CCTV-9", "CCTV-10", "CCTV-11", "CCTV-12", "CCTV-13",
    "CCTV-14", "CCTV-15", "CCTV-16", "CCTV-17", "CCTV-4K", "CCTV-8K",
    "CCTV世界地理", "CCTV央视台球", "CCTV女性时尚", "CCTV怀旧剧场",
    "CCTV第一剧场", "CCTV风云足球", "CCTV老故事", "CGTN", "CGTN俄语",
    "CGTN法语", "CGTN纪录", "CGTN西语", "CGTN阿语"
]

M3U_FILE = "tv.m3u"
TXT_FILE = "tv.txt"

CACHE_HOURS = int(os.getenv("CACHE_HOURS", 24))
MAX_SOURCES_PER_CHANNEL = int(os.getenv("MAX_SOURCES_PER_CHANNEL", 3))

ENABLE_DEMO_FILTER = os.getenv("ENABLE_DEMO_FILTER", "true").lower() == "true"
ENABLE_ALIAS = os.getenv("ENABLE_ALIAS", "true").lower() == "true"
ENABLE_BLACKLIST = os.getenv("ENABLE_BLACKLIST", "true").lower() == "true"
DATABASE_ENABLE = os.getenv("DATABASE_ENABLE", "true").lower() == "true"
DEMO_MATCH_MODE = os.getenv("DEMO_MATCH_MODE", "contains")

CACHE_RAW_HOURS = int(os.getenv("CACHE_RAW_HOURS", 48))
CACHE_SPEED_HOURS = int(os.getenv("CACHE_SPEED_HOURS", 24))
ENABLE_INCREMENTAL_FETCH = os.getenv("ENABLE_INCREMENTAL_FETCH", "true").lower() == "true"

ENABLE_JSON_OUTPUT = os.getenv("ENABLE_JSON_OUTPUT", "true").lower() == "true"
ENABLE_LITE_VERSION = os.getenv("ENABLE_LITE_VERSION", "true").lower() == "true"
ENABLE_EPG_OUTPUT = os.getenv("ENABLE_EPG_OUTPUT", "true").lower() == "true"

# 自治模式
AUTONOMOUS_MODE = os.getenv("AUTONOMOUS_MODE", "false").lower() == "true"
AUTO_UPDATE_STABLE = os.getenv("AUTO_UPDATE_STABLE", "true").lower() == "true"
AUTO_REPLACE_FAILED = os.getenv("AUTO_REPLACE_FAILED", "true").lower() == "true"
QUALITY_CHECK_INTERVAL = int(os.getenv("QUALITY_CHECK_INTERVAL", 24))
CANDIDATE_OBSERVATION_HOURS = int(os.getenv("CANDIDATE_OBSERVATION_HOURS", 24))
CANDIDATE_MIN_SUCCESS = int(os.getenv("CANDIDATE_MIN_SUCCESS", 10))
CANDIDATE_MIN_SUCCESS_RATE = float(os.getenv("CANDIDATE_MIN_SUCCESS_RATE", 0.8))
CANDIDATE_MAX_LATENCY = int(os.getenv("CANDIDATE_MAX_LATENCY", 2000))

# ========== 测速与黑名单 ==========
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", 8))
MAX_RETRY_BEFORE_BLACKLIST = 2
SLOW_SPEED_THRESHOLD = 3000

# ========== 自治模式 ==========
AUTONOMOUS_MODE = os.getenv("AUTONOMOUS_MODE", "false").lower() == "true"
AUTO_UPDATE_STABLE = os.getenv("AUTO_UPDATE_STABLE", "true").lower() == "true"
AUTO_REPLACE_FAILED = os.getenv("AUTO_REPLACE_FAILED", "true").lower() == "true"
QUALITY_CHECK_INTERVAL = int(os.getenv("QUALITY_CHECK_INTERVAL", 24))
CANDIDATE_OBSERVATION_HOURS = int(os.getenv("CANDIDATE_OBSERVATION_HOURS", 24))
CANDIDATE_MIN_SUCCESS = int(os.getenv("CANDIDATE_MIN_SUCCESS", 10))
CANDIDATE_MIN_SUCCESS_RATE = float(os.getenv("CANDIDATE_MIN_SUCCESS_RATE", 0.8))
CANDIDATE_MAX_LATENCY = int(os.getenv("CANDIDATE_MAX_LATENCY", 2000))

# ========== 补充自治及数据库参数 ==========
AUTO_PROMOTE_THRESHOLD = int(os.getenv("AUTO_PROMOTE_THRESHOLD", 3))
CANDIDATE_MAX_AGE_HOURS = int(os.getenv("CANDIDATE_MAX_AGE_HOURS", 72))
ENABLE_BLOOM_FILTER = os.getenv("ENABLE_BLOOM_FILTER", "true").lower() == "true"
BLOOM_FILTER_CAPACITY = int(os.getenv("BLOOM_FILTER_CAPACITY", 100000))

# ========== 健康度预测 ==========
HEALTH_HISTORY_DAYS = int(os.getenv("HEALTH_HISTORY_DAYS", 30))
PREDICT_THRESHOLD = float(os.getenv("PREDICT_THRESHOLD", 0.6))

# 测速与黑名单
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", 8))
MAX_RETRY_BEFORE_BLACKLIST = 2
SLOW_SPEED_THRESHOLD = 3000

HEALTH_HISTORY_DAYS = 30
PREDICT_THRESHOLD = 0.6
