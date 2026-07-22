# src/repositories/source_repo.py
from src.repositories.base import BaseRepo
from datetime import datetime
from typing import List, Dict

class SourceRepo(BaseRepo):
    async def add(self, source_key: str, channel_name: str, url: str, source_url: str):
        await self._execute(
            """INSERT OR REPLACE INTO source_pool
               (source_key, channel_name, url, source_url, discovered_at, last_check)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (source_key, channel_name, url, source_url, datetime.now().isoformat(), datetime.now().isoformat())
        )

    async def get_pending(self, limit: int = 1000) -> List[Dict]:
        rows = await self._fetchall(
            "SELECT source_key, channel_name, url FROM source_pool WHERE status = 'pending' LIMIT ?",
            (limit,)
        )
        return [{"key": r[0], "name": r[1], "url": r[2]} for r in rows]

    async def update_status(self, source_key: str, status: str, latency: int = 0, success: bool = True):
        await self._execute(
            """UPDATE source_pool SET status = ?, last_check = ?, latency = ?,
               success_count = success_count + ?, fail_count = fail_count + ?
               WHERE source_key = ?""",
            (status, datetime.now().isoformat(), latency,
             1 if success else 0, 0 if success else 1, source_key)
        )
