# src/managers/candidate_manager.py
"""候选源管理器"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.infrastructure.logger import get_logger

logger = get_logger(__name__)


class CandidateManager:
    """候选源管理器"""
    
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self._candidates: Dict[str, Dict] = {}
        self._load()
    
    def _load(self):
        pool_file = self.data_dir / "candidate_pool.json"
        if pool_file.exists():
            try:
                with open(pool_file, 'r', encoding='utf-8') as f:
                    self._candidates = json.load(f)
                logger.info(f"📦 加载候选池: {len(self._candidates)} 个候选源")
            except Exception as e:
                logger.warning(f"加载候选池失败: {e}")
    
    def _save(self):
        pool_file = self.data_dir / "candidate_pool.json"
        try:
            with open(pool_file, 'w', encoding='utf-8') as f:
                json.dump(self._candidates, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存候选池失败: {e}")
    
    def add_candidate(self, key: str, name: str, url: str):
        if key not in self._candidates:
            self._candidates[key] = {
                "key": key,
                "name": name,
                "url": url,
                "status": "observing",
                "discovered_at": datetime.now().isoformat(),
                "last_check": datetime.now().isoformat(),
                "success_count": 0,
                "fail_count": 0,
                "avg_latency": 0,
            }
            self._save()
    
    def get_observing_sources(self, limit: int = 100) -> List[Dict]:
        observing = [
            c for c in self._candidates.values() 
            if c.get("status") == "observing"
        ]
        return sorted(observing, key=lambda x: x.get("discovered_at", ""))[:limit]
    
    def get_stable_sources(self) -> List[Dict]:
        return [
            c for c in self._candidates.values() 
            if c.get("status") == "stable"
        ]
    
    def get_observing_count(self) -> int:
        return sum(1 for c in self._candidates.values() if c.get("status") == "observing")
    
    def batch_update(self, candidates: List[Dict]):
        for cand in candidates:
            key = cand.get("key")
            if key and key in self._candidates:
                self._candidates[key].update(cand)
        self._save()
    
    def mark_promoted(self, key: str):
        if key in self._candidates:
            self._candidates[key]["status"] = "promoted"
            self._candidates[key]["promoted_at"] = datetime.now().isoformat()
            self._save()
    
    def get_statistics(self) -> Dict[str, int]:
        stats = {
            "total": len(self._candidates),
            "observing": self.get_observing_count(),
            "stable": sum(1 for c in self._candidates.values() if c.get("status") == "stable"),
            "promoted": sum(1 for c in self._candidates.values() if c.get("status") == "promoted"),
            "rejected": sum(1 for c in self._candidates.values() if c.get("status") == "rejected"),
        }
        return stats
