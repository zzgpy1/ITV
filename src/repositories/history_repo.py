# src/repositories/history_repo.py
from src.repositories.base import BaseRepository
from datetime import datetime
from typing import List, Dict

class HistoryRepo(BaseRepository):
    async def add(self, channel_key: str, url: str, latency: int, success: bool):
        await self._execute(
            "INSERT INTO speed_history (channel_key, url, timestamp, latency, success) VALUES (?, ?, ?, ?, ?)",
            (channel_key, url, datetime.now().isoformat(), latency, 1 if success else 0)
        )

    async def get_history(self, channel_key: str, days: int = 30) -> List[Dict]:
        cutoff = (datetime.now().timestamp() - days * 86400)
        rows = await self._fetchall(
            "SELECT timestamp, latency, success FROM speed_history WHERE channel_key = ? AND timestamp > datetime(?, 'unixepoch') ORDER BY timestamp ASC",
            (channel_key, cutoff)
        )
        return [{"timestamp": r[0], "latency": r[1], "success": bool(r[2])} for r in rows]
