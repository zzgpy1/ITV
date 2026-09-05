# src/generator.py
"""输出生成器 - 所有频道按 Demo 列表顺序输出，不新增分类"""

import json
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime

from src.config_loader import config
from src.constants import PROVINCES
from src.logger import logger
from src.demo_filter import parse_demo_order_with_categories
from src.alias_matcher import get_alias_matcher


class Generator:
    """输出生成器"""

    def __init__(self):
        self.alias_matcher = get_alias_matcher()

    def generate_all(self, channels: List[Dict], demo_order: List[Tuple[str, str]] = None) -> None:
        """生成所有输出"""
        output_dir = config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        if demo_order is None:
            demo_order = parse_demo_order_with_categories()

        # 应用别名标准化
        channels = self._normalize_channels_with_alias(channels)

        # 按 Demo 分类并保持顺序
        categorized = self._categorize_by_demo(channels, demo_order)

        # 生成文件
        self._generate_m3u(categorized, output_dir / "tv.m3u")
        self._generate_txt(categorized, output_dir / "tv.txt")
        self._generate_multi_m3u(categorized, output_dir / "tv_multi.m3u")
        self._generate_json(channels, output_dir / "channels.json")

        logger.info("✅ 所有输出文件已生成")

    def _normalize_channels_with_alias(self, channels: List[Dict]) -> List[Dict]:
        """使用别名标准化频道名"""
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
        """提取 Demo 中所有已有分类及省份映射"""
        categories = set()
        province_to_category = {}

        for cat, _ in demo_order:
            categories.add(cat)
            if cat.startswith("☘️"):
                province = cat.replace("☘️", "").replace("频道", "").strip()
                if province:
                    province_to_category[province] = cat

        return {"all": categories, "province_map": province_to_category}

    def _infer_category(self, channel_name: str, existing: Dict) -> str:
        """根据频道名推断应归入的已有分类（绝不创建新分类）"""
        name_lower = channel_name.lower()

        # 1. 央视
        cctv_keywords = ["cctv", "央视", "中央电视", "cntv", "cgtn"]
        for kw in cctv_keywords:
            if kw in name_lower:
                if "📺央视频道" in existing["all"]:
                    return "📺央视频道"
                break

        # 2. 港澳台
        hk_keywords = ["tvb", "翡翠", "明珠", "凤凰", "无线", "rthk", "hoy", "viu",
                       "东森", "民视", "台视", "华视", "中视", "三立", "纬来", "tvbs",
                       "香港", "澳门", "台湾", "澳视", "八大", "中天"]
        for kw in hk_keywords:
            if kw in name_lower:
                if "🌊港·澳·台" in existing["all"]:
                    return "🌊港·澳·台"
                break

        # 3. 卫视
        if "卫视" in channel_name:
            if "📡卫视频道" in existing["all"]:
                return "📡卫视频道"

        # 4. 地方频道 - 按省份匹配已有 ☘️XX频道
        for prov in PROVINCES:
            if prov in channel_name:
                if prov in existing["province_map"]:
                    return existing["province_map"][prov]
                if "📡卫视频道" in existing["all"]:
                    return "📡卫视频道"
                break

        # 5. 兜底
        if "📡卫视频道" in existing["all"]:
            return "📡卫视频道"
        elif "📺央视频道" in existing["all"]:
            return "📺央视频道"
        else:
            for cat in existing["all"]:
                return cat
            return "其他"

    def _categorize_by_demo(self, channels: List[Dict], demo_order: List[Tuple[str, str]]) -> Dict[str, List[Dict]]:
        """按 Demo 顺序分类，同一分类内频道顺序：Demo 顺序 → 分类匹配（按名称）→ 未匹配（按名称）"""
        result = {}
        existing = self._get_existing_categories(demo_order)
        for cat in existing["all"]:
            result[cat] = []

        if not demo_order:
            for ch in channels:
                cat = self._infer_category(ch["name"], existing)
                result.setdefault(cat, []).append(ch)
            return result

        # 构建频道名到频道的映射
        channel_map = {ch["name"]: ch for ch in channels}

        # 按省份分组（用于分类匹配）
        province_channels = {}
        for ch in channels:
            prov = None
            for p in PROVINCES:
                if p in ch["name"]:
                    prov = p
                    break
            if prov:
                province_channels.setdefault(prov, []).append(ch)
        # 排序，保证顺序稳定
        for prov in province_channels:
            province_channels[prov].sort(key=lambda x: x["name"])

        matched_names = set()
        total_matched = 0

        # 第一遍：按 Demo 顺序匹配具体频道名
        for cat, demo_name in demo_order:
            # 跳过分类行（分类行稍后处理）
            if demo_name.startswith(("☘️", "📺", "📡", "🌊")):
                continue

            matched_ch = None
            # 精确匹配
            if demo_name in channel_map:
                matched_ch = channel_map[demo_name]
            elif self.alias_matcher:
                # 别名匹配
                for name, ch in channel_map.items():
                    if name in matched_names:
                        continue
                    std_name = self.alias_matcher.normalize(name)
                    if std_name == demo_name or demo_name in std_name:
                        matched_ch = ch
                        break
            if matched_ch and matched_ch["name"] not in matched_names:
                matched_names.add(matched_ch["name"])
                total_matched += 1
                result[cat].append(matched_ch)

        # 第二遍：处理分类行，匹配剩余频道（按名称排序）
        for cat, demo_name in demo_order:
            if not demo_name.startswith(("☘️", "📺", "📡", "🌊")):
                continue
            prefix = demo_name[0]
            cat_part = demo_name[1:].replace("频道", "").strip()
            if cat_part in province_channels:
                for ch in province_channels[cat_part]:
                    if ch["name"] not in matched_names:
                        matched_names.add(ch["name"])
                        total_matched += 1
                        result[cat].append(ch)
                logger.info(f"📌 分类匹配: {demo_name} -> {len(province_channels.get(cat_part, []))} 个频道")

        # 第三遍：未匹配频道自动归入已有分类（按名称排序）
        unmatched = [ch for ch in channels if ch["name"] not in matched_names]
        if unmatched:
            unmatched.sort(key=lambda x: x["name"])
            logger.info(f"📊 未匹配频道: {len(unmatched)} 个，自动归入已有分类")
            for ch in unmatched:
                cat = self._infer_category(ch["name"], existing)
                result[cat].append(ch)

        # 统计
        total_output = sum(len(lst) for lst in result.values())
        logger.info(f"📊 Demo 匹配: {total_matched} 个，自动归类: {len(unmatched)} 个，总计: {total_output} 个")
        for cat, ch_list in result.items():
            if ch_list:
                logger.info(f"   {cat}: {len(ch_list)} 个频道")
            else:
                logger.info(f"   {cat}: (空)")

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
            "channels": []
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


# 兼容 run.py 调用
def generate_outputs_from_demo(ordered_channels: List[Dict], demo_order: List[Tuple[str, str]]) -> None:
    """供 run.py 调用的兼容函数"""
    generator = Generator()
    generator.generate_all(ordered_channels, demo_order)
