# src/repositories/cache_repo.py
from src.repositories.base import BaseRepository
from datetime import datetime, timedelta
from typing import Optional

class CacheRepo(BaseRepository):
    async def get(self, key: str, cache_type: str = "raw") -> Optional[str]:
        row = await self._fetchone(
            "SELECT data, updated_at, ttl_hours FROM cache WHERE cache_key = ? AND cache_type = ?",
            (key, cache_type)
        )
        if row:
            data, updated_at, ttl = row
            if datetime.now() - datetime.fromisoformat(updated_at) < timedelta(hours=ttl):
                return data
        return None

    async def set(self, key: str, data: str, cache_type: str = "raw", ttl_hours: int = 24):
        await self._execute(
            "INSERT OR REPLACE INTO cache (cache_key, data, cache_type, updated_at, ttl_hours) VALUES (?, ?, ?, ?, ?)",
            (key, data, cache_type, datetime.now().isoformat(), ttl_hours)
        )
