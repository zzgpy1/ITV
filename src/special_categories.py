# src/special_categories.py
"""特定分类采集模块 - 从 abc123 源采集指定类别，并验证频道可用性（增强版）"""

import re
import asyncio
import aiohttp
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from src.logger import logger
from src.classifier import PROVINCES

# ========== 需要采集的分类关键词及匹配规则 ==========
TARGET_CATEGORIES = [
    "广播",
    "韩国女团",
    "电影",
    "电视剧",
    "动漫",
    "体育竞赛",
    "音乐吧",          # 匹配“经典老歌”、“经典歌曲”
    "热门歌曲",        # 匹配“音乐”、“歌曲”、“流行”等
    "戏曲",
    "美食",
    "动感舞曲",
    "广场舞"
]

# ========== 分类显示名称映射 ==========
CATEGORY_DISPLAY_NAME = {
    "广播": "📻 网络电台",
    "韩国女团": "🎤 韩国女团",
    "电影": "🎬 电影频道",
    "电视剧": "📺 电视剧频道",
    "动漫": "🎬 动漫频道",
    "体育竞赛": "🏀 体育竞赛频道",
    "音乐吧": "🎵 音乐吧",
    "热门歌曲": "🔥 热门歌曲",
    "戏曲": "🎭 戏曲频道",
    "美食": "🍜 美食频道",
    "动感舞曲": "🎧 动感舞曲",
    "广场舞": "💃 广场舞",
}

# 每个分类对应的关键词列表（小写，用于匹配分类名）
# 优化：音乐吧只匹配“经典老歌”、“经典歌曲”，避免误匹配“经典电影”
CATEGORY_KEYWORDS = {
    "广播": ["广播", "电台", "fm", "am", "动听"],
    "韩国女团": ["歌团", "女团", "kpop"],
    "电影": ["电影", "影院", "影片", "chc", "动作电影", "家庭影院", "影迷电影", "经典电影", "华语影院", "峨眉电影", "第一剧场", "怀旧剧场", "风云剧场"],
    "电视剧": ["电视剧", "剧集", "剧场", "连续剧"],
    "动漫": ["动漫", "动画", "卡通", "二次元"],
    "体育竞赛": ["体育", "竞赛", "赛事", "竞技"],
    # 音乐吧：精准匹配“经典老歌”、“经典歌曲”，而非所有含“经典”的
    "音乐吧": ["经典老歌", "经典歌曲", "经典音乐", "经典金曲"],
    "热门歌曲": ["音乐", "歌曲", "热门歌曲", "流行", "金曲", "热歌", "动听", "好歌", "歌单"],
    "戏曲": ["戏曲", "京剧", "越剧", "黄梅戏", "豫剧", "评剧", "秦腔", "昆曲", "粤剧", "河北梆子", "梨园"],
    "美食": ["美食", "烹饪", "吃播", "厨房", "菜谱"],
    "动感舞曲": ["动感", "舞曲", "dj", "迪斯科", "劲舞"],
    "广场舞": ["广场舞", "健身舞", "排舞"],
}

# ========== 验证配置 ==========
PROBE_TIMEOUT = 8          # 每个频道探测超时(秒)
PROBE_CONCURRENCY = 20     # 并发探测数


def detect_province_from_category(cat_name: str) -> Optional[str]:
    """检测分类名中的省份（如“吉林地方” -> “吉林”）"""
    for prov in PROVINCES:
        if cat_name.startswith(prov) and "地方" in cat_name:
            return prov
    return None


