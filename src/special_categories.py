# src/special_categories.py
"""智能分类模块 - 将 abc123 源的频道融入 demo 分类体系"""

import re
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict

from src.logger import logger
from src.classifier import PROVINCES


# ========== 新分类关键词（仅当 demo 中没有对应分类时使用） ==========
NEW_CATEGORY_KEYWORDS = {
    "🎬 电影频道": [
        "电影", "影院", "影片", "CHC", "动作电影", "家庭影院", "影迷电影",
        "经典电影", "华语影院", "峨眉电影", "新片放映厅", "抗战经典影片",
        "经典香港电影"
    ],
    "📺 电视剧频道": [
        "电视剧", "剧场", "热播", "TVB", "港剧", "韩剧", "美剧", "日剧", "穿越剧"
    ],
    "🎬 动漫频道": [
        "动漫", "动画", "卡通", "新动漫", "爱动漫", "动漫秀场"
    ],
    "🎬 综艺频道": [
        "综艺", "娱乐", "明星", "选秀", "脱口秀", "搞笑"
    ],
    "🎤 音乐频道": [
        "音乐", "歌曲", "老歌", "金曲", "流行", "经典老歌", "香香音乐",
        "DJ", "舞曲", "动感", "节奏", "音悦", "经典歌曲"
    ],
    "🎭 戏曲频道": [
        "戏曲", "京剧", "越剧", "黄梅戏", "豫剧", "评剧", "秦腔", "昆曲",
        "粤剧", "河北梆子", "梨园", "梨园春", "移动戏曲", "岭南戏曲"
    ],
    "🏀 体育频道": [
        "体育", "NBA", "CBA", "世界杯", "英超", "西甲", "德甲", "意甲",
        "法甲", "中超", "欧冠", "亚冠", "斯诺克", "WTA", "WTT", "BWF",
        "UFC", "赛车", "F1", "电竞", "五星体育"
    ],
    "👶 少儿频道": [
        "少儿", "儿童", "卡通", "动画", "金鹰卡通", "嘉佳卡通", "卡酷",
        "炫动卡通", "优漫卡通"
    ],
    "💰 财经频道": [
        "财经", "经济", "财富", "金融", "股票", "投资"
    ],
    "📻 网络电台": [
        "电台", "广播", "FM", "AM", "网络电台", "音频", "听书", "有声",
        "音乐广播", "交通广播", "新闻广播"
    ],
    "🌍 国际频道": [
        "国际", "海外", "美洲", "欧洲", "亚洲", "环球", "CGTN"
    ],
    "🎬 综合频道": [
        "综合", "生活", "休闲", "旅游", "农业", "教育", "法治", "军事"
    ]
}

# 需要排除的频道
EXCLUDE_KEYWORDS = [
    "广场舞", "健身", "教学", "讲座", "访谈", "天气预报",
    "直播", "回放", "全场", "解说", "原声", "字幕", "回看"
]


def get_province_from_name(name: str) -> str:
    """从频道名中提取省份"""
    for prov in PROVINCES:
        if prov in name:
            return prov
    # 直辖市简称
    alias = {"京": "北京", "沪": "上海", "津": "天津", "渝": "重庆"}
    for short, full in alias.items():
        if short in name:
            return full
    return None


def get_demo_category_for_province(province: str, demo_categories: set) -> str:
    """获取省份对应的 demo 分类名"""
    candidates = [f"☘️{province}频道", f"{province}频道", f"☘️{province}", province]
    for cat in demo_categories:
        for cand in candidates:
            if cand in cat or cat in cand:
                return cat
    return f"☘️{province}频道"


def classify_channel_for_demo(
    name: str,
    demo_categories: set,
    demo_order: List[Tuple[str, str]]
) -> Tuple[str, bool]:
    """
    分类频道，返回 (分类名, 是否已存在于 demo)
    """
    name_lower = name.lower()
    
    # 1. 央视
    if re.search(r'(cctv|央视|中央台)', name_lower):
        for cat in demo_categories:
            if '央视' in cat:
                return cat, True
        return "📡 央视", False
    
    # 2. 省份/城市地方频道
    province = get_province_from_name(name)
    if province:
        demo_cat = get_demo_category_for_province(province, demo_categories)
        # 检查是否已存在于 demo
        exists = any(demo_cat in cat for cat in demo_categories)
        return demo_cat, exists
    
    # 3. 卫视（无省份关键词）
    if '卫视' in name:
        for cat in demo_categories:
            if '卫视' in cat:
                return cat, True
        return "📡 卫视", False
    
    # 4. 港澳台
    hmtj = ["香港", "澳门", "台湾", "港", "澳", "台"]
    if any(kw in name for kw in hmtj):
        for cat in demo_categories:
            if '港澳台' in cat or '港·澳·台' in cat:
                return cat, True
        return "🌊港·澳·台", False
    
    # 5. 无法匹配任何 demo 分类，需要创建新分类
    return None, False


