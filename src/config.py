# src/config.py
# 兼容层：从 config_loader 导入配置，并导出所有传统变量名

from src.config_loader import config
from pathlib import Path

# 基础路径
ROOT_DIR = config.root_dir
DATA_DIR = config.data_dir
OUTPUT_DIR = config.output_dir

# 性能
MAX_WORKERS = config.max_workers
TIMEOUT = config.timeout
HTTP_TIMEOUT = config.http_timeout

# ffmpeg
FFMPEG_ENABLE = config.ffmpeg_enable
FFMPEG_MODE = config.ffmpeg_mode
FFPROBE_CACHE_HOURS = config.ffprobe_cache_hours
FFMPEG_WORKERS = config.max_workers  # 简单映射

# 缓存
CACHE_HOURS = config.cache_hours
CACHE_RAW_HOURS = config.cache_raw_hours
CACHE_SPEED_HOURS = config.cache_speed_hours

# 功能开关
ENABLE_DEMO_FILTER = config.enable_demo_filter
ENABLE_ALIAS = config.enable_alias
ENABLE_BLACKLIST = config.enable_blacklist
DATABASE_ENABLE = config.database_enable
ENABLE_INCREMENTAL_FETCH = config.enable_incremental_fetch
ENABLE_JSON_OUTPUT = config.enable_json_output
ENABLE_LITE_VERSION = config.enable_lite_version
ENABLE_EPG_OUTPUT = config.enable_epg_output
DEMO_MATCH_MODE = config.demo_match_mode

# 合并
MAX_SOURCES_PER_CHANNEL = config.max_sources_per_channel

# 测速与黑名单
MAX_RETRY_BEFORE_BLACKLIST = config.max_retry_before_blacklist
SLOW_SPEED_THRESHOLD = config.slow_speed_threshold
DOWNLOAD_CHUNK_SIZE = config.download_chunk_size

# 自治模式
AUTONOMOUS_MODE = config.autonomous_mode
AUTO_UPDATE_STABLE = config.auto_update_stable
AUTO_REPLACE_FAILED = config.auto_replace_failed
QUALITY_CHECK_INTERVAL = config.quality_check_interval
CANDIDATE_OBSERVATION_HOURS = config.candidate_observation_hours
CANDIDATE_MIN_SUCCESS = config.candidate_min_success
CANDIDATE_MIN_SUCCESS_RATE = config.candidate_min_success_rate
CANDIDATE_MAX_LATENCY = config.candidate_max_latency
AUTO_PROMOTE_THRESHOLD = config.auto_promote_threshold

# 健康预测
HEALTH_HISTORY_DAYS = config.health_history_days
PREDICT_THRESHOLD = config.predict_threshold

# 固定源优化
ENABLE_FIXED_OPTIMIZATION = config.enable_fixed_optimization
FIXED_OPTIMIZATION_THRESHOLD = config.fixed_optimization_threshold

# 源列表
IPTV_SOURCES = config.iptv_sources
RAW_SOURCES = config.raw_sources
DIRECT_SOURCES = config.direct_sources

# 代理
ENABLE_GITHUB_PROXY = config.enable_github_proxy
GITHUB_RAW_PROXIES = config.github_raw_proxies
GITHUB_PROXY_TIMEOUT = config.github_proxy_timeout
PROXY = ""  # 保留

# 重试
ENABLE_RETRY = True
RETRY_MAX_ATTEMPTS = 3
RETRY_BACKOFF_FACTOR = 2
RETRY_MAX_WAIT = 60

# 请求头
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# 文件路径（兼容旧代码）
DEMO_FILE = ROOT_DIR / "demo.txt"
ALIAS_FILE = ROOT_DIR / "alias.txt"
BLACKLIST_FILE = ROOT_DIR / "blacklist.txt"
DATABASE_PATH = DATA_DIR / "iptv_cache.db"

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

# 省份和港澳台关键词（从 constants 导入）
from src.constants import PROVINCES, HK_MACAU_TAIWAN_KEYWORDS
PROVINCES = PROVINCES
HK_MACAU_TAIWAN_KEYWORDS = HK_MACAU_TAIWAN_KEYWORDS
