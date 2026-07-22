# src/repositories/stable_repo.py
from src.repositories.base import BaseRepo
from datetime import datetime
from typing import Dict, Optional

class StableRepo(BaseRepo):
    async def get(self, channel_name: str) -> Optional[Dict]:
        row = await self._fetchone(
            "SELECT channel_name, url, latency, video_codec, is_fixed, auto_optimize, fail_count, status FROM stable_sources WHERE channel_name = ?",
            (channel_name,)
        )
        if row:
            return {"channel_name": row[0], "url": row[1], "latency": row[2], "video_codec": row[3],
                    "is_fixed": bool(row[4]), "auto_optimize": bool(row[5]), "fail_count": row[6], "status": row[7]}
        return None

    async def upsert(self, channel_name: str, url: str, latency: int, video_codec: str = "", is_fixed: bool = False, auto_optimize: bool = False):
        await self._execute(
            """INSERT OR REPLACE INTO stable_sources
               (channel_name, url, latency, video_codec, is_fixed, auto_optimize, promoted_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (channel_name, url, latency, video_codec, 1 if is_fixed else 0, 1 if auto_optimize else 0, datetime.now().isoformat())
        )

    async def delete(self, channel_name: str):
        await self._execute("DELETE FROM stable_sources WHERE channel_name = ?", (channel_name,))

    async def get_all(self) -> Dict[str, Dict]:
        rows = await self._fetchall("SELECT channel_name, url, latency, video_codec, is_fixed, auto_optimize, fail_count, status FROM stable_sources")
        return {r[0]: {"url": r[1], "latency": r[2], "video_codec": r[3], "is_fixed": bool(r[4]), "auto_optimize": bool(r[5]), "fail_count": r[6], "status": r[7]} for r in rows}

    async def record_failure(self, channel_name: str):
        await self._execute(
            "UPDATE stable_sources SET fail_count = fail_count + 1, last_verified = ? WHERE channel_name = ?",
            (datetime.now().isoformat(), channel_name)
        )

    async def record_success(self, channel_name: str):
        await self._execute(
            "UPDATE stable_sources SET fail_count = 0, last_verified = ? WHERE channel_name = ?",
            (datetime.now().isoformat(), channel_name)
        )
