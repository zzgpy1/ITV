# src/special_categories.py
"""特定分类采集模块 - 从 abc123 和 iptv-org 体育专源采集指定类别"""

import re
from typing import List, Dict, Tuple
from pathlib import Path
from src.logger import logger

# 需要采集的分类关键词（小写）
TARGET_CATEGORIES = [
    "音乐", "广播", "韩国女团", "电影", "电视剧", "动漫", "体育竞赛"
]

# 分类显示名称映射
CATEGORY_DISPLAY_NAME = {
    "音乐": "🎵 音乐频道",
    "广播": "📻 网络电台",
    "韩国女团": "🎤 韩国女团",
    "电影": "🎬 电影频道",
    "电视剧": "📺 电视剧频道",
    "动漫": "🎬 动漫频道",
    "体育竞赛": "🏀 体育竞赛频道",
}


def parse_abc123_for_targets(content: str) -> Dict[str, List[Tuple[str, str]]]:
    """解析 abc123 源内容，提取目标分类下的频道"""
    if not content:
        return {}

    result = {cat: [] for cat in TARGET_CATEGORIES}
    lines = content.splitlines()
    current_category = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.endswith(",#genre#") or line.endswith(", #genre#"):
            cat_name = line.replace(",#genre#", "").replace(", #genre#", "").strip()
            current_category = None
            for target in TARGET_CATEGORIES:
                if target == "韩国女团" and ("歌团" in cat_name or "女团" in cat_name):
                    current_category = target
                    break
                elif target in cat_name:
                    current_category = target
                    break
            continue

        if line.startswith('#'):
            continue

        if ',' in line and current_category in result:
            parts = line.split(',', 1)
            if len(parts) == 2:
                name = parts[0].strip()
                url = parts[1].strip()
                if url.startswith(('http://', 'https://')):
                    existing_urls = [u for _, u in result[current_category]]
                    if url not in existing_urls:
                        result[current_category].append((name, url))

    return {k: v for k, v in result.items() if v}


def parse_iptvorg_sports(content: str) -> List[Tuple[str, str]]:
    """
    解析 iptv-org 体育专类 M3U 内容，提取所有体育频道
    返回 [(频道名, URL), ...]
    """
    if not content:
        return []
    sports_channels = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            # 提取频道名（逗号之后）
            name = line.split(",")[-1].strip()
            if i + 1 < len(lines) and not lines[i + 1].startswith("#"):
                url = lines[i + 1].strip()
                if url.startswith(('http://', 'https://')):
                    sports_channels.append((name, url))
            i += 2
        else:
            i += 1
    return sports_channels


def parse_iptvorg_jp_sports(content: str) -> List[Tuple[str, str]]:
    """
    解析 iptv-org 日本频道 M3U 内容，提取体育类频道（group-title 含 Sport/Sports/体育）
    返回 [(频道名, URL), ...]
    """
    if not content:
        return []
    sports_channels = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            # 提取 group-title
            group_title = ""
            match = re.search(r'group-title="([^"]+)"', line)
            if match:
                group_title = match.group(1)
            # 提取频道名
            name = line.split(",")[-1].strip()
            # 判断是否为体育类
            if group_title and re.search(r'(?i)sport|体育', group_title):
                if i + 1 < len(lines) and not lines[i + 1].startswith("#"):
                    url = lines[i + 1].strip()
                    if url.startswith(('http://', 'https://')):
                        sports_channels.append((name, url))
            i += 2
        else:
            i += 1
    return sports_channels


async def fetch_abc123_source() -> Dict[str, List[Tuple[str, str]]]:
    """直接拉取 abc123 源内容并解析目标分类"""
    import aiohttp
    source_url = "https://tv.19860519.xyz/abc123"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(source_url, timeout=10, headers=headers) as resp:
                if resp.status != 200:
                    logger.warning(f"⚠️ abc123 源返回 HTTP {resp.status}")
                    return {}
                content = await resp.text()
                return parse_abc123_for_targets(content)
    except Exception as e:
        logger.error(f"❌ 获取 abc123 源失败: {e}")
        return {}


