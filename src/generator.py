# src/services/generator.py
"""生成服务 - 所有频道按Demo已有分类输出，不新增分类"""

import json
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime

from src.core.config import get_config
from src.core.constants import PROVINCES
from src.infrastructure.logger import get_logger
from src.services.demo_service import (
    load_demo_order,
    match_channel_name,
    is_category_match,
    extract_province_from_name,
    get_channel_aliases,
    get_alias_matcher
)

logger = get_logger(__name__)


class Generator:
    """输出生成器"""
    
    def __init__(self):
        self.config = get_config()
        self.alias_matcher = get_alias_matcher()
    
    def generate_all(self, channels: List[Dict], demo_order: List[Tuple[str, str]] = None) -> None:
        """生成所有输出"""
        output_dir = self.config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if demo_order is None:
            demo_order = load_demo_order()
        
        # 先应用别名标准化频道名
        channels = self._normalize_channels_with_alias(channels)
        
        # 按 demo 分类，未匹配的频道自动归类到已有分类
        categorized = self._categorize_by_demo(channels, demo_order)
        
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
    
    def _get_existing_categories(self, demo_order: List[Tuple[str, str]]) -> Dict[str, str]:
        """
        从 demo_order 提取所有已有分类
        返回: {分类名: 分类名}，以及省份到分类名的映射
        """
        categories = set()
        province_to_category = {}
        
        for cat, _ in demo_order:
            categories.add(cat)
            # 如果是 ☘️XX频道 格式，提取省份
            if cat.startswith("☘️"):
                province = cat.replace("☘️", "").replace("频道", "").strip()
                if province:
                    province_to_category[province] = cat
        
        return {
            "all": categories,
            "province_map": province_to_category
        }
    
    def _infer_category(self, channel_name: str, existing_categories: Dict) -> str:
        """
        根据频道名推断应归入的现有分类
        优先匹配已有分类，不创建新分类
        """
        name_lower = channel_name.lower()
        
        # 1. 央视
        cctv_keywords = ["cctv", "央视", "中央电视", "cntv", "cgtn"]
        for kw in cctv_keywords:
            if kw in name_lower:
                if "📺央视频道" in existing_categories["all"]:
                    return "📺央视频道"
                break
        
        # 2. 港澳台
        hk_keywords = ["tvb", "翡翠", "明珠", "凤凰", "无线", "rthk", "hoy", "viu",
                       "东森", "民视", "台视", "华视", "中视", "三立", "纬来", "tvbs",
                       "香港", "澳门", "台湾", "澳视", "八大", "纬来", "中天"]
        for kw in hk_keywords:
            if kw in name_lower:
                if "🌊港·澳·台" in existing_categories["all"]:
                    return "🌊港·澳·台"
                break
        
        # 3. 卫视（省级卫视）
        if "卫视" in channel_name:
            if "📡卫视频道" in existing_categories["all"]:
                return "📡卫视频道"
        
        # 4. 地方频道 - 按省份匹配已有 ☘️XX频道
        for prov in PROVINCES:
            if prov in channel_name:
                # 检查是否有对应的 ☘️XX频道
                if prov in existing_categories["province_map"]:
                    return existing_categories["province_map"][prov]
                # 如果没有，尝试匹配到已有的卫视频道
                if "📡卫视频道" in existing_categories["all"]:
                    return "📡卫视频道"
                break
        
        # 5. 其他 - 归入卫视频道（如果存在）或央视频道（兜底）
        if "📡卫视频道" in existing_categories["all"]:
            return "📡卫视频道"
        elif "📺央视频道" in existing_categories["all"]:
            return "📺央视频道"
        else:
            # 如果以上都不存在，取第一个已有分类
            for cat in existing_categories["all"]:
                return cat
            return "其他"  # 不会发生
    
    def _categorize_by_demo(self, channels: List[Dict], demo_order: List[Tuple[str, str]]) -> Dict[str, List[Dict]]:
        """
        按 demo 顺序分类
        匹配 demo 的频道按顺序输出
        未匹配的频道根据名称自动归入已有分类
        """
        result = {}
        existing = self._get_existing_categories(demo_order)
        
        # 初始化 result，包含所有已有分类
        for cat in existing["all"]:
            result[cat] = []
        
        if not demo_order:
            logger.warning("⚠️ demo_order 为空，使用自动分类")
            for ch in channels:
                cat = self._infer_category(ch["name"], existing)
                result.setdefault(cat, []).append(ch)
            return result
        
        # 构建频道名到频道的映射
        channel_map = {ch["name"]: ch for ch in channels}
        
        # 按省份分组频道（用于分类匹配）
        province_channels = {}
        for ch in channels:
            prov = extract_province_from_name(ch["name"])
            if prov:
                if prov not in province_channels:
                    province_channels[prov] = []
                province_channels[prov].append(ch)
        
        matched_names = set()
        total_matched = 0
        
        # 第一步：按 demo 顺序匹配
        for cat, demo_name in demo_order:
            # 分类匹配（☘️上海频道 → 所有上海频道）
            if is_category_match(demo_name, ""):
                for prefix in ["☘️", "📺", "📡", "🌊"]:
                    if demo_name.startswith(prefix):
                        cat_part = demo_name[len(prefix):].replace("频道", "").strip()
                        if cat_part in province_channels:
                            for ch in province_channels.get(cat_part, []):
                                if ch["name"] not in matched_names:
                                    result[cat].append(ch)
                                    matched_names.add(ch["name"])
                                    total_matched += 1
                            logger.info(f"📌 分类匹配: {demo_name} -> {len(province_channels.get(cat_part, []))} 个频道")
                        break
                continue
            
            # 精确匹配
            if demo_name in channel_map:
                ch = channel_map[demo_name]
                if ch["name"] not in matched_names:
                    matched_names.add(ch["name"])
                    total_matched += 1
                    result[cat].append(ch)
                continue
            
            # 别名匹配
            if self.alias_matcher:
                for name, ch in channel_map.items():
                    if name in matched_names:
                        continue
                    std_name = self.alias_matcher.normalize(name)
                    if std_name == demo_name or demo_name in std_name:
                        matched_names.add(name)
                        total_matched += 1
                        result[cat].append(ch)
                        break
        
        # 第二步：未匹配的频道自动归入已有分类
        unmatched = [ch for ch in channels if ch["name"] not in matched_names]
        if unmatched:
            logger.info(f"📊 未匹配频道: {len(unmatched)} 个，自动归入已有分类")
            for ch in unmatched:
                cat = self._infer_category(ch["name"], existing)
                # cat 一定在 result 中
                result[cat].append(ch)
        
        # 统计输出
        total_output = sum(len(lst) for lst in result.values())
        logger.info(f"📊 Demo 匹配结果: {total_matched} 个，自动归类: {len(unmatched)} 个，总计: {total_output} 个")
        
        for cat, ch_list in result.items():
            if ch_list:
                logger.info(f"   {cat}: {len(ch_list)} 个频道")
            else:
                logger.info(f"   {cat}: (空)")
        
        return result
    
    def _generate_m3u(self, categorized: Dict[str, List[Dict]], path: Path) -> None:
        """生成 M3U"""
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
        """生成 TXT"""
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
        """生成多源 M3U"""
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
        """生成 JSON"""
        data = {
            "version": "2.0",
            "total": len(channels),
            "generated": datetime.now().isoformat(),
            "channels": []
        }
        
        for ch in channels:
            channel_info = {
                "name": ch.get("name", ""),
                "url": ch.get("url", ""),
                "urls": ch.get("urls", []),
                "latency": ch.get("latency"),
                "codec": ch.get("video_codec", ""),
                "category": ch.get("group_title", ""),
                "is_fixed": ch.get("is_fixed", False),
            }
            channel_info = {k: v for k, v in channel_info.items() if v}
            data["channels"].append(channel_info)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ JSON 文件已生成: {path}")
