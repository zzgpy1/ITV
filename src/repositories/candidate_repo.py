# src/repositories/candidate_repo.py
from src.repositories.base import BaseRepository
from datetime import datetime
from typing import List, Dict


class CandidateRepo(BaseRepository):
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

    async def get_stats(self, source_key: str) -> Dict:
        row = await self._fetchone(
            "SELECT check_count, success_count, fail_count, avg_latency FROM candidate_pool WHERE source_key = ?",
            (source_key,)
        )
        if row:
            return {"check_count": row[0], "success_count": row[1], "fail_count": row[2], "avg_latency": row[3]}
        return {"check_count": 0, "success_count": 0, "fail_count": 0, "avg_latency": 0}

    async def get_all_for_output(self, limit: int = 500) -> List[Dict]:
        """获取所有候选源用于输出补充"""
        rows = await self._fetchall(
            "SELECT source_key, channel_name, url, avg_latency FROM candidate_pool WHERE status IN ('stable', 'observing') LIMIT ?",
            (limit,)
        )
        return [{"key": r[0], "name": r[1], "url": r[2], "latency": r[3] or 9999} for r in rows]
