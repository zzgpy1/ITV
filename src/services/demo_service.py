# src/services/demo_service.py
"""Demo 服务"""

import re
from pathlib import Path
from typing import List, Tuple, Optional

from src.core.config import get_config
from src.infrastructure.logger import get_logger

logger = get_logger(__name__)

try:
    from pypinyin import lazy_pinyin
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False
    logger.warning("⚠️ pypinyin 未安装，拼音匹配功能不可用")


def load_demo_order(demo_file: Optional[Path] = None) -> List[Tuple[str, str]]:
    """加载 demo 顺序"""
    config = get_config()
    demo_file = demo_file or config.demo_file
    
    if not demo_file.exists():
        logger.warning(f"⚠️ Demo 文件不存在: {demo_file}")
        return []
    
    order = []
    current_category = None
    
    with open(demo_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.endswith(",#genre#") or line.endswith(", #genre#"):
                current_category = line.replace(",#genre#", "").replace(", #genre#", "").strip()
                continue
            if line.startswith('#'):
                continue
            if current_category is not None:
                order.append((current_category, line))
    
    logger.info(f"📋 加载 demo 顺序: {len(order)} 个频道")
    return order


def match_channel_name(channel_name: str, demo_name: str) -> bool:
    """匹配频道名"""
    cn_lower = channel_name.lower()
    dn_lower = demo_name.lower()
    
    # 央视频道数字匹配
    cctv_pattern = re.compile(r'cctv[-\s]*(\d+(?:k)?)', re.IGNORECASE)
    m1 = cctv_pattern.search(channel_name)
    m2 = cctv_pattern.search(demo_name)
    
    if m1 and m2 and m1.group(1).lower() == m2.group(1).lower():
        num = m1.group(1).lower()
        if num in ["4k", "8k"]:
            return True
        if num.isdigit():
            area_keywords = {"欧洲": ["欧洲", "europe"], "美洲": ["美洲", "america"]}
            for kw, variants in area_keywords.items():
                if kw in dn_lower:
                    if not any(v in cn_lower for v in variants):
                        return False
            return True
    
    # 包含匹配
    if dn_lower in cn_lower or cn_lower in dn_lower:
        return True
    
    # 拼音匹配
    if HAS_PYPINYIN:
        def to_pinyin(text):
            return ''.join(lazy_pinyin(text)).lower()
        if to_pinyin(demo_name) in to_pinyin(channel_name):
            return True
    
    # 去特殊字符匹配
    def clean(s):
        return re.sub(r'[^a-zA-Z\u4e00-\u9fa5]', '', s).lower()
    if clean(demo_name) in clean(channel_name):
        return True
    
    return False
