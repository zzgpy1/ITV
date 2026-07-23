# src/db.py
import aiosqlite
from pathlib import Path
from src.settings import settings


class Database:
    _instance = None
    _conn: aiosqlite.Connection = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self):
        if self._conn is not None:
            return self._conn
        db_path = settings.data_dir / "iptv.db"
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(db_path))
        # 启用 WAL 模式提高并发性能
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

    def get_connection(self):
        return self._conn


db = Database()
