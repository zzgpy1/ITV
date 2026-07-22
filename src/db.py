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

    async def init(self):
        if self._conn is not None:
            return
        db_path = settings.data_dir / "iptv.db"
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(db_path))
        self._conn.row_factory = aiosqlite.Row
        await self._create_tables()

    async def _create_tables(self):
        await self._conn.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=NORMAL;

            CREATE TABLE IF NOT EXISTS source_pool (
                source_key TEXT PRIMARY KEY,
                channel_name TEXT NOT NULL,
                url TEXT NOT NULL,
                source_url TEXT,
                discovered_at TIMESTAMP,
                last_check TIMESTAMP,
                status TEXT DEFAULT 'pending',
                fail_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                latency INTEGER DEFAULT 0,
                video_codec TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS candidate_pool (
                source_key TEXT PRIMARY KEY,
                channel_name TEXT NOT NULL,
                url TEXT NOT NULL,
                status TEXT DEFAULT 'observing',
                check_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                total_latency INTEGER DEFAULT 0,
                avg_latency INTEGER DEFAULT 0,
                last_check TIMESTAMP,
                discovered_at TIMESTAMP,
                promoted_at TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS stable_sources (
                channel_name TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                latency INTEGER,
                video_codec TEXT,
                is_fixed BOOLEAN DEFAULT 0,
                auto_optimize BOOLEAN DEFAULT 0,
                promoted_at TIMESTAMP,
                last_verified TIMESTAMP,
                fail_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active'
            );

            CREATE TABLE IF NOT EXISTS speed_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_key TEXT,
                url TEXT,
                timestamp TIMESTAMP,
                latency INTEGER,
                success BOOLEAN
            );

            CREATE TABLE IF NOT EXISTS cache (
                cache_key TEXT PRIMARY KEY,
                data TEXT,
                cache_type TEXT,
                updated_at TIMESTAMP,
                ttl_hours INTEGER
            );

            CREATE TABLE IF NOT EXISTS blacklist (
                url TEXT PRIMARY KEY,
                reason TEXT,
                added_at TIMESTAMP,
                fail_count INTEGER DEFAULT 1
            );

            CREATE INDEX IF NOT EXISTS idx_source_status ON source_pool(status);
            CREATE INDEX IF NOT EXISTS idx_candidate_status ON candidate_pool(status);
            CREATE INDEX IF NOT EXISTS idx_stable_channel ON stable_sources(channel_name);
            CREATE INDEX IF NOT EXISTS idx_speed_history_key ON speed_history(channel_key);
            CREATE INDEX IF NOT EXISTS idx_cache_type ON cache(cache_type);
        """)
        await self._conn.commit()

    async def get_connection(self) -> aiosqlite.Connection:
        if self._conn is None:
            await self.init()
        return self._conn

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

db = Database()
