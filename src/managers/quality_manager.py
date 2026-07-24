# src/managers/quality_manager.py
"""质量管理器"""

from datetime import datetime
from typing import List, Dict

from src.infrastructure.database import get_db
from src.infrastructure.logger import get_logger

logger = get_logger(__name__)


class QualityManager:
    """质量管理器"""
    
    def __init__(self, stable_manager):
        self.stable_manager = stable_manager
        self.CHECK_WINDOW = 10
        self.LATENCY_WARN = 3000
        self.LATENCY_CRITICAL = 5000
    
    async def check_all(self) -> List[Dict]:
        """检查所有稳定源"""
        sources = await self.stable_manager.get_active_sources()
        if not sources:
            return []
        
        logger.info(f"🔍 检查 {len(sources)} 个稳定源质量...")
        
        db = await get_db()
        reports = []
        
        for name, src in sources.items():
            if src.get("is_fixed"):
                continue
            
            # 查询最近历史
            rows = await db.fetch_all(
                """SELECT latency, success FROM speed_history 
                   WHERE channel_key LIKE ? ORDER BY timestamp DESC LIMIT ?""",
                (f"%{name}%", self.CHECK_WINDOW)
            )
            
            if len(rows) < 3:
                continue
            
            success_count = sum(1 for r in rows if r["success"])
            success_rate = success_count / len(rows)
            
            latencies = [r["latency"] for r in rows if r["success"] and r["latency"] > 0]
            avg_latency = sum(latencies) // max(len(latencies), 1) if latencies else 9999
            
            consecutive_fails = 0
            for r in reversed(rows):
                if not r["success"]:
                    consecutive_fails += 1
                else:
                    break
            
            if consecutive_fails >= 3 or success_rate < 0.5 or avg_latency > self.LATENCY_CRITICAL:
                status = "critical"
            elif success_rate < 0.8 or avg_latency > self.LATENCY_WARN:
                status = "warning"
            else:
                status = "healthy"
            
            if status in ("warning", "critical"):
                logger.warning(f"⚠️ {name}: {status} (成功率 {success_rate:.2%}, 延迟 {avg_latency}ms)")
            
            reports.append({
                "channel_name": name,
                "status": status,
                "success_rate": success_rate,
                "avg_latency": avg_latency,
                "sample_count": len(rows),
                "consecutive_fails": consecutive_fails,
            })
        
        return reports
