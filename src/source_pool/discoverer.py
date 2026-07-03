# src/source_pool/discoverer.py
"""源发现器 - 多源抓取、去重、入库，支持国内频道过滤和强制刷新"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.config import IPTV_SOURCES
from src.fetcher import fetch_all_sources_incremental
from src.parser import parse_and_dedupe
from src.database import get_db_cache
from src.logger import logger
from src.source_pool.models import RawSource, SourceStatus

# ========== 国内频道关键词（用于过滤） ==========
DOMESTIC_KEYWORDS = [
    "CCTV", "央视", "中央", "CGTN",
    "卫视", "东方卫视", "北京卫视", "湖南卫视", "浙江卫视", "江苏卫视",
    "广东卫视", "深圳卫视", "天津卫视", "山东卫视", "安徽卫视",
    "湖北卫视", "黑龙江卫视", "江西卫视", "河南卫视", "河北卫视",
    "山西卫视", "陕西卫视", "甘肃卫视", "宁夏卫视", "青海卫视",
    "云南卫视", "贵州卫视", "广西卫视", "内蒙古卫视", "新疆卫视",
    "西藏卫视", "海南卫视", "东南卫视", "重庆卫视", "四川卫视",
    "辽宁卫视", "吉林卫视", "厦门卫视", "大湾区卫视", "海峡卫视",
    "电视台", "综合频道", "新闻频道", "都市频道", "生活频道",
    "影视", "少儿", "公共", "经济", "科教", "文艺", "体育",
    "北京", "上海", "广东", "浙江", "江苏", "湖南", "湖北",
    "山东", "河南", "四川", "福建", "安徽", "辽宁", "陕西",
    "河北", "江西", "黑龙江", "吉林", "山西", "云南", "贵州",
    "甘肃", "海南", "青海", "宁夏", "新疆", "西藏", "广西",
    "内蒙古", "香港", "澳门", "台湾",
    "凤凰", "翡翠", "明珠", "TVB", "无线", "RTHK", "HOY",
    "东森", "民视", "台视", "华视", "中视", "三立", "纬来"
]

def is_domestic_channel(channel_name: str) -> bool:
    name_lower = channel_name.lower()
    for kw in DOMESTIC_KEYWORDS:
        if kw.lower() in name_lower:
            return True
    return False

class SourceDiscoverer:
    """源发现器 - 负责从多个源抓取新源，支持国内频道过滤"""
    
    def __init__(self, pool_db_path: Path = None):
        self.pool_db_path = pool_db_path or Path("data/source_pool.json")
        self.pool_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.pool: Dict[str, RawSource] = {}
        self._load_pool()
    
    def _load_pool(self):
        if self.pool_db_path.exists():
            try:
                with open(self.pool_db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for key, value in data.items():
                        value["discovered_at"] = datetime.fromisoformat(value["discovered_at"])
                        if value.get("last_check"):
                            value["last_check"] = datetime.fromisoformat(value["last_check"])
                        self.pool[key] = RawSource.from_dict(value)
                logger.info(f"📦 加载源池: {len(self.pool)} 个源")
            except Exception as e:
                logger.warning(f"加载源池失败: {e}")
                self.pool = {}
    
def _save_pool(self):
    try:
        data = {}
        for key, value in self.pool.items():
            item = value.to_dict()
            # 确保日期字段是 datetime 对象，如果是字符串则跳过
            if isinstance(item.get("discovered_at"), datetime):
                item["discovered_at"] = item["discovered_at"].isoformat()
            if item.get("last_check") and isinstance(item["last_check"], datetime):
                item["last_check"] = item["last_check"].isoformat()
            data[key] = item
        with open(self.pool_db_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"保存源池失败: {e}")
    
    async def discover(self, db=None, filter_domestic: bool = True, force_refresh: bool = False) -> Dict[str, List[RawSource]]:
        """发现新源，按频道名分组"""
        logger.info("🔍 开始发现新源..." + (" (仅国内频道)" if filter_domestic else ""))
        
        raw_contents = await fetch_all_sources_incremental(IPTV_SOURCES, db, force_refresh)
        channels_dict = parse_and_dedupe(raw_contents)
        
        new_sources = []
        existing_keys = set(self.pool.keys())
        
        total_count = len(channels_dict)
        filtered_count = 0
        
        for ch in channels_dict.values():
            if filter_domestic and not is_domestic_channel(ch["name"]):
                filtered_count += 1
                continue
            
            raw_source = RawSource(
                url=ch["url"],
                channel_name=ch["name"],
                source_url=ch.get("source_url", "unknown"),
                discovered_at=datetime.now(),
                status=SourceStatus.PENDING
            )
            key = raw_source.get_key()
            
            if key not in existing_keys:
                self.pool[key] = raw_source
                new_sources.append(raw_source)
            else:
                self.pool[key].last_check = datetime.now()
        
        self._save_pool()
        
        grouped = {}
        for src in new_sources:
            if src.channel_name not in grouped:
                grouped[src.channel_name] = []
            grouped[src.channel_name].append(src)
        
        logger.info(f"✅ 发现新源: {len(new_sources)} 个，涉及 {len(grouped)} 个频道")
        if filter_domestic:
            logger.info(f"📊 过滤掉 {filtered_count} 个国外频道（保留国内频道）")
        
        return grouped
    
    def get_pending_sources(self, limit: int = 100) -> List[RawSource]:
        pending = [s for s in self.pool.values() if s.status == SourceStatus.PENDING]
        return sorted(pending, key=lambda x: x.discovered_at)[:limit]
    
    def get_failed_sources(self, max_fail_count: int = 3) -> List[RawSource]:
        return [s for s in self.pool.values() if s.fail_count >= max_fail_count]
    
    def update_source_status(self, source_key: str, status: str, 
                              latency: int = 0, success: bool = True):
        if source_key in self.pool:
            self.pool[source_key].status = status
            self.pool[source_key].last_check = datetime.now()
            if success:
                self.pool[source_key].success_count += 1
                self.pool[source_key].latency = latency
            else:
                self.pool[source_key].fail_count += 1
            self._save_pool()
    
    def get_statistics(self) -> dict:
        stats = {
            "total": len(self.pool),
            "pending": sum(1 for s in self.pool.values() if s.status == SourceStatus.PENDING),
            "verified": sum(1 for s in self.pool.values() if s.status == SourceStatus.VERIFIED),
            "failed": sum(1 for s in self.pool.values() if s.status == SourceStatus.FAILED),
            "promoted": sum(1 for s in self.pool.values() if s.status == SourceStatus.PROMOTED),
        }
        return stats
