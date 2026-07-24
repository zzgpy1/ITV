# src/managers/source_manager.py
"""源管理器"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from src.core.config import get_config
from src.core.exceptions import FetchError
from src.infrastructure.database import get_db, channel_key
from src.infrastructure.http_client import get_http_client
from src.infrastructure.logger import get_logger
from src.services.fetcher import fetch_source
from src.services.parser import parse_content

logger = get_logger(__name__)


class SourceManager:
    """源管理器"""
    
    DOMESTIC_KEYWORDS: Set[str] = {
        "CCTV", "央视", "中央", "CGTN", "卫视", "电视台",
        "北京", "上海", "广东", "浙江", "江苏", "湖南", "湖北",
        "山东", "河南", "四川", "福建", "安徽", "辽宁", "陕西",
        "河北", "江西", "黑龙江", "吉林", "山西", "云南", "贵州",
        "甘肃", "海南", "青海", "宁夏", "新疆", "西藏", "广西",
        "内蒙古", "香港", "澳门", "台湾",
        "凤凰", "翡翠", "明珠", "TVB", "无线",
    }
    
    def __init__(self, data_dir: Optional[Path] = None):
        config = get_config()
        self.data_dir = data_dir or config.data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self._source_pool: Dict[str, Dict] = {}
        self._load_pool()
    
    def _load_pool(self):
        pool_file = self.data_dir / "source_pool.json"
        if pool_file.exists():
            try:
                with open(pool_file, 'r', encoding='utf-8') as f:
                    self._source_pool = json.load(f)
                logger.info(f"📦 加载源池: {len(self._source_pool)} 个源")
            except Exception as e:
                logger.warning(f"加载源池失败: {e}")
    
    def _save_pool(self):
        pool_file = self.data_dir / "source_pool.json"
        try:
            with open(pool_file, 'w', encoding='utf-8') as f:
                json.dump(self._source_pool, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存源池失败: {e}")
    
    @staticmethod
    def is_domestic(channel_name: str) -> bool:
        name_lower = channel_name.lower()
        for kw in SourceManager.DOMESTIC_KEYWORDS:
            if kw.lower() in name_lower:
                return True
        return False
    
    async def discover_sources(self, source_urls: List[str], 
                               filter_domestic: bool = True,
                               force_refresh: bool = False) -> Dict[str, List[Dict]]:
        """发现新源"""
        logger.info(f"🔍 发现新源: {len(source_urls)} 个源")
        
        http_client = await get_http_client()
        db = await get_db()
        
        new_sources = {}
        filtered_count = 0
        
        for url in source_urls:
            try:
                content = await fetch_source(url, db, force_refresh, http_client)
                if not content:
                    continue
                
                channels = parse_content(content, url)
                for channel in channels:
                    if filter_domestic and not self.is_domestic(channel["name"]):
                        filtered_count += 1
                        continue
                    
                    key = channel_key(channel["name"], channel["url"])
                    if key not in self._source_pool:
                        self._source_pool[key] = {
                            "url": channel["url"],
                            "channel_name": channel["name"],
                            "source_url": url,
                            "discovered_at": datetime.now().isoformat(),
                            "status": "pending",
                            "fail_count": 0,
                            "success_count": 0,
                        }
                        
                        if channel["name"] not in new_sources:
                            new_sources[channel["name"]] = []
                        new_sources[channel["name"]].append(channel)
                
            except FetchError as e:
                logger.warning(f"拉取源失败 {url}: {e}")
            except Exception as e:
                logger.error(f"处理源失败 {url}: {e}")
        
        self._save_pool()
        
        total_new = sum(len(v) for v in new_sources.values())
        logger.info(f"✅ 发现新源: {total_new} 个，涉及 {len(new_sources)} 个频道")
        if filter_domestic:
            logger.info(f"📊 过滤掉 {filtered_count} 个国外频道")
        
        return new_sources
    
    def get_pending_sources(self, limit: int = 100) -> List[Dict]:
        pending = [
            s for s in self._source_pool.values() 
            if s.get("status") == "pending"
        ]
        return sorted(pending, key=lambda x: x.get("discovered_at", ""))[:limit]
    
    def update_source_status(self, key: str, status: str, 
                             latency: int = 0, success: bool = True) -> None:
        if key in self._source_pool:
            self._source_pool[key]["status"] = status
            self._source_pool[key]["last_check"] = datetime.now().isoformat()
            if success:
                self._source_pool[key]["success_count"] = self._source_pool[key].get("success_count", 0) + 1
                self._source_pool[key]["latency"] = latency
            else:
                self._source_pool[key]["fail_count"] = self._source_pool[key].get("fail_count", 0) + 1
            self._save_pool()
    
    def get_statistics(self) -> Dict[str, int]:
        stats = {
            "total": len(self._source_pool),
            "pending": sum(1 for s in self._source_pool.values() if s.get("status") == "pending"),
            "verified": sum(1 for s in self._source_pool.values() if s.get("status") == "verified"),
            "failed": sum(1 for s in self._source_pool.values() if s.get("status") == "failed"),
            "promoted": sum(1 for s in self._source_pool.values() if s.get("status") == "promoted"),
        }
        return stats
