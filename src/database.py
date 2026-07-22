import aiosqlite
from pathlib import Path
from src.settings import settings


class Database:
    def __init__(self):
        self._conn: aiosqlite.Connection = None
        self.db_path = settings.data_dir / "iptv.db"

    async def init(self):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(self.db_path))
        # 启用 WAL 模式，提高并发性能
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._create_tables()
        return self

    async def _create_tables(self):
        await self._conn.execute("""
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
            )
        """)
        await self._conn.execute("""
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
            )
        """)
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS stable_sources (
                channel_name TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                latency INTEGER,
                video_codec TEXT,
                is_fixed INTEGER DEFAULT 0,
                auto_optimize INTEGER DEFAULT 0,
                promoted_at TIMESTAMP,
                last_verified TIMESTAMP,
                fail_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active'
            )
        """)
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS speed_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_key TEXT,
                url TEXT,
                timestamp TIMESTAMP,
                latency INTEGER,
                success INTEGER
            )
        """)
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                cache_key TEXT PRIMARY KEY,
                data TEXT,
                cache_type TEXT,
                updated_at TIMESTAMP,
                ttl_hours INTEGER
            )
        """)
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                url TEXT PRIMARY KEY,
                reason TEXT,
                added_at TIMESTAMP,
                fail_count INTEGER DEFAULT 1
            )
        """)
        await self._conn.execute("CREATE INDEX IF NOT EXISTS idx_source_status ON source_pool(status)")
        await self._conn.execute("CREATE INDEX IF NOT EXISTS idx_candidate_status ON candidate_pool(status)")
        await self._conn.execute("CREATE INDEX IF NOT EXISTS idx_stable_channel ON stable_sources(channel_name)")
        await self._conn.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()


_db: Database = None


async def get_db() -> Database:
    global _db
    if _db is None:
        _db = await Database().init()
    return _db
