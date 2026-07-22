# src/repository/history_repo.py
from src.repository.base import Repository
from datetime import datetime, timedelta
from typing import List, Dict

class HistoryRepo(Repository):
    async def add(self, channel_key: str, url: str, latency: int, success: bool):
        await self._execute(
            """INSERT INTO speed_history
               (channel_key, url, timestamp, latency, success)
               VALUES (?, ?, ?, ?, ?)""",
            (channel_key, url, datetime.now().isoformat(), latency, 1 if success else 0)
        )
        await self.commit()

    async def get_history(self, channel_key: str, days: int = 30) -> List[Dict]:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cursor = await self._execute(
            "SELECT * FROM speed_history WHERE channel_key = ? AND timestamp > ? ORDER BY timestamp ASC",
            (channel_key, cutoff)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
