# src/source_pool/discoverer.py
"""源发现器 - 存根实现（避免导入错误）"""

from typing import Dict, List
from src.logger import logger

class SourceDiscoverer:
    def __init__(self, pool_db_path=None):
        logger.warning("⚠️ SourceDiscoverer 使用存根实现，实际功能未启用")
        self.pool = {}

    async def discover(self, db=None, filter_domestic=True, force_refresh=False) -> Dict:
        return {}

    def get_statistics(self) -> dict:
        return {"total": 0, "pending": 0, "verified": 0, "failed": 0, "promoted": 0}