async def fetch_iptvorg_sports() -> List[Tuple[str, str]]:
    """拉取 iptv-org 体育专类 M3U 并提取体育频道"""
    import aiohttp
    source_url = "https://iptv-org.github.io/iptv/categories/sports.m3u"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(source_url, timeout=15, headers=headers) as resp:
                if resp.status != 200:
                    logger.warning(f"⚠️ iptv-org 体育源返回 HTTP {resp.status}")
                    return []
                content = await resp.text()
                return parse_iptvorg_sports(content)
    except Exception as e:
        logger.error(f"❌ 获取 iptv-org 体育频道失败: {e}")
        return []

def append_special_to_output(
    special_data: Dict[str, List[Tuple[str, str]]],
    output_dir: Path
) -> int:
    """将特殊分类追加到输出文件（仅追加到 tv.m3u 和 tv.txt）"""
    if not special_data:
        return 0

    total_appended = 0
    m3u_path = output_dir / "tv.m3u"
    txt_path = output_dir / "tv.txt"

    # 追加到 M3U
    with open(m3u_path, 'a', encoding='utf-8') as f:
        f.write(f"\n# ========== 智能补充分类 ==========\n")
        for cat, channels in special_data.items():
            if not channels:
                continue
            display_name = CATEGORY_DISPLAY_NAME.get(cat, cat)
            f.write(f"\n# ----- {display_name} ({len(channels)}个频道) -----\n")
            for name, url in channels:
                f.write(f'#EXTINF:-1 group-title="{display_name}",{name}\n{url}\n')
                total_appended += 1

    # 追加到 TXT
    with open(txt_path, 'a', encoding='utf-8') as f:
        f.write(f"\n# ========== 智能补充分类 ==========\n")
        for cat, channels in special_data.items():
            if not channels:
                continue
            display_name = CATEGORY_DISPLAY_NAME.get(cat, cat)
            f.write(f"\n{display_name},#genre#\n")
            for name, url in channels:
                f.write(f"{name},{url}\n")

    return total_appended


async def collect_and_append_special_categories(output_dir: Path, db=None) -> Dict[str, int]:
    """
    主函数：从 abc123 和 iptv-org 体育专类采集指定分类并追加到输出文件
    """
    logger.info("🧠 开始智能补充采集（从 abc123 + iptv-org 体育专类 + 日本体育频道）...")

    # 1. 从 abc123 获取所有目标分类
    abc123_data = await fetch_abc123_source()

    # 2. 从 iptv-org 体育专类获取体育频道
    iptv_sports = await fetch_iptvorg_sports()

    # 3. 从 iptv-org 日本源获取体育频道
    jp_sports = await fetch_iptvorg_jp_sports()

    # 4. 合并到 sports_channels
    combined_data = abc123_data.copy()  # 包含所有分类
    if "体育竞赛" not in combined_data:
        combined_data["体育竞赛"] = []

    # 合并 iptv-org 体育专类的频道（去重）
    existing_urls = {url for _, url in combined_data["体育竞赛"]}
    for name, url in iptv_sports:
        if url not in existing_urls:
            combined_data["体育竞赛"].append((name, url))
            existing_urls.add(url)

    # 合并日本源的体育频道（去重）
    for name, url in jp_sports:
        if url not in existing_urls:
            combined_data["体育竞赛"].append((name, url))
            existing_urls.add(url)

    # 去重（其他分类已在 parse_abc123 中处理）
    for cat in combined_data:
        if combined_data[cat]:
            seen = set()
            unique = []
            for name, url in combined_data[cat]:
                if url not in seen:
                    seen.add(url)
                    unique.append((name, url))
            combined_data[cat] = unique

    # 统计
    stats = {}
    total = 0
    for cat, channels in combined_data.items():
        if channels:
            stats[cat] = len(channels)
            total += len(channels)

    if total == 0:
        logger.warning("⚠️ 未获取到任何智能补充分类内容")
        return {}

    logger.info(f"📊 智能补充统计: 共 {total} 个频道")
    for cat, count in stats.items():
        logger.info(f"   {CATEGORY_DISPLAY_NAME.get(cat, cat)}: {count} 个频道")

    # 追加到输出文件
    appended = append_special_to_output(combined_data, output_dir)
    logger.info(f"✅ 已将 {appended} 个智能补充频道追加到输出文件")

    return stats
