# src/generator.py
# 输出 M3U 和 TXT 文件模块，修正 M3U 格式为播放器兼容格式

from pathlib import Path
from typing import List, Dict
from src.config import OUTPUT_DIR, M3U_FILE, TXT_FILE
from src.logger import logger

def generate_m3u(channels_by_category: Dict[str, List[dict]], output_path: Path) -> None:
    """
    生成标准 M3U8 格式文件
    - 不写入单独的分类行，通过 group-title 属性分组
    - 保持分类和频道的文件顺序
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        f.write("# 分类顺序: " + ", ".join(channels_by_category.keys()) + "\n")
        
        for cat, channels in channels_by_category.items():
            if not channels:
                continue
            # 可选：写入分类注释（部分播放器会识别为分组标题）
            f.write(f"\n# 分类: {cat}\n")
            
            for ch in channels:
                url = ch.get("urls", [ch.get("url")])[0]
                tvg_id = ch.get("id", "")
                tvg_logo = ch.get("logo", "")
                name = ch["name"]
                
                # 标准 M3U 格式：所有频道属性放在同一行
                extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{tvg_logo}" group-title="{cat}",{name}'
                f.write(f"{extinf}\n{url}\n")
    
    logger.info(f"✅ M3U 文件已生成: {output_path} (共 {sum(len(ch) for ch in channels_by_category.values())} 个频道)")

def generate_txt(channels_by_category: Dict[str, List[dict]], output_path: Path) -> None:
    """生成 TXT 文件（保持原格式）"""
    with open(output_path, 'w', encoding='utf-8') as f:
        for cat, channels in channels_by_category.items():
            if not channels:
                continue
            f.write(f"\n{cat},#genre#\n")
            for ch in channels:
                url = ch.get("urls", [ch.get("url")])[0]
                f.write(f"{ch['name']},{url}\n")
    logger.info(f"✅ TXT 文件已生成: {output_path}")

def generate_outputs_from_demo(ordered_channels: List[dict]) -> None:
    """
    ordered_channels 已按照 demo.txt 的顺序排列（包含 demo_category 字段）
    按 demo_category 分组后输出 M3U 和 TXT
    """
    if not ordered_channels:
        logger.warning("无频道数据，跳过输出生成")
        return

    # 按 demo_category 分组，保持插入顺序
    groups = {}
    for ch in ordered_channels:
        cat = ch.get("demo_category", "其他")
        groups.setdefault(cat, []).append(ch)

    # 统计分组信息
    for cat, channels in groups.items():
        logger.info(f"📂 分类 '{cat}': {len(channels)} 个频道")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generate_m3u(groups, OUTPUT_DIR / M3U_FILE)
    generate_txt(groups, OUTPUT_DIR / TXT_FILE)
