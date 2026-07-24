# src/services/parser.py
"""解析服务"""

import re
from typing import List, Dict, Optional, Tuple

from src.core.constants import PROVINCES, HK_MACAU_TAIWAN_KEYWORDS
from src.infrastructure.logger import get_logger

logger = get_logger(__name__)


def infer_category_from_name(name: str) -> str:
    """从名称推断分类"""
    name_lower = name.lower()
    
    if any(kw in name_lower for kw in ["tvb", "翡翠", "明珠", "无线", "rthk", "hoy", "viu", "香港"]):
        return "香港频道"
    if any(kw in name_lower for kw in ["澳视", "澳门", "macau", "tdm"]):
        return "澳门频道"
    if any(kw in name_lower for kw in ["东森", "民视", "台视", "华视", "中视", "三立", "纬来", "tvbs"]):
        return "台湾频道"
    if any(kw in name_lower for kw in ["nhk", "japan", "tokyo", "fuji", "tbs", "日本"]):
        return "日本频道"
    
    return "其他"


def parse_m3u(content: str, source_url: str = "") -> List[Dict[str, str]]:
    """解析 M3U 格式"""
    channels = []
    lines = content.splitlines()
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            group_title = ""
            tvg_id = ""
            tvg_logo = ""
            
            match = re.search(r'group-title="([^"]+)"', line)
            if match:
                group_title = match.group(1)
            
            match = re.search(r'tvg-id="([^"]+)"', line)
            if match:
                tvg_id = match.group(1)
            
            match = re.search(r'tvg-logo="([^"]+)"', line)
            if match:
                tvg_logo = match.group(1)
            
            parts = line.split(",")
            name = ",".join(parts[1:]).strip() if len(parts) >= 2 else line
            
            if not group_title:
                group_title = infer_category_from_name(name)
            
            if i + 1 < len(lines) and not lines[i + 1].startswith("#"):
                url = lines[i + 1].strip()
                if url.startswith(("http://", "https://", "rtmp://", "rtsp://")):
                    channels.append({
                        "name": name,
                        "url": url,
                        "group_title": group_title,
                        "tvg_id": tvg_id,
                        "tvg_logo": tvg_logo,
                        "source_url": source_url,
                    })
            i += 2
        else:
            i += 1
    
    return channels


def parse_txt(content: str, source_url: str = "") -> List[Dict[str, str]]:
    """解析 TXT 格式"""
    channels = []
    lines = content.splitlines()
    current_name = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            if not line.startswith("#EXT"):
                current_name = line.lstrip("#").strip()
            continue
        if line.startswith(("http://", "https://", "rtmp://", "rtsp://")):
            name = current_name if current_name else "未知频道"
            channels.append({
                "name": name,
                "url": line,
                "group_title": "",
                "tvg_id": "",
                "tvg_logo": "",
                "source_url": source_url,
            })
            current_name = None
    
    return channels


def parse_content(content: str, source_url: str = "") -> List[Dict[str, str]]:
    """自动识别格式并解析"""
    if not content:
        return []
    
    if content.strip().startswith("#EXTM3U"):
        return parse_m3u(content, source_url)
    else:
        return parse_txt(content, source_url)


def apply_alias_to_channels(channels: List[Dict], alias_matcher) -> List[Dict]:
    """应用别名映射"""
    if not alias_matcher:
        return channels
    
    for ch in channels:
        original = ch.get("name", "")
        normalized = alias_matcher.normalize(original)
        if normalized != original:
            ch["name"] = normalized
    
    return channels