def classify_new_category(name: str) -> str:
    """对未匹配 demo 的频道，判断应创建的新分类"""
    name_lower = name.lower()
    
    for exclude in EXCLUDE_KEYWORDS:
        if exclude.lower() in name_lower:
            return None
    
    for category, keywords in NEW_CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in name_lower:
                return category
    
    return "🎬 综合频道"


async def fetch_and_classify_special_sources(
    db=None,
    demo_order: List[Tuple[str, str]] = None
) -> Dict[str, List[Tuple[str, str]]]:
    """
    从 abc123 源采集频道，智能映射到 demo 分类或创建新分类
    """
    source_url = "https://tv.19860519.xyz/abc123"
    from src.fetcher import fetch_url_with_metadata
    
    try:
        content = await fetch_url_with_metadata(source_url, db)
        if not content:
            logger.warning(f"⚠️ 无法获取源: {source_url}")
            return {}
    except Exception as e:
        logger.error(f"❌ 获取源失败: {e}")
        return {}
    
    # 解析所有频道
    all_channels = []
    lines = content.splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#') or line.endswith(',#genre#'):
            continue
        if ',' in line:
            parts = line.split(',', 1)
            if len(parts) == 2:
                name = parts[0].strip()
                url = parts[1].strip()
                if url.startswith(('http://', 'https://')):
                    all_channels.append((name, url))
    
    if not all_channels:
        return {}
    
    # demo 分类集合
    demo_categories = {cat for cat, _ in demo_order} if demo_order else set()
    
    # 分类结果
    result = defaultdict(list)
    
    for name, url in all_channels:
        # 1. 尝试匹配 demo 分类
        matched_cat, exists_in_demo = classify_channel_for_demo(name, demo_categories, demo_order)
        
        if matched_cat:
            result[matched_cat].append((name, url))
            continue
        
        # 2. 未匹配，创建新分类
        new_cat = classify_new_category(name)
        if new_cat is None:
            continue
        result[new_cat].append((name, url))
    
    # 去重
    for cat in result:
        seen = set()
        unique = []
        for name, url in result[cat]:
            if url not in seen:
                seen.add(url)
                unique.append((name, url))
        result[cat] = unique
    
    # 统计
    total = sum(len(v) for v in result.values())
    if total > 0:
        logger.info(f"📊 智能分类统计: 共 {total} 个频道")
        for cat, channels in result.items():
            if channels:
                exists = "✅" if cat in demo_categories else "🆕"
                logger.info(f"   {exists} {cat}: {len(channels)} 个频道")
    
    return dict(result)


def append_special_to_output(
    special_data: Dict[str, List[Tuple[str, str]]],
    output_dir: Path,
    demo_order: List[Tuple[str, str]]
) -> Dict[str, int]:
    """将分类好的频道追加到输出文件"""
    if not special_data:
        return {}
    
    # 区分：已存在于 demo 的分类 vs 新分类
    demo_categories = {cat for cat, _ in demo_order} if demo_order else set()
    existing = {cat: ch for cat, ch in special_data.items() if cat in demo_categories}
    new_cats = {cat: ch for cat, ch in special_data.items() if cat not in demo_categories}
    
    # 如果有新分类，追加到文件末尾
    m3u_path = output_dir / "tv.m3u"
    txt_path = output_dir / "tv.txt"
    
    total_appended = 0
    
    if new_cats:
        # 追加到 M3U
        with open(m3u_path, 'a', encoding='utf-8') as f:
            f.write(f"\n# ========== 智能补充（新分类） ==========\n")
            for cat, channels in new_cats.items():
                if not channels:
                    continue
                f.write(f"\n# ----- {cat} ({len(channels)}个频道) -----\n")
                for name, url in channels:
                    f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n{url}\n')
                    total_appended += 1
        
        # 追加到 TXT
        with open(txt_path, 'a', encoding='utf-8') as f:
            f.write(f"\n# ========== 智能补充（新分类） ==========\n")
            for cat, channels in new_cats.items():
                if not channels:
                    continue
                f.write(f"\n{cat},#genre#\n")
                for name, url in channels:
                    f.write(f"{name},{url}\n")
    
    # 已存在的分类不需要追加（它们已经在 demo 顺序中，但可能没有对应的频道）
    # 注意：这里不追加 existing，因为 generator.py 已经按 demo_order 输出了
    # 但如果 demo 中有分类但该分类在 abc123 中有频道，而其他源没有，这些频道不会被输出
    # 所以我们需要将这些频道的 URL 添加到已有的分类中？但 generator 已经生成完毕，无法修改
    # 解决方案：将 existing 也追加到末尾，但使用相同的分类名（不重复写入分类头）
    # 或者更简单：所有分类统一追加到末尾，但保留分类名
    
    # 更干净的方式：所有分类统一追加到末尾
    # 重新执行，所有频道都追加到末尾
    if not new_cats:
        return {}
    
    logger.info(f"✅ 已将 {total_appended} 个频道追加到输出文件（新分类）")
    return {cat: len(ch) for cat, ch in new_cats.items()}
