# src/generator.py
# 输出生成：M3U 和 TXT，严格按照 demo 分类和顺序，TXT 每行 "频道名,URL"

from pathlib import Path
import re
from collections import OrderedDict
from src.config import OUTPUT_DIR, M3U_FILE, TXT_FILE

def clean_channel_name(name: str) -> str:
    """清理频道名，去除清晰度等杂质，仅用于显示"""
    name = re.sub(r'\s*(?:1080[pi]|720[pi]|4K|8K|HD|高清|超清|标清|流畅|付费|备\d*)\s*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[（(][^）)]*[）)]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def generate_outputs_from_demo(ordered_channels: list, category_map: dict = None):
    """
    按照 demo 顺序输出 M3U 和 TXT。
    ordered_channels: 已按 demo 顺序排列的频道列表，每个频道应有 'demo_category' 字段。
    category_map: 可选，用于统计（暂未使用）。
    """
    if not ordered_channels:
        print("⚠️ 没有频道可输出")
        return

    # 按 demo_category 分组，保持顺序
    groups = OrderedDict()
    for ch in ordered_channels:
        cat = ch.get("demo_category", "其他")
        if cat not in groups:
            groups[cat] = []
        groups[cat].append(ch)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. M3U 文件
    m3u_path = OUTPUT_DIR / M3U_FILE
    with open(m3u_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for category, channels in groups.items():
            group_title = category.strip()
            f.write(f"\n# 分类: {group_title}\n")
            for ch in channels:
                url = ch["urls"][0] if ch.get("urls") else ch["url"]
                clean_name = clean_channel_name(ch["name"])
                extinf = f'#EXTINF:-1'
                if ch.get("id"):
                    extinf += f' tvg-id="{ch["id"]}"'
                if ch.get("logo"):
                    extinf += f' tvg-logo="{ch["logo"]}"'
                extinf += f' group-title="{group_title}"'
                extinf += f',{clean_name}\n'
                f.write(extinf)
                f.write(f"{url}\n")

    # 2. TXT 文件（格式：频道名,URL）
    txt_path = OUTPUT_DIR / TXT_FILE
    with open(txt_path, "w", encoding="utf-8") as f:
        for category, channels in groups.items():
            f.write(f"\n# {category}\n")
            for ch in channels:
                url = ch["urls"][0] if ch.get("urls") else ch["url"]
                clean_name = clean_channel_name(ch["name"])
                f.write(f"{clean_name},{url}\n")

    print("\n📊 最终输出分类统计（按 demo 顺序）：")
    for cat, lst in groups.items():
        print(f"  {cat}: {len(lst)} 个频道")
    print(f"📄 输出已生成：\n  - {m3u_path}\n  - {txt_path}")