async def probe_channel_quick(url: str, session: aiohttp.ClientSession) -> bool:
    """
    增强版探测：GET 前16KB数据，检查是否为视频流，并排除HTML错误页
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Range": "bytes=0-16384",  # 只请求前16KB
    }
    try:
        async with session.get(url, timeout=PROBE_TIMEOUT, allow_redirects=True, headers=headers) as resp:
            # 状态码检查：200 或 206（部分内容）视为可接受，其他视为无效
            if resp.status not in (200, 206):
                logger.debug(f"❌ 状态码异常 {resp.status}: {url[:80]}")
                return False

            content_type = resp.headers.get("content-type", "").lower()
            # 如果Content-Type明确是视频/M3U8，直接通过
            if any(ct in content_type for ct in ["video", "mpegurl", "x-mpegurl", "application/vnd.apple.mpegurl"]):
                return True

            # 读取数据
            data = await resp.content.read(16384)
            if not data:
                return False

            # 检查是否为HTML错误页（含403、Access Denied等）
            data_lower = data.lower()
            error_keywords = [
                b"<html", b"<!doctype", b"403", b"forbidden",
                b"access denied", b"404", b"not found",
                b"请勿滥用", b"该资源暂不可用"
            ]
            for kw in error_keywords:
                if kw in data_lower:
                    logger.debug(f"❌ 错误页检测: {url[:80]}")
                    return False

            # 检查是否为视频文件头或M3U8
            if data.startswith(b'#EXTM3U') or b'#EXTINF' in data:
                return True
            # 视频文件头
            video_signatures = [
                b'\x00\x00\x00\x18ftyp', b'\x00\x00\x00\x1cftyp',  # MP4
                b'\x1a\x45\xdf\xa3',  # MKV
                b'\x47\x40\x00',      # TS
                b'FLV',              # FLV
                b'RIFF',             # AVI
            ]
            for sig in video_signatures:
                if data.startswith(sig):
                    return True

            # 如果前面都没匹配，但Content-Type是文本，可能无效
            if "text" in content_type:
                return False

            # 兜底：如果数据长度>0且不是明显错误，宽松通过（但最好还是上述检查）
            # 这里决定保守，若未识别则视为无效
            return False
    except asyncio.TimeoutError:
        logger.debug(f"⏱️ 超时: {url[:80]}")
        return False
    except Exception as e:
        logger.debug(f"⚠️ 探测异常 {url[:80]}: {e}")
        return False


def parse_abc123_for_targets(content: str) -> Dict[str, List[Tuple[str, str]]]:
    """
    解析 abc123 源内容，提取目标分类下的频道
    特殊处理：省份地方分类归入对应省份分类（如“吉林地方” -> “☘️吉林频道”）
    """
    if not content:
        return {}

    result = {cat: [] for cat in TARGET_CATEGORIES}
    province_channels = {}

    lines = content.splitlines()
    current_category = None
    current_province = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.endswith(",#genre#") or line.endswith(", #genre#"):
            cat_name = line.replace(",#genre#", "").replace(", #genre#", "").strip()
            current_category = None
            current_province = None

            # 检查是否为省份地方分类
            prov = detect_province_from_category(cat_name)
            if prov:
                current_province = prov
                continue

            # 常规分类匹配
            for target, keywords in CATEGORY_KEYWORDS.items():
                if target == "韩国女团" and ("歌团" in cat_name or "女团" in cat_name):
                    current_category = target
                    break
                if any(kw in cat_name for kw in keywords):
                    current_category = target
                    break
            continue

        if line.startswith('#'):
            continue

        if ',' in line and (current_category in result or current_province):
            parts = line.split(',', 1)
            if len(parts) == 2:
                name = parts[0].strip()
                url = parts[1].strip()
                if url.startswith(('http://', 'https://')):
                    if current_province:
                        if current_province not in province_channels:
                            province_channels[current_province] = []
                        existing_urls = [u for _, u in province_channels[current_province]]
                        if url not in existing_urls:
                            province_channels[current_province].append((name, url))
                    elif current_category in result:
                        existing_urls = [u for _, u in result[current_category]]
                        if url not in existing_urls:
                            result[current_category].append((name, url))

    # 合并省份频道
    for prov, channels in province_channels.items():
        if channels:
            key = f"☘️{prov}频道"
            result[key] = channels

    return {k: v for k, v in result.items() if v}


async def validate_channels(channels: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """并发验证频道可用性"""
    if not channels:
        return []

    semaphore = asyncio.Semaphore(PROBE_CONCURRENCY)
    async with aiohttp.ClientSession() as session:
        async def check_one(name, url):
            async with semaphore:
                ok = await probe_channel_quick(url, session)
                if ok:
                    return (name, url)
                return None

        tasks = [check_one(name, url) for name, url in channels]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]


async def fetch_abc123_source() -> Dict[str, List[Tuple[str, str]]]:
    """拉取 abc123 源并解析分类，然后验证可用性"""
    source_url = "https://tv.19860519.xyz/abc123"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": "https://tv.19860519.xyz/",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(source_url, timeout=15, headers=headers) as resp:
                if resp.status != 200:
                    logger.warning(f"⚠️ abc123 源返回 HTTP {resp.status}")
                    return {}
                content = await resp.text()
                parsed = parse_abc123_for_targets(content)
                if not parsed:
                    return {}

                logger.info("🔍 开始验证智能补充频道的可用性...")
                validated = {}
                total_before = 0
                total_after = 0
                for cat, channels in parsed.items():
                    if not channels:
                        continue
                    total_before += len(channels)
                    valid = await validate_channels(channels)
                    if valid:
                        validated[cat] = valid
                        total_after += len(valid)
                    display = cat if cat.startswith("☘️") else CATEGORY_DISPLAY_NAME.get(cat, cat)
                    logger.info(f"   {display}: {len(valid)}/{len(channels)} 可用")

                if total_before > 0:
                    logger.info(f"📊 验证完成: {total_after}/{total_before} 个频道可用")
                return validated
    except Exception as e:
        logger.error(f"❌ 获取 abc123 源失败: {e}")
        return {}


def append_special_to_output(
    special_data: Dict[str, List[Tuple[str, str]]],
    output_dir: Path
) -> int:
    """追加到输出文件，使用分类名作为 group-title"""
    if not special_data:
        return 0

    total_appended = 0
    m3u_path = output_dir / "tv.m3u"
    txt_path = output_dir / "tv.txt"

    with open(m3u_path, 'a', encoding='utf-8') as f:
        f.write(f"\n# ========== 智能补充分类 ==========\n")
        for cat, channels in special_data.items():
            if not channels:
                continue
            display = cat if cat.startswith("☘️") else CATEGORY_DISPLAY_NAME.get(cat, cat)
            f.write(f"\n# ----- {display} ({len(channels)}个频道) -----\n")
            for name, url in channels:
                f.write(f'#EXTINF:-1 group-title="{display}",{name}\n{url}\n')
                total_appended += 1

    with open(txt_path, 'a', encoding='utf-8') as f:
        f.write(f"\n# ========== 智能补充分类 ==========\n")
        for cat, channels in special_data.items():
            if not channels:
                continue
            display = cat if cat.startswith("☘️") else CATEGORY_DISPLAY_NAME.get(cat, cat)
            f.write(f"\n{display},#genre#\n")
            for name, url in channels:
                f.write(f"{name},{url}\n")

    return total_appended


async def collect_and_append_special_categories(output_dir: Path, db=None) -> Dict[str, int]:
    """主函数：采集、验证并追加"""
    logger.info("🧠 开始智能补充采集（从 abc123 源）...")

    special_data = await fetch_abc123_source()

    if not special_data:
        logger.warning("⚠️ 未获取到任何智能补充分类内容")
        return {}

    stats = {cat: len(channels) for cat, channels in special_data.items()}
    total = sum(stats.values())
    logger.info(f"📊 智能补充统计: 共 {total} 个有效频道")
    for cat, count in stats.items():
        display = cat if cat.startswith("☘️") else CATEGORY_DISPLAY_NAME.get(cat, cat)
        logger.info(f"   {display}: {count} 个频道")

    if total == 0:
        logger.warning("⚠️ 没有符合分类规则的频道")
        return {}

    appended = append_special_to_output(special_data, output_dir)
    logger.info(f"✅ 已将 {appended} 个智能补充频道追加到输出文件")

    return stats
