# src/repository/source_repo.py
from src.repository.base import Repository
from datetime import datetime
from typing import Optional, List, Dict

class SourceRepo(Repository):
    async def add(self, source_key: str, channel_name: str, url: str, source_url: str = ""):
        await self._execute(
            """INSERT OR REPLACE INTO source_pool
               (source_key, channel_name, url, source_url, discovered_at, last_check, status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (source_key, channel_name, url, source_url, datetime.now().isoformat(),
             datetime.now().isoformat(), "pending")
        )
        await self.commit()

    async def update_status(self, source_key: str, status: str, latency: int = 0, success: bool = True):
        now = datetime.now().isoformat()
        if success:
            await self._execute(
                """UPDATE source_pool
                   SET status = ?, last_check = ?, latency = ?, success_count = success_count + 1
                   WHERE source_key = ?""",
                (status, now, latency, source_key)
            )
        else:
            await self._execute(
                """UPDATE source_pool
                   SET status = ?, last_check = ?, fail_count = fail_count + 1
                   WHERE source_key = ?""",
                (status, now, source_key)
            )
        await self.commit()

    async def get_pending(self, limit: int = 1000) -> List[Dict]:
        cursor = await self._execute(
            "SELECT * FROM source_pool WHERE status = 'pending' ORDER BY discovered_at ASC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_all(self) -> List[Dict]:
        cursor = await self._execute("SELECT * FROM source_pool")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
