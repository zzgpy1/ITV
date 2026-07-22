# src/repository/stable_repo.py
from src.repository.base import Repository
from datetime import datetime
from typing import Optional, Dict, List

class StableRepo(Repository):
    async def upsert(self, channel_name: str, url: str, latency: int = 0,
                     video_codec: str = "", is_fixed: bool = False,
                     auto_optimize: bool = False):
        now = datetime.now().isoformat()
        await self._execute(
            """INSERT OR REPLACE INTO stable_sources
               (channel_name, url, latency, video_codec, is_fixed, auto_optimize, promoted_at, last_verified, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (channel_name, url, latency, video_codec, 1 if is_fixed else 0,
             1 if auto_optimize else 0, now, now, "active")
        )
        await self.commit()

    async def get(self, channel_name: str) -> Optional[Dict]:
        cursor = await self._execute(
            "SELECT * FROM stable_sources WHERE channel_name = ?",
            (channel_name,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_all(self) -> Dict[str, Dict]:
        cursor = await self._execute("SELECT * FROM stable_sources")
        rows = await cursor.fetchall()
        return {row["channel_name"]: dict(row) for row in rows}

    async def get_active(self) -> List[Dict]:
        cursor = await self._execute(
            "SELECT * FROM stable_sources WHERE status = 'active'"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def record_failure(self, channel_name: str):
        await self._execute(
            """UPDATE stable_sources
               SET fail_count = fail_count + 1, last_verified = ?
               WHERE channel_name = ?""",
            (datetime.now().isoformat(), channel_name)
        )
        await self.commit()

    async def record_success(self, channel_name: str):
        await self._execute(
            """UPDATE stable_sources
               SET fail_count = 0, last_verified = ?
               WHERE channel_name = ?""",
            (datetime.now().isoformat(), channel_name)
        )
        await self.commit()

    async def replace_source(self, channel_name: str, new_url: str, latency: int, video_codec: str = ""):
        current = await self.get(channel_name)
        if current and current.get("is_fixed") and not current.get("auto_optimize"):
            return False  # 固定源禁止自动替换
        is_fixed = current.get("is_fixed", False) if current else False
        auto_opt = current.get("auto_optimize", False) if current else False
        await self.upsert(channel_name, new_url, latency, video_codec, is_fixed, auto_opt)
        return True
