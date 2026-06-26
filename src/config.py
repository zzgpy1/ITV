# src/config.py
# 配置文件：源地址、分类关键词、全局参数

import os
import sys
from pathlib import Path


def get_base_dir():
    """获取应用根目录（支持 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        # 打包环境，exe 所在路径
        return Path(sys.executable).parent
    else:
        # 开发环境，项目根目录
        return Path(__file__).parent.parent


ROOT_DIR = get_base_dir()
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "output"
DEMO_FILE = ROOT_DIR / "demo.txt"
ALIAS_FILE = ROOT_DIR / "alias.txt"
BLACKLIST_FILE = ROOT_DIR / "blacklist.txt"
DATABASE_PATH = ROOT_DIR / "iptv_cache.db"


def is_github_actions() -> bool:
    """检测是否在 GitHub Actions 环境中运行"""
    return os.getenv("GITHUB_ACTIONS") == "true" or os.getenv("CI") == "true"


def is_docker() -> bool:
    """检测是否在 Docker 容器中运行"""
    return os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv")

def get_base_dir():
    """获取应用根目录（支持 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后，数据文件在 sys._MEIPASS 目录下
        if hasattr(sys, '_MEIPASS'):
            return Path(sys._MEIPASS)
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.parent
        
def get_cdn_proxy() -> str:
    if is_github_actions():
        return ""
    return "https://gh-proxy.19860519.xyz/"


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

PROXY = get_cdn_proxy()
IPTV_SOURCES = []

for src in RAW_SOURCES:
    if PROXY:
        IPTV_SOURCES.append(PROXY + src)
    else:
        IPTV_SOURCES.append(src)

IPTV_SOURCES.extend(DIRECT_SOURCES)

if is_github_actions():
    print("🏃 检测到 GitHub Actions 环境，使用直接访问模式")
elif is_docker():
    print("🐳 检测到 Docker 环境，启用 CDN 加速")
else:
    print("💻 检测到本地环境，启用 CDN 加速")

print(f"📡 共配置 {len(IPTV_SOURCES)} 个源")

# 性能配置
MAX_WORKERS = int(os.getenv("MAX_WORKERS", 20))
TIMEOUT = int(os.getenv("TIMEOUT", 10))

# ffmpeg 配置
FFMPEG_ENABLE = os.getenv("FFMPEG_ENABLE", "true").lower() == "true"
FFMPEG_STRICT = os.getenv("FFMPEG_STRICT", "true").lower() == "true"
FFMPEG_WORKERS = min(MAX_WORKERS, 5)

# ffmpeg 模式
FFMPEG_MODE = os.getenv("FFMPEG_MODE", "deep")
FFPROBE_CACHE_HOURS = int(os.getenv("FFPROBE_CACHE_HOURS", 168))

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

# 每个频道保留的源数量
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

# ========== 缓存优化配置 ==========
CACHE_RAW_HOURS = int(os.getenv("CACHE_RAW_HOURS", 48))
CACHE_SPEED_HOURS = int(os.getenv("CACHE_SPEED_HOURS", 24))
ENABLE_INCREMENTAL_FETCH = os.getenv("ENABLE_INCREMENTAL_FETCH", "true").lower() == "true"

# ========== EPG 配置 ==========
ENABLE_EPG_INJECTION = os.getenv("ENABLE_EPG_INJECTION", "true").lower() == "true"
EPG_CACHE_DAYS = int(os.getenv("EPG_CACHE_DAYS", 7))

# ========== 输出格式配置 ==========
ENABLE_JSON_OUTPUT = os.getenv("ENABLE_JSON_OUTPUT", "true").lower() == "true"
ENABLE_LITE_VERSION = os.getenv("ENABLE_LITE_VERSION", "true").lower() == "true"
ENABLE_EPG_OUTPUT = os.getenv("ENABLE_EPG_OUTPUT", "true").lower() == "true"

# ========== 自治模式配置 ==========
AUTONOMOUS_MODE = os.getenv("AUTONOMOUS_MODE", "true").lower() == "true"
AUTO_UPDATE_STABLE = os.getenv("AUTO_UPDATE_STABLE", "true").lower() == "true"
AUTO_REPLACE_FAILED = os.getenv("AUTO_REPLACE_FAILED", "true").lower() == "true"
QUALITY_CHECK_INTERVAL = int(os.getenv("QUALITY_CHECK_INTERVAL", 24))
CANDIDATE_OBSERVATION_HOURS = int(os.getenv("CANDIDATE_OBSERVATION_HOURS", 24))
CANDIDATE_MIN_SUCCESS = int(os.getenv("CANDIDATE_MIN_SUCCESS", 10))
CANDIDATE_MIN_SUCCESS_RATE = float(os.getenv("CANDIDATE_MIN_SUCCESS_RATE", 0.8))
CANDIDATE_MAX_LATENCY = int(os.getenv("CANDIDATE_MAX_LATENCY", 2000))

# ========== 动态并发配置 ==========
DYNAMIC_CONCURRENCY = os.getenv("DYNAMIC_CONCURRENCY", "true").lower() == "true"
MIN_WORKERS = int(os.getenv("MIN_WORKERS", 5))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", 20))

# ========== 布隆过滤器配置 ==========
ENABLE_BLOOM_FILTER = os.getenv("ENABLE_BLOOM_FILTER", "true").lower() == "true"
BLOOM_FILTER_CAPACITY = int(os.getenv("BLOOM_FILTER_CAPACITY", 100000))

# ========== Web 管理界面配置 ==========
WEB_UI_ENABLE = os.getenv("WEB_UI_ENABLE", "true").lower() == "true"
WEB_UI_TITLE = os.getenv("WEB_UI_TITLE", "IPTV 智能管理面板")

# ========== GitHub 代理配置（用于 proxy_utils.py） ==========
ENABLE_GITHUB_PROXY = os.getenv("ENABLE_GITHUB_PROXY", "false").lower() == "true"
GITHUB_PROXY_TIMEOUT = int(os.getenv("GITHUB_PROXY_TIMEOUT", 15))
GITHUB_RAW_PROXIES = [
    "https://ghproxy.net/",
    "https://gh-proxy.19860519.xyz/",
    "https://ghproxy.19860519.xyz/",
]

# 打印自治模式状态
if AUTONOMOUS_MODE:
    print("🤖 自治模式已启用")
    print(f"   - 自动更新稳定版: {AUTO_UPDATE_STABLE}")
    print(f"   - 自动替换失效源: {AUTO_REPLACE_FAILED}")
    print(f"   - 质量检查间隔: {QUALITY_CHECK_INTERVAL}小时")
    print(f"   - 候选观察期: {CANDIDATE_OBSERVATION_HOURS}小时")
    print(f"   - 最少成功次数: {CANDIDATE_MIN_SUCCESS}")
    print(f"   - 最低成功率: {CANDIDATE_MIN_SUCCESS_RATE}")
    print(f"   - 最大延迟: {CANDIDATE_MAX_LATENCY}ms")
