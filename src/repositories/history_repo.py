# src/repositories/history_repo.py
from src.repositories.base import BaseRepository
from datetime import datetime, timedelta
from typing import List, Dict


class HistoryRepo(BaseRepository):
    async def add(self, channel_key: str, url: str, latency: int, success: bool):
        await self._execute(
            "INSERT INTO speed_history (channel_key, url, timestamp, latency, success) VALUES (?, ?, ?, ?, ?)",
            (channel_key, url, datetime.now().isoformat(), latency, 1 if success else 0)
        )

    async def get_history(self, channel_key: str, days: int = 30) -> List[Dict]:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        rows = await self._fetchall(
            "SELECT timestamp, latency, success FROM speed_history WHERE channel_key = ? AND timestamp > ? ORDER BY timestamp ASC",
            (channel_key, cutoff)
        )
        return [{"timestamp": r[0], "latency": r[1], "success": bool(r[2])} for r in rows]

    async def get_recent_stats(self, channel_key: str, limit: int = 10) -> Dict:
        rows = await self._fetchall(
            "SELECT success, latency FROM speed_history WHERE channel_key = ? ORDER BY timestamp DESC LIMIT ?",
            (channel_key, limit)
        )
        if not rows:
            return {"success_rate": 0, "avg_latency": 0, "count": 0}
        total = len(rows)
        success_count = sum(1 for r in rows if r[0])
        latencies = [r[1] for r in rows if r[1] > 0]
        avg_lat = sum(latencies) // len(latencies) if latencies else 0
        return {"success_rate": success_count / total, "avg_latency": avg_lat, "count": total}
