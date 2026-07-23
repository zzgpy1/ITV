# src/repositories/__init__.py
from src.db import db
from src.repositories.source_repo import SourceRepo
from src.repositories.candidate_repo import CandidateRepo
from src.repositories.stable_repo import StableRepo
from src.repositories.history_repo import HistoryRepo
from src.repositories.cache_repo import CacheRepo


class RepoFactory:
    def __init__(self):
        self._conn = None
        self.source: SourceRepo = None
        self.candidate: CandidateRepo = None
        self.stable: StableRepo = None
        self.history: HistoryRepo = None
        self.cache: CacheRepo = None
        self._initialized = False

    async def init(self):
        """初始化所有 repository，如果已初始化则跳过"""
        if self._initialized and self._conn is not None:
            return
        self._conn = await db.connect()
        self.source = SourceRepo(self._conn)
        self.candidate = CandidateRepo(self._conn)
        self.stable = StableRepo(self._conn)
        self.history = HistoryRepo(self._conn)
        self.cache = CacheRepo(self._conn)
        self._initialized = True
        # 确保表存在
        await self._ensure_tables()

    async def _ensure_tables(self):
        """确保所有表已创建"""
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
                latency INTEGER DEFAULT 0
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
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS system_status (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP
            )
        """)
        await self._conn.commit()

    async def close(self):
        if self._conn:
            await db.close()
            self._conn = None
            self._initialized = False


repo_factory = RepoFactory()
