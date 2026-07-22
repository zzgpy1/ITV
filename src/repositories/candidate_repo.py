# src/repositories/candidate_repo.py
from src.repositories.base import BaseRepo
from datetime import datetime
from typing import List, Dict

class CandidateRepo(BaseRepo):
    async def add(self, source_key: str, channel_name: str, url: str):
        await self._execute(
            """INSERT OR REPLACE INTO candidate_pool
               (source_key, channel_name, url, discovered_at, last_check)
               VALUES (?, ?, ?, ?, ?)""",
            (source_key, channel_name, url, datetime.now().isoformat(), datetime.now().isoformat())
        )

    async def update_latency(self, source_key: str, latency: int, success: bool):
        await self._execute(
            """UPDATE candidate_pool SET
               check_count = check_count + 1,
               success_count = success_count + ?,
               fail_count = fail_count + ?,
               total_latency = total_latency + ?,
               avg_latency = (total_latency + ?) / (success_count + ?),
               last_check = ?
               WHERE source_key = ?""",
            (1 if success else 0, 0 if success else 1,
             latency if success else 0, latency if success else 0,
             1 if success else 0, datetime.now().isoformat(), source_key)
        )

    async def get_observing(self, limit: int = 1000) -> List[Dict]:
        rows = await self._fetchall(
            "SELECT source_key, channel_name, url FROM candidate_pool WHERE status = 'observing' LIMIT ?",
            (limit,)
        )
        return [{"key": r[0], "name": r[1], "url": r[2]} for r in rows]

    async def get_stable_candidates(self) -> List[Dict]:
        rows = await self._fetchall(
            "SELECT source_key, channel_name, url, avg_latency, success_count, fail_count FROM candidate_pool WHERE status = 'stable'"
        )
        return [{"key": r[0], "name": r[1], "url": r[2], "latency": r[3], "success": r[4], "fail": r[5]} for r in rows]

    async def promote(self, source_key: str):
        await self._execute(
            "UPDATE candidate_pool SET status = 'promoted', promoted_at = ? WHERE source_key = ?",
            (datetime.now().isoformat(), source_key)
        )

    async def mark_stable(self, source_key: str):
        await self._execute(
            "UPDATE candidate_pool SET status = 'stable' WHERE source_key = ?",
            (source_key,)
        )
