# src/repository/base.py
import aiosqlite
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Dict

class Repository(ABC):
    def __init__(self, conn: aiosqlite.Connection):
        self.conn = conn

    async def _execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        return await self.conn.execute(sql, params)

    async def _executemany(self, sql: str, params: List[tuple]) -> None:
        await self.conn.executemany(sql, params)

    async def commit(self):
        await self.conn.commit()
