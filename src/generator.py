# src/generator.py
"""输出生成器 - 别名前置 + 城市映射兜底 + Demo 顺序输出 + 非电视内容过滤"""

import json
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
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


# ========== 频道名（英文/别名）→ 可识别中文名（仅用于分类判断，不改变输出名） ==========
CHANNEL_CLASSIFY_ALIAS = {
    # 英文地方台/卫视 → 中文名
    'Baicheng TV': '白城',
    'Siping TV': '四平',
    'Tonghua TV': '通化',
    'Harbin Comprehensive News Channel': '哈尔滨新闻综合',
    'Harbin Movie Channel': '哈尔滨影视',
    'Hebei TV': '河北卫视',
    'Hunan TV': '湖南卫视',
    'Hunan Economy Channel': '湖南经视',
    'Guangdong Satellite TV': '广东卫视',
    'Guangxi Variety & Travel Channel': '广西综艺旅游',
    'Jiangsu Public & News Channel': '江苏公共新闻',
    'Kangba TV': '康巴卫视',
    'Lanzhou Comprehensive News Channel': '兰州新闻综合',
    'Lanzhou Culture & Tourism Channel': '兰州文旅',
    'Jingmen Comprehensive News Channel': '荆门新闻综合',
    'Xizang TV Tibetan': '西藏藏语',
    'Zhejiang International Channel': '浙江国际',
    'Zhejiang TV International': '浙江国际',
    'Yichang Sanxia Travel & Life Channel': '宜昌三峡文旅',
    'Yichang Sanxia General Channel': '宜昌三峡综合',
    'Chaozhou Public Channel': '潮州公共',
    'Chifeng Comprehensive News Chanel': '赤峰综合',
    'Chuxiong News Channel': '楚雄新闻',
    'Dongguan Comprehensive News Channel': '东莞综合',
    'Hebi News Channel': '鹤壁新闻',
    'Nei Monggol TV': '内蒙古卫视',
    'Nei Monggol TV 2 Mongolian Culture Channel': '内蒙古蒙语文化',
    'Anhui TV': '安徽卫视',
    'Guangzhou TV': '广州综合',
    'QTV-1': '青岛新闻综合',
    'QTV-2': '青岛生活',
    'QTV-3': '青岛影视',
    'QTV-4': '青岛教育',
    'QTV-6': '青岛城阳',
    'Xinjiang TV 2': '新疆TV2',
    'Xinjiang TV 3': '新疆TV3',
    'Xinjiang TV 5': '新疆TV5',
    'Xinjiang TV 8': '新疆TV8',

    # 中文别名 → 可识别全名（补省份信息）
    '第一财经': '上海第一财经',
    '数码时代': '浙江数码时代',
    '钱江都市': '浙江钱江都市',
    '长影频道': '吉林长影频道',
}


# ========== 非电视频道内容（直接跳过，不输出） ==========
SKIP_PATTERNS = [
    # 春晚录像
    re.compile(r'\d{4}\s*年?春晚|春晚\s*\d{4}'),
    # 影视片段（短视频平台）
    re.compile(r'倩女幽魂|龙门飞甲|飞碟之谜'),
    # 景区/风景直播
    re.compile(
        r'乌镇|月牙泉|泰山望人松|泰山太平岭|恒山|六盘山|黄果树|黄花城|鼓浪屿|东极岛|'
        r'张家界|崇圣寺|朱鹮|九华山风景区|翡翠湾|芦村远眺|中央电视塔东|^黄山$'
    ),
    # 音乐录像
    re.compile(r'^音乐欣赏$|^音乐现场$'),
    # 熊猫直播
    re.compile(r'熊猫(直|直播)$'),
    # 测试/调试
    re.compile(r'^retest$|^test$'),
    # 外文国际台
    re.compile(
        r'^(RT|VOA|VoA|CNA|Arirang|Newsmax|WionNews|Wild Earth|'
        r'Pet Club TV|Trace Sports|Supreme Master TV|Home Plus|Good|Good 2|'
        r'Bread TV|Beautiful Life TV|ABN China|Angel TV Chinese)(\s|$)',
        re.IGNORECASE
    ),
    # 韩国台
    re.compile(r'^韩国'),
    # 其他明显非电视内容
    re.compile(r'^China Travel$|^Discovering China$'),
]


# ========== 繁体字 → 简体字（用于地名识别） ==========
TRADITIONAL_TO_SIMPLIFIED = {
    '餘': '余', '蕭': '萧', '頻': '频', '廣': '广', '東': '东',
    '電': '电', '視': '视', '臺': '台', '灣': '湾', '體': '体',
    '經': '经', '濟': '济', '線': '线', '門': '门', '華': '华',
    '國': '国', '際': '际', '數': '数', '碼': '码', '時': '时',
    '綜': '综', '藝': '艺', '劇': '剧', '場': '场', '聞': '闻',
    '間': '间', '陽': '阳', '陰': '阴', '縣': '县', '區': '区',
    '鎮': '镇', '鄉': '乡', '莊': '庄', '園': '园', '館': '馆',
    '廳': '厅', '長': '长', '龍': '龙', '鳳': '凤', '鷹': '鹰',
    '遼': '辽', '寧': '宁', '蘇': '苏', '魯': '鲁', '晉': '晋',
    '陝': '陕', '肅': '肃', '雲': '云', '貴': '贵', '瓊': '琼',
    '閩': '闽', '粵': '粤', '贛': '赣', '滬': '沪',
}


