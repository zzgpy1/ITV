# src/repository/cache_repo.py
from src.repository.base import Repository
from datetime import datetime, timedelta
from typing import Optional

class CacheRepo(Repository):
    async def get(self, cache_key: str, cache_type: str, max_age_hours: int) -> Optional[str]:
        cursor = await self._execute(
            "SELECT data, updated_at FROM cache WHERE cache_key = ? AND cache_type = ?",
            (cache_key, cache_type)
        )
        row = await cursor.fetchone()
        if row:
            updated_at = datetime.fromisoformat(row["updated_at"])
            if datetime.now() - updated_at < timedelta(hours=max_age_hours):
                return row["data"]
        return None

    async def set(self, cache_key: str, data: str, cache_type: str, ttl_hours: int):
        await self._execute(
            """INSERT OR REPLACE INTO cache (cache_key, data, cache_type, updated_at, ttl_hours)
               VALUES (?, ?, ?, ?, ?)""",
            (cache_key, data, cache_type, datetime.now().isoformat(), ttl_hours)
        )
        await self.commit()
