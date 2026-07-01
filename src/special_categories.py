# src/special_categories.py
"""特定分类采集模块 - 从 abc123 源采集指定类别：音乐、广播、韩国女团、电影、电视剧、动漫、体育竞赛"""

import re
from typing import List, Dict, Tuple
from pathlib import Path
from src.logger import logger

# ========== 需要采集的分类关键词 ==========
TARGET_CATEGORIES = [
    "音乐",
    "广播",
    "韩国女团",
    "电影",
    "电视剧",
    "动漫",
    "体育竞赛"
]

# ========== 分类显示名称映射 ==========
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
    """
    解析 abc123 源内容，只提取目标分类下的频道
    
    特殊处理：
      - 源中"歌团★"分类归入"韩国女团"
      - 包含"体育"或"竞赛"的分类归入"体育竞赛"
    """
    if not content:
        return {}
    
    result = {cat: [] for cat in TARGET_CATEGORIES}
    lines = content.splitlines()
    current_category = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 检测分类行（格式：分类名,#genre#）
        if line.endswith(",#genre#") or line.endswith(", #genre#"):
            cat_name = line.replace(",#genre#", "").replace(", #genre#", "").strip()
            current_category = None
            
            for target in TARGET_CATEGORIES:
                # 韩国女团特殊匹配
                if target == "韩国女团" and ("歌团" in cat_name or "女团" in cat_name):
                    current_category = target
                    break
                # 体育竞赛：匹配"体育"或"竞赛"
                if target == "体育竞赛" and ("体育" in cat_name or "竞赛" in cat_name):
                    current_category = target
                    break
                # 普通匹配
                if target in cat_name:
                    current_category = target
                    break
            continue

        # 跳过注释
        if line.startswith('#'):
            continue

        # 解析频道行（格式：频道名,URL）
        if ',' in line and current_category in result:
            parts = line.split(',', 1)
            if len(parts) == 2:
                name = parts[0].strip()
                url = parts[1].strip()
                if url.startswith(('http://', 'https://')):
                    # 去重（基于URL）
                    existing_urls = [u for _, u in result[current_category]]
                    if url not in existing_urls:
                        result[current_category].append((name, url))

    # 只返回非空分类
    return {k: v for k, v in result.items() if v}


async def fetch_abc123_source() -> Dict[str, List[Tuple[str, str]]]:
    """直接拉取 abc123 源内容并解析目标分类"""
    import aiohttp
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
                return parse_abc123_for_targets(content)
    except Exception as e:
        logger.error(f"❌ 获取 abc123 源失败: {e}")
        return {}


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
    """主函数：采集指定分类并追加到输出文件"""
    logger.info("🧠 开始智能补充采集（从 abc123 源）...")

    special_data = await fetch_abc123_source()

    if not special_data:
        logger.warning("⚠️ 未获取到任何智能补充分类内容")
        return {}

    stats = {cat: len(channels) for cat, channels in special_data.items()}
    total = sum(stats.values())
    logger.info(f"📊 智能补充统计: 共 {total} 个频道")
    for cat, count in stats.items():
        logger.info(f"   {CATEGORY_DISPLAY_NAME.get(cat, cat)}: {count} 个频道")

    if total == 0:
        logger.warning("⚠️ 没有符合分类规则的频道")
        return {}

    appended = append_special_to_output(special_data, output_dir)
    logger.info(f"✅ 已将 {appended} 个智能补充频道追加到输出文件")

    return stats
