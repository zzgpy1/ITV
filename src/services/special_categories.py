# src/services/special_categories.py
"""智能补充分类"""

import asyncio
import aiohttp
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from src.core.config import get_config
from src.core.constants import PROVINCES
from src.infrastructure.logger import get_logger

logger = get_logger(__name__)

# 目标分类
TARGET_CATEGORIES = {
    "广播": ["广播", "电台", "fm", "am"],
    "韩国女团": ["歌团", "女团", "kpop"],
    "音乐吧": ["经典老歌", "经典歌曲", "经典音乐"],
    "热门歌曲": ["音乐", "歌曲", "热门", "流行", "金曲", "热歌"],
    "动感舞曲": ["动感", "舞曲", "dj", "迪斯科"],
    "广场舞": ["广场舞", "健身舞", "排舞"],
}

CATEGORY_DISPLAY = {
    "广播": "📻 网络电台",
    "韩国女团": "🎤 韩国女团",
    "音乐吧": "🎵 音乐吧",
    "热门歌曲": "🔥 热门歌曲",
    "动感舞曲": "🎧 动感舞曲",
    "广场舞": "💃 广场舞",
}


def detect_province(cat_name: str) -> Optional[str]:
    """从分类名检测省份"""
    for prov in PROVINCES:
        if cat_name.startswith(prov) and "地方" in cat_name:
            return prov
    return None


def detect_category(cat_name: str) -> Optional[str]:
    """检测分类"""
    for target, keywords in TARGET_CATEGORIES.items():
        if any(kw in cat_name for kw in keywords):
            return target
    return None


def parse_special_content(content: str) -> Dict[str, List[Tuple[str, str]]]:
    """解析特殊分类内容"""
    if not content:
        return {}
    
    result = {}
    lines = content.splitlines()
    current_cat = None
    current_prov = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if line.endswith(",#genre#") or line.endswith(", #genre#"):
            cat_name = line.replace(",#genre#", "").replace(", #genre#", "").strip()
            current_cat = None
            current_prov = None
            
            prov = detect_province(cat_name)
            if prov:
                current_prov = prov
                continue
            
            cat = detect_category(cat_name)
            if cat:
                current_cat = cat
            continue
        
        if line.startswith('#'):
            continue
        
        if ',' in line and (current_cat or current_prov):
            parts = line.split(',', 1)
            if len(parts) == 2:
                name = parts[0].strip()
                url = parts[1].strip()
                if url.startswith(('http://', 'https://')):
                    key = current_cat or current_prov
                    if key:
                        if key not in result:
                            result[key] = []
                        existing_urls = [u for _, u in result[key]]
                        if url not in existing_urls:
                            result[key].append((name, url))
    
    return result


async def probe_channel(url: str, session: aiohttp.ClientSession) -> bool:
    """探测频道可用性"""
    try:
        async with session.head(url, timeout=5, allow_redirects=True) as resp:
            if resp.status != 200:
                return False
            content_type = resp.headers.get("content-type", "").lower()
            if any(ct in content_type for ct in ["video", "mpegurl", "x-mpegurl"]):
                return True
            return False
    except Exception:
        return False


async def validate_channels(channels: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """验证频道"""
    if not channels:
        return []
    
    semaphore = asyncio.Semaphore(20)
    
    async with aiohttp.ClientSession() as session:
        async def check_one(name: str, url: str):
            async with semaphore:
                if await probe_channel(url, session):
                    return (name, url)
                return None
        
        tasks = [check_one(name, url) for name, url in channels]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]


async def fetch_special_categories() -> Dict[str, List[Tuple[str, str]]]:
    """获取特殊分类"""
    source_url = "https://tv.19860519.xyz/abc123"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(source_url, timeout=15, headers=headers) as resp:
                if resp.status != 200:
                    logger.warning(f"⚠️ 特殊分类源返回 HTTP {resp.status}")
                    return {}
                content = await resp.text()
                parsed = parse_special_content(content)
                
                if not parsed:
                    return {}
                
                logger.info("🔍 验证特殊分类频道...")
                validated = {}
                for cat, channels in parsed.items():
                    if channels:
                        valid = await validate_channels(channels)
                        if valid:
                            validated[cat] = valid
                            display = CATEGORY_DISPLAY.get(cat, cat)
                            logger.info(f"   {display}: {len(valid)}/{len(channels)} 可用")
                
                return validated
                
    except Exception as e:
        logger.error(f"❌ 获取特殊分类失败: {e}")
        return {}


async def collect_and_append_special_categories(output_dir: Path) -> Dict[str, int]:
    """采集并追加特殊分类"""
    logger.info("🧠 开始智能补充采集...")
    
    special_data = await fetch_special_categories()
    if not special_data:
        logger.warning("⚠️ 未获取到特殊分类内容")
        return {}
    
    stats = {cat: len(channels) for cat, channels in special_data.items()}
    total = sum(stats.values())
    
    if total == 0:
        logger.warning("⚠️ 没有可用的特殊分类频道")
        return {}
    
    # 追加到输出
    m3u_path = output_dir / "tv.m3u"
    txt_path = output_dir / "tv.txt"
    
    if m3u_path.exists():
        with open(m3u_path, 'a', encoding='utf-8') as f:
            f.write(f"\n# ========== 智能补充分类 ({total}个频道) ==========\n")
            for cat, channels in special_data.items():
                display = CATEGORY_DISPLAY.get(cat, cat)
                if not channels:
                    continue
                for name, url in channels:
                    f.write(f'#EXTINF:-1 group-title="{display}",{name}\n{url}\n')
    
    if txt_path.exists():
        with open(txt_path, 'a', encoding='utf-8') as f:
            f.write(f"\n# ========== 智能补充分类 ({total}个频道) ==========\n")
            for cat, channels in special_data.items():
                display = CATEGORY_DISPLAY.get(cat, cat)
                if not channels:
                    continue
                f.write(f"\n{display},#genre#\n")
                for name, url in channels:
                    f.write(f"{name},{url}\n")
    
    logger.info(f"✅ 已追加 {total} 个智能补充频道")
    return stats