class Generator:
    def __init__(self):
        self.alias_matcher = get_alias_matcher()

    # ---------- 名称规范化（仅用于分类判断，不改变输出名） ----------
    def _to_simplified(self, text: str) -> str:
        return ''.join(TRADITIONAL_TO_SIMPLIFIED.get(c, c) for c in text)

    def _normalize_name(self, name: str) -> str:
        # 1. 去清晰度/状态后缀
        cleaned = re.sub(r'\s*\(\d+[pi]\)\s*|\s*\[[^\]]*\]\s*', '', name).strip()
        # 2. 繁简转换
        simplified = self._to_simplified(cleaned)
        # 3. 别名映射
        if simplified in CHANNEL_CLASSIFY_ALIAS:
            return CHANNEL_CLASSIFY_ALIAS[simplified]
        if cleaned in CHANNEL_CLASSIFY_ALIAS:
            return CHANNEL_CLASSIFY_ALIAS[cleaned]
        return simplified

    def _should_skip(self, name: str) -> bool:
        """判断是否为非电视内容，应跳过"""
        for pattern in SKIP_PATTERNS:
            if pattern.search(name):
                return True
        return False

    # ---------- 对外入口 ----------
    def generate_all(self, channels: List[Dict], demo_order: List[Tuple[str, str]] = None) -> None:
        output_dir = config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        if demo_order is None:
            demo_order = parse_demo_order_with_categories()

        # 1) 别名前置
        channels = self._normalize_with_alias(channels)

        # 2) 分类
        categorized = self._categorize_by_demo(channels, demo_order)

        # 3) 输出
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

    # ---------- 分类核心 ----------
    def _infer_category(self, channel_name: str, existing: Dict) -> Optional[str]:
        """
        返回分类名 → 正常归类
        返回 None → 跳过（非电视频道/无法识别）
        """
        mapped = self._normalize_name(channel_name)
        name_lower = mapped.lower()
        all_set = existing["all_set"]

        # 1. 央视
        for kw in ("cctv", "央视", "中央电视", "cntv", "cgtn"):
            if kw in name_lower:
                if CCTV_CATEGORY in all_set:
                    return CCTV_CATEGORY
                break

        # 2. 港澳台
        for kw in ("tvb", "翡翠", "明珠", "凤凰", "无线", "rthk", "hoy", "viu",
                   "东森", "民视", "台视", "华视", "中视", "三立", "纬来", "tvbs",
                   "香港", "澳门", "台湾", "澳视", "八大", "中天"):
            if kw in name_lower:
                if HKMT_CATEGORY in all_set:
                    return HKMT_CATEGORY
                break

        # 3. 卫视
        if "卫视" in mapped:
            if SATELLITE_CATEGORY in all_set:
                return SATELLITE_CATEGORY

        # 4. 地方频道
        prov = detect_province(mapped)
        if prov and prov != "港澳台":
            if prov in existing["province_map"]:
                return existing["province_map"][prov]
            # 有省份但 demo 无对应分类 → 跳过（不兜底到卫视）
            return None

        # 5. 无法识别 → 跳过（不再兜底到卫视）
        return None

    def _categorize_by_demo(self, channels, demo_order):
        existing = self._get_existing_categories(demo_order)
        result = {cat: [] for cat in existing["all"]}

        if not demo_order:
            for ch in channels:
                cat = self._infer_category(ch["name"], existing)
                if cat:
                    result.setdefault(cat, []).append(ch)
            return result

        channel_map = {ch["name"]: ch for ch in channels}

        # 省份分组（排除卫视，避免"湖南卫视"被归入☘️湖南频道）
        province_channels: Dict[str, List[Dict]] = {}
        for ch in channels:
            mapped = self._normalize_name(ch["name"])
            if "卫视" in mapped:
                continue
            prov = detect_province(mapped)
            if prov and prov != "港澳台":
                province_channels.setdefault(prov, []).append(ch)
        for p in province_channels:
            province_channels[p].sort(key=lambda x: x["name"])

        matched = set()
        total_matched = 0

        # 第一遍：具体频道名匹配
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
                    if std == dn or dn in std or std in dn:
                        ch_found = c
                        break
            if ch_found and ch_found["name"] not in matched:
                if self._should_skip(ch_found["name"]):
                    continue
                matched.add(ch_found["name"])
                total_matched += 1
                result[cat].append(ch_found)

        # 第二遍：分类行匹配
        for cat, demo_name in demo_order:
            dn = demo_name.strip()
            if not dn.startswith(CATEGORY_PREFIXES):
                continue
            p = dn[1:].replace("频道", "").strip()
            if p in province_channels:
                added = 0
                for ch in province_channels[p]:
                    if ch["name"] not in matched:
                        if self._should_skip(ch["name"]):
                            continue
                        matched.add(ch["name"])
                        total_matched += 1
                        result[cat].append(ch)
                        added += 1
                if added:
                    logger.info(f"📌 分类匹配: {dn} -> 新增 {added} 个频道")

        # 第三遍：未匹配兜底
        unmatched = [ch for ch in channels if ch["name"] not in matched]
        skipped_count = 0
        if unmatched:
            unmatched.sort(key=lambda x: x["name"])
            for ch in unmatched:
                if self._should_skip(ch["name"]):
                    skipped_count += 1
                    logger.debug(f"⏭️ 跳过非电视内容: {ch['name']}")
                    continue
                cat = self._infer_category(ch["name"], existing)
                if cat:
                    result[cat].append(ch)
                else:
                    skipped_count += 1
                    logger.debug(f"⏭️ 跳过无法归类: {ch['name']}")

        total_out = sum(len(v) for v in result.values())
        logger.info(
            f"📊 Demo 匹配: {total_matched}，未匹配: {len(unmatched)}"
            f"（其中跳过 {skipped_count}），最终输出: {total_out}"
        )
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


def quick_generate_from_stable(stable_sources: Dict[str, Dict], demo_order=None) -> int:
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
