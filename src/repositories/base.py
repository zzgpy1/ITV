# src/repositories/base.py
import aiosqlite

class BaseRepo:
    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn

    async def _execute(self, sql: str, params=()):
        async with self._conn.execute(sql, params) as cursor:
            await self._conn.commit()
            return cursor

    async def _fetchone(self, sql: str, params=()):
        async with self._conn.execute(sql, params) as cursor:
            return await cursor.fetchone()

    async def _fetchall(self, sql: str, params=()):
        async with self._conn.execute(sql, params) as cursor:
            return await cursor.fetchall()
