# src/generator.py
"""输出生成器 - 别名前置 + 城市映射兜底 + Demo 顺序输出"""

import json
import re
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime

from src.config_loader import config
from src.constants import PROVINCES
from src.logger import logger
from src.demo_filter import parse_demo_order_with_categories, detect_province
from src.alias_matcher import get_alias_matcher


CCTV_CATEGORY = "📺央视频道"
SATELLITE_CATEGORY = "📡卫视频道"
HKMT_CATEGORY = "🌊港·澳·台"
CATEGORY_PREFIXES = ("☘️", "📺", "📡", "🌊")


class Generator:
    def __init__(self):
        self.alias_matcher = get_alias_matcher()

    def generate_all(self, channels: List[Dict], demo_order: List[Tuple[str, str]] = None) -> None:
        output_dir = config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        if demo_order is None:
            demo_order = parse_demo_order_with_categories()

        # 1) 别名前置标准化（必须先做，再做分类/匹配）
        channels = self._normalize_with_alias(channels)

        # 2) 分类
        categorized = self._categorize_by_demo(channels, demo_order)

        # 3) 生成
        self._generate_m3u(categorized, output_dir / "tv.m3u")
        self._generate_txt(categorized, output_dir / "tv.txt")
        self._generate_multi_m3u(categorized, output_dir / "tv_multi.m3u")
        self._generate_json(channels, output_dir / "channels.json")
        logger.info("✅ 所有输出文件已生成")

    def _normalize_with_alias(self, channels: List[Dict]) -> List[Dict]:
        if not self.alias_matcher:
            return channels
        out = []
        for ch in channels:
            c = ch.copy()
            original = c.get("name", "")
            std = self.alias_matcher.normalize(original)
            if std != original:
                c["name"] = std
                c["_original_name"] = original
            out.append(c)
        return out

    def _get_existing_categories(self, demo_order):
        categories: List[str] = []
        seen = set()
        province_map = {}
        for cat, _ in demo_order:
            if cat not in seen:
                seen.add(cat)
                categories.append(cat)
            if cat.startswith("☘️"):
                p = cat.replace("☘️", "").replace("频道", "").strip()
                if p:
                    province_map[p] = cat
        return {"all": categories, "all_set": set(categories), "province_map": province_map}

    def _infer_category(self, channel_name: str, existing: Dict) -> str:
        name_lower = channel_name.lower()
        all_set = existing["all_set"]

        # 央视
        for kw in ("cctv", "央视", "中央电视", "cntv", "cgtn"):
            if kw in name_lower:
                if CCTV_CATEGORY in all_set:
                    return CCTV_CATEGORY
                break

        # 港澳台
        for kw in ("tvb", "翡翠", "明珠", "凤凰", "无线", "rthk", "hoy", "viu",
                   "东森", "民视", "台视", "华视", "中视", "三立", "纬来", "tvbs",
                   "香港", "澳门", "台湾", "澳视", "八大", "中天"):
            if kw in name_lower:
                if HKMT_CATEGORY in all_set:
                    return HKMT_CATEGORY
                break

        # 卫视
        if "卫视" in channel_name:
            if SATELLITE_CATEGORY in all_set:
                return SATELLITE_CATEGORY

        # 地方频道：复用 demo_filter.detect_province（含城市映射）
        prov = detect_province(channel_name)
        if prov and prov != "港澳台":
            if prov in existing["province_map"]:
                return existing["province_map"][prov]
            if SATELLITE_CATEGORY in all_set:
                return SATELLITE_CATEGORY

        # 兜底
        if SATELLITE_CATEGORY in all_set:
            return SATELLITE_CATEGORY
        if CCTV_CATEGORY in all_set:
            return CCTV_CATEGORY
        if existing["all"]:
            return existing["all"][0]
        return "其他"

    def _categorize_by_demo(self, channels, demo_order):
        existing = self._get_existing_categories(demo_order)
        result = {cat: [] for cat in existing["all"]}

        if not demo_order:
            for ch in channels:
                cat = self._infer_category(ch["name"], existing)
                result.setdefault(cat, []).append(ch)
            return result

        channel_map = {ch["name"]: ch for ch in channels}

        # 省份分组（用 detect_province，含城市映射）
        province_channels: Dict[str, List[Dict]] = {}
        for ch in channels:
            prov = detect_province(ch["name"])
            if prov and prov != "港澳台":
                province_channels.setdefault(prov, []).append(ch)
        for p in province_channels:
            province_channels[p].sort(key=lambda x: x["name"])

        matched = set()
        total_matched = 0

        # 第一遍：具体频道名
        for cat, demo_name in demo_order:
            dn = demo_name.strip()
            if not dn or dn.startswith(CATEGORY_PREFIXES):
                continue
            ch_found = None
            if dn in channel_map:
                ch_found = channel_map[dn]
            elif self.alias_matcher:
                for name, c in channel_map.items():
                    if name in matched:
                        continue
                    std = self.alias_matcher.normalize(name)
                    if std == dn or dn in std:
                        ch_found = c
                        break
            if ch_found and ch_found["name"] not in matched:
                matched.add(ch_found["name"])
                total_matched += 1
                result[cat].append(ch_found)

        # 第二遍：分类行
        for cat, demo_name in demo_order:
            dn = demo_name.strip()
            if not dn.startswith(CATEGORY_PREFIXES):
                continue
            p = dn[1:].replace("频道", "").strip()
            if p in province_channels:
                added = 0
                for ch in province_channels[p]:
                    if ch["name"] not in matched:
                        matched.add(ch["name"])
                        total_matched += 1
                        result[cat].append(ch)
                        added += 1
                logger.info(f"📌 分类匹配: {dn} -> 新增 {added} 个频道")

        # 第三遍：未匹配
        unmatched = [ch for ch in channels if ch["name"] not in matched]
        if unmatched:
            unmatched.sort(key=lambda x: x["name"])
            for ch in unmatched:
                cat = self._infer_category(ch["name"], existing)
                result[cat].append(ch)

        total_out = sum(len(v) for v in result.values())
        logger.info(f"📊 Demo 匹配: {total_matched}，未匹配: {len(unmatched)}，总计: {total_out}")
        for cat in existing["all"]:
            if result[cat]:
                logger.info(f"   {cat}: {len(result[cat])} 个频道")
        return result

    # ---------- 输出 ----------
    def _generate_m3u(self, categorized, path):
        total = sum(len(v) for v in categorized.values())
        with open(path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            f.write(f"# Total channels: {total}\n")
            for cat, chs in categorized.items():
                if not chs:
                    continue
                f.write(f"\n# ----- {cat} ({len(chs)}个频道) -----\n")
                for ch in chs:
                    url = ch.get("url", "")
                    if url:
                        f.write(f'#EXTINF:-1 group-title="{cat}",{ch.get("name", "未知频道")}\n{url}\n')
        logger.info(f"✅ M3U 已生成: {path} ({total})")

    def _generate_txt(self, categorized, path):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            for cat, chs in categorized.items():
                if not chs:
                    continue
                f.write(f"\n{cat},#genre#\n")
                for ch in chs:
                    url = ch.get("url", "")
                    if url:
                        f.write(f"{ch.get('name', '未知频道')},{url}\n")
        logger.info(f"✅ TXT 已生成: {path}")

    def _generate_multi_m3u(self, categorized, path):
        with open(path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            for cat, chs in categorized.items():
                if not chs:
                    continue
                f.write(f"\n# ----- {cat} ({len(chs)}个频道) -----\n")
                for ch in chs:
                    urls = ch.get("urls", [ch.get("url", "")])
                    valid = [u for u in urls if u and u.startswith(('http://', 'https://'))]
                    if valid:
                        f.write(f'#EXTINF:-1 group-title="{cat}",{ch.get("name", "未知频道")}\n{" # ".join(valid)}\n')
        logger.info(f"✅ 多源 M3U 已生成: {path}")

    def _generate_json(self, channels, path):
        data = {"version": "2.0", "total": len(channels),
                "generated": datetime.now().isoformat(), "channels": []}
        for ch in channels:
            info = {k: ch.get(k) for k in
                    ("name", "url", "urls", "latency", "video_codec", "group_title", "is_fixed", "source_state")}
            info = {k: v for k, v in info.items() if v not in (None, "", [])}
            data["channels"].append(info)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ JSON 已生成: {path}")


def generate_outputs_from_demo(ordered_channels, demo_order):
    Generator().generate_all(ordered_channels, demo_order)


# ---------- 第一段快速产出（新增） ----------
def quick_generate_from_stable(stable_sources: Dict[str, Dict], demo_order=None) -> int:
    """
    仅从数据库稳定源快速生成初版列表。
    返回生成的频道数。
    """
    if not stable_sources:
        return 0
    channels = []
    for name, src in stable_sources.items():
        if not src.get("url"):
            continue
        channels.append({
            "name": name,
            "url": src["url"],
            "urls": [src["url"]],
            "latency": src.get("latency", 0),
            "video_codec": src.get("video_codec", ""),
            "is_fixed": src.get("is_fixed", False),
            "source_state": "from_cache",
        })
    if not channels:
        return 0
    if demo_order is None:
        demo_order = parse_demo_order_with_categories()
    Generator().generate_all(channels, demo_order)
    return len(channels)
