# src/repositories/base.py
import aiosqlite
from typing import Optional, List, Tuple


class BaseRepository:
    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn

    async def _execute(self, sql: str, params: tuple = ()):
        cursor = await self._conn.execute(sql, params)
        await self._conn.commit()
        return cursor

    async def _fetchone(self, sql: str, params: tuple = ()):
        cursor = await self._conn.execute(sql, params)
        row = await cursor.fetchone()
        await cursor.close()
        return row

    async def _fetchall(self, sql: str, params: tuple = ()):
        cursor = await self._conn.execute(sql, params)
        rows = await cursor.fetchall()
        await cursor.close()
        return rows
