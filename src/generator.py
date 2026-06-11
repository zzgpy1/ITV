# src/generator.py
# 输出 M3U 和 TXT 文件模块，按 demo.txt 顺序输出

from pathlib import Path
from typing import List, Tuple, Dict
from src.config import OUTPUT_DIR, M3U_FILE, TXT_FILE
from src.logger import logger


def generate_m3u_by_demo_order(channels_by_name: Dict[str, dict], demo_order: List[Tuple[str, str]], output_path: Path) -> None:
    """严格按照 demo.txt 的顺序生成 M3U 文件"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for cat, demo_name in demo_order:
            channel = channels_by_name.get(demo_name)
            if channel:
                url = channel.get("urls", [channel.get("url")])[0]
                name = channel.get("name", demo_name)
                # 修正：group-title 使用纯分类名，不包含 #genre#
                clean_cat = cat.replace(",#genre#", "").strip()
                f.write(f'#EXTINF:-1 group-title="{clean_cat}",{name}\n')
                f.write(f"{url}\n")
    logger.info(f"✅ M3U 文件已生成: {output_path}")


def generate_txt_by_demo_order(channels_by_name: Dict[str, dict], demo_order: List[Tuple[str, str]], output_path: Path) -> None:
    """严格按照 demo.txt 的顺序生成 TXT 文件"""
    with open(output_path, 'w', encoding='utf-8') as f:
        current_cat = None
        for cat, demo_name in demo_order:
            # 清理分类名
            clean_cat = cat.replace(",#genre#", "").strip()
            if clean_cat != current_cat:
                current_cat = clean_cat
                f.write(f"{current_cat},#genre#\n")
            channel = channels_by_name.get(demo_name)
            if channel:
                url = channel.get("urls", [channel.get("url")])[0]
                name = channel.get("name", demo_name)
                f.write(f"{name},{url}\n")
    logger.info(f"✅ TXT 文件已生成: {output_path}")


def generate_multi_m3u_by_demo_order(channels_by_name: Dict[str, dict], demo_order: List[Tuple[str, str]], output_path: Path) -> None:
    """生成多源 M3U 文件（支持自动切换）"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for cat, demo_name in demo_order:
            channel = channels_by_name.get(demo_name)
            if channel:
                urls = channel.get("urls", [channel.get("url")])
                # 过滤掉空 URL
                valid_urls = [u for u in urls if u and u.startswith(('http://', 'https://'))]
                if valid_urls:
                    # 多个源用 # 分隔，PotPlayer 支持此格式自动切换
                    multi_url = " # ".join(valid_urls)
                    name = channel.get("name", demo_name)
                    clean_cat = cat.replace(",#genre#", "").strip()
                    f.write(f'#EXTINF:-1 group-title="{clean_cat}",{name}\n')
                    f.write(f"{multi_url}\n")
    logger.info(f"✅ 多源 M3U 文件已生成: {output_path}")


def generate_outputs_from_demo(ordered_channels: List[dict], demo_order: List[Tuple[str, str]]) -> None:
    """按照 demo.txt 的顺序输出 M3U 和 TXT 文件"""
    if not ordered_channels or not demo_order:
        logger.warning("无频道数据或 demo_order 为空，跳过输出生成")
        return

    # 构建 {标准化名称: 频道数据} 的字典
    channels_by_name = {ch["name"]: ch for ch in ordered_channels}
    # 同时使用 demo_name 作为备用键
    for ch in ordered_channels:
        if "demo_name" in ch:
            channels_by_name[ch["demo_name"]] = ch

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 生成标准 M3U 文件
    generate_m3u_by_demo_order(channels_by_name, demo_order, OUTPUT_DIR / M3U_FILE)
    
    # 生成 TXT 文件
    generate_txt_by_demo_order(channels_by_name, demo_order, OUTPUT_DIR / TXT_FILE)
    
    # 生成多源 M3U 文件（支持自动切换）
    generate_multi_m3u_by_demo_order(channels_by_name, demo_order, OUTPUT_DIR / "tv_multi.m3u")
