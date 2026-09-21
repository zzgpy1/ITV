# src/generator.py
"""输出生成器 - 所有频道按 Demo 列表顺序输出，不新增分类"""

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


# 分类名称常量
CCTV_CATEGORY = "📺央视频道"
SATELLITE_CATEGORY = "📡卫视频道"
HKMT_CATEGORY = "🌊港·澳·台"

# 分类行前缀（用于判断 demo_name 是否为分类）
CATEGORY_PREFIXES = ("☘️", "📺", "📡", "🌊")


class Generator:
    """输出生成器"""

    def __init__(self):
        self.alias_matcher = get_alias_matcher()

    # ---------- 对外入口 ----------
    def generate_all(self, channels: List[Dict], demo_order: List[Tuple[str, str]] = None) -> None:
        output_dir = config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        if demo_order is None:
            demo_order = parse_demo_order_with_categories()

        # 别名标准化（统一频道名）
        channels = self._normalize_channels_with_alias(channels)

        # 按 Demo 顺序分类
        categorized = self._categorize_by_demo(channels, demo_order)

        # 生成文件
        self._generate_m3u(categorized, output_dir / "tv.m3u")
        self._generate_txt(categorized, output_dir / "tv.txt")
        self._generate_multi_m3u(categorized, output_dir / "tv_multi.m3u")
        self._generate_json(channels, output_dir / "channels.json")

        logger.info("✅ 所有输出文件已生成")

    # ---------- 内部方法 ----------
    def _normalize_channels_with_alias(self, channels: List[Dict]) -> List[Dict]:
        if not self.alias_matcher:
            return channels

        normalized = []
        for ch in channels:
            ch_copy = ch.copy()
            original_name = ch.get("name", "")
            std_name = self.alias_matcher.normalize(original_name)
            if std_name != original_name:
                ch_copy["name"] = std_name
                ch_copy["_original_name"] = original_name
            normalized.append(ch_copy)
        return normalized

    def _get_existing_categories(self, demo_order: List[Tuple[str, str]]) -> Dict:
        """
        按 demo 顺序收集分类（用 list 保证顺序）
        """
        categories: List[str] = []
        seen = set()
        province_to_category = {}

        for cat, _ in demo_order:
            if cat not in seen:
                seen.add(cat)
                categories.append(cat)
            if cat.startswith("☘️"):
                province = cat.replace("☘️", "").replace("频道", "").strip()
                if province:
                    province_to_category[province] = cat

        return {
            "all": categories,             # list，保证顺序
            "all_set": set(categories),    # set，用于 O(1) 查找
            "province_map": province_to_category,
        }

    def _infer_category(self, channel_name: str, existing: Dict) -> str:
        """根据频道名推断分类（只归入已有分类）"""
        name_lower = channel_name.lower()
        all_set = existing["all_set"]

        # 1. 央视
        cctv_keywords = ["cctv", "央视", "中央电视", "cntv", "cgtn"]
        for kw in cctv_keywords:
            if kw in name_lower:
                if CCTV_CATEGORY in all_set:
                    return CCTV_CATEGORY
                break

        # 2. 港澳台
        hk_keywords = ["tvb", "翡翠", "明珠", "凤凰", "无线", "rthk", "hoy", "viu",
                       "东森", "民视", "台视", "华视", "中视", "三立", "纬来", "tvbs",
                       "香港", "澳门", "台湾", "澳视", "八大", "中天"]
        for kw in hk_keywords:
            if kw in name_lower:
                if HKMT_CATEGORY in all_set:
                    return HKMT_CATEGORY
                break

        # 3. 卫视
        if "卫视" in channel_name:
            if SATELLITE_CATEGORY in all_set:
                return SATELLITE_CATEGORY

        # 4. 地方频道 - 用 demo_filter 的城市映射精确识别省份
        prov = detect_province(channel_name)
        if prov and prov != "港澳台":
            if prov in existing["province_map"]:
                return existing["province_map"][prov]
            # 没有对应省份分类 → 归入卫视
            if SATELLITE_CATEGORY in all_set:
                return SATELLITE_CATEGORY

        # 5. 兜底
        if SATELLITE_CATEGORY in all_set:
            return SATELLITE_CATEGORY
        elif CCTV_CATEGORY in all_set:
            return CCTV_CATEGORY
        elif existing["all"]:
            return existing["all"][0]
        return "其他"

    def _categorize_by_demo(self, channels: List[Dict],
                            demo_order: List[Tuple[str, str]]) -> Dict[str, List[Dict]]:
        """
        按 Demo 顺序分类：
        第一遍：具体频道名（Demo 顺序）
        第二遍：分类行（☘️/📺/📡/🌊）
        第三遍：未匹配频道按名称排序归入已有分类
        """
        existing = self._get_existing_categories(demo_order)

        # 用普通 dict，插入顺序按 existing["all"] (list) 保证
        result = {cat: [] for cat in existing["all"]}

        if not demo_order:
            for ch in channels:
                cat = self._infer_category(ch["name"], existing)
                result.setdefault(cat, []).append(ch)
            return result

        channel_map = {ch["name"]: ch for ch in channels}

        # 构建 省份 → 频道列表（用 detect_province 精确识别）
        province_channels: Dict[str, List[Dict]] = {}
        for ch in channels:
            prov = detect_province(ch["name"])
            if prov and prov != "港澳台":
                province_channels.setdefault(prov, []).append(ch)
        for prov in province_channels:
            province_channels[prov].sort(key=lambda x: x["name"])

        matched_names = set()
        total_matched = 0

        # ------- 第一遍：具体频道名匹配 -------
        for cat, demo_name in demo_order:
            demo_name_stripped = demo_name.strip()
            if not demo_name_stripped:
                continue
            # 跳过分类行
            if demo_name_stripped.startswith(CATEGORY_PREFIXES):
                continue

            matched_ch = None

            # 1) 精确匹配
            if demo_name_stripped in channel_map:
                matched_ch = channel_map[demo_name_stripped]
            else:
                # 2) 别名匹配
                if self.alias_matcher:
                    for name, ch in channel_map.items():
                        if name in matched_names:
                            continue
                        std_name = self.alias_matcher.normalize(name)
                        if std_name == demo_name_stripped or demo_name_stripped in std_name:
                            matched_ch = ch
                            break

            if matched_ch and matched_ch["name"] not in matched_names:
                matched_names.add(matched_ch["name"])
                total_matched += 1
                result[cat].append(matched_ch)

        # ------- 第二遍：分类行匹配 -------
        for cat, demo_name in demo_order:
            demo_name_stripped = demo_name.strip()
            if not demo_name_stripped.startswith(CATEGORY_PREFIXES):
                continue
            cat_part = demo_name_stripped[1:].replace("频道", "").strip()
            if cat_part in province_channels:
                added = 0
                for ch in province_channels[cat_part]:
                    if ch["name"] not in matched_names:
                        matched_names.add(ch["name"])
                        total_matched += 1
                        result[cat].append(ch)
                        added += 1
                logger.info(f"📌 分类匹配: {demo_name_stripped} -> 新增 {added} 个频道")

        # ------- 第三遍：未匹配频道归入已有分类 -------
        unmatched = [ch for ch in channels if ch["name"] not in matched_names]
        if unmatched:
            unmatched.sort(key=lambda x: x["name"])
            logger.info(f"📊 未匹配频道: {len(unmatched)} 个，自动归类")
            for ch in unmatched:
                cat = self._infer_category(ch["name"], existing)
                result[cat].append(ch)

        # 统计
        total_output = sum(len(lst) for lst in result.values())
        logger.info(f"📊 Demo 匹配: {total_matched} 个，未匹配: {len(unmatched)} 个，总计: {total_output} 个")
        for cat in existing["all"]:
            n = len(result[cat])
            if n:
                logger.info(f"   {cat}: {n} 个频道")

        return result

    # ---------- 输出生成方法 ----------
    def _generate_m3u(self, categorized: Dict[str, List[Dict]], path: Path) -> None:
        total = sum(len(ch) for ch in categorized.values())
        with open(path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            f.write(f"# Total channels: {total}\n")
            for cat, channels in categorized.items():
                if not channels:
                    continue
                f.write(f"\n# ----- {cat} ({len(channels)}个频道) -----\n")
                for ch in channels:
                    url = ch.get("url", "")
                    if url:
                        name = ch.get("name", "未知频道")
                        f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n{url}\n')
        logger.info(f"✅ M3U 文件已生成: {path} ({total} 个频道)")

    def _generate_txt(self, categorized: Dict[str, List[Dict]], path: Path) -> None:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            for cat, channels in categorized.items():
                if not channels:
                    continue
                f.write(f"\n{cat},#genre#\n")
                for ch in channels:
                    url = ch.get("url", "")
                    if url:
                        name = ch.get("name", "未知频道")
                        f.write(f"{name},{url}\n")
        logger.info(f"✅ TXT 文件已生成: {path}")

    def _generate_multi_m3u(self, categorized: Dict[str, List[Dict]], path: Path) -> None:
        with open(path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            for cat, channels in categorized.items():
                if not channels:
                    continue
                f.write(f"\n# ----- {cat} ({len(channels)}个频道) -----\n")
                for ch in channels:
                    urls = ch.get("urls", [ch.get("url", "")])
                    valid_urls = [u for u in urls if u and u.startswith(('http://', 'https://'))]
                    if valid_urls:
                        name = ch.get("name", "未知频道")
                        f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n{" # ".join(valid_urls)}\n')
        logger.info(f"✅ 多源 M3U 文件已生成: {path}")

    def _generate_json(self, channels: List[Dict], path: Path) -> None:
        data = {
            "version": "2.0",
            "total": len(channels),
            "generated": datetime.now().isoformat(),
            "channels": [],
        }
        for ch in channels:
            info = {
                "name": ch.get("name", ""),
                "url": ch.get("url", ""),
                "urls": ch.get("urls", []),
                "latency": ch.get("latency"),
                "codec": ch.get("video_codec", ""),
                "category": ch.get("group_title", ""),
                "is_fixed": ch.get("is_fixed", False),
            }
            info = {k: v for k, v in info.items() if v}
            data["channels"].append(info)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ JSON 文件已生成: {path}")


# ---------- 兼容 run.py 调用 ----------
def generate_outputs_from_demo(ordered_channels: List[Dict],
                                demo_order: List[Tuple[str, str]]) -> None:
    """供 run.py 调用的兼容函数"""
    generator = Generator()
    generator.generate_all(ordered_channels, demo_order)
