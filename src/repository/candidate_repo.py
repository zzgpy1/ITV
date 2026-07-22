# src/repository/candidate_repo.py
from src.repository.base import Repository
from datetime import datetime
from typing import List, Dict, Optional

class CandidateRepo(Repository):
    async def add(self, source_key: str, channel_name: str, url: str):
        now = datetime.now().isoformat()
        await self._execute(
            """INSERT OR REPLACE INTO candidate_pool
               (source_key, channel_name, url, discovered_at, last_check, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (source_key, channel_name, url, now, now, "observing")
        )
        await self.commit()

    async def update_latency(self, source_key: str, latency: int, success: bool):
        now = datetime.now().isoformat()
        if success:
            await self._execute(
                """UPDATE candidate_pool
                   SET check_count = check_count + 1,
                       success_count = success_count + 1,
                       total_latency = total_latency + ?,
                       avg_latency = (total_latency + ?) / (success_count + 1),
                       last_check = ?
                   WHERE source_key = ?""",
                (latency, latency, now, source_key)
            )
        else:
            await self._execute(
                """UPDATE candidate_pool
                   SET check_count = check_count + 1,
                       fail_count = fail_count + 1,
                       last_check = ?
                   WHERE source_key = ?""",
                (now, source_key)
            )
        await self.commit()

    async def get_stable_candidates(self) -> List[Dict]:
        cursor = await self._execute(
            "SELECT * FROM candidate_pool WHERE status = 'stable'"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_observing(self, limit: int = 1000) -> List[Dict]:
        cursor = await self._execute(
            "SELECT * FROM candidate_pool WHERE status = 'observing' ORDER BY discovered_at ASC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def promote(self, source_key: str):
        now = datetime.now().isoformat()
        await self._execute(
            "UPDATE candidate_pool SET status = 'promoted', promoted_at = ? WHERE source_key = ?",
            (now, source_key)
        )
        await self.commit()

    async def mark_stable(self, source_key: str):
        await self._execute(
            "UPDATE candidate_pool SET status = 'stable' WHERE source_key = ?",
            (source_key,)
        )
        await self.commit()
