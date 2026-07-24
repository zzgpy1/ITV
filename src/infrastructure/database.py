# src/infrastructure/database.py
"""数据库连接池"""

import asyncio
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any
from contextlib import asynccontextmanager

import aiosqlite

from src.core.config import get_config
from src.core.exceptions import DatabaseError
from src.infrastructure.logger import get_logger

logger = get_logger(__name__)


class DatabasePool:
    """数据库连接池管理器"""
    
    _instance: Optional["DatabasePool"] = None
    _pool: Optional[aiosqlite.Connection] = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def initialize(self) -> None:
        """初始化数据库连接"""
        if self._pool is not None:
            return
        
        config = get_config()
        if not config.database_enable:
            logger.info("📦 数据库已禁用")
            return
        
        db_path = config.data_dir / "iptv_cache.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            self._pool = await aiosqlite.connect(
                str(db_path),
                timeout=30.0,
                isolation_level=None
            )
            self._pool.row_factory = aiosqlite.Row
            await self._create_tables()
            logger.info(f"✅ 数据库连接池已初始化: {db_path}")
        except Exception as e:
            logger.error(f"❌ 数据库初始化失败: {e}")
            self._pool = None
            raise DatabaseError(f"数据库初始化失败: {e}")
    
    async def _create_tables(self) -> None:
        """创建所有表"""
        if self._pool is None:
            return
        
        tables = [
            """
            CREATE TABLE IF NOT EXISTS channel_cache (
                channel_key TEXT PRIMARY KEY,
                name TEXT,
                url TEXT,
                latency INTEGER,
                video_codec TEXT,
                updated_at TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS raw_cache (
                url TEXT PRIMARY KEY,
                content TEXT,
                updated_at TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS blacklist (
                url TEXT PRIMARY KEY,
                reason TEXT,
                added_at TIMESTAMP,
                fail_count INTEGER DEFAULT 1
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS speed_history (
                channel_key TEXT,
                url TEXT,
                timestamp TIMESTAMP,
                latency INTEGER,
                success INTEGER,
                PRIMARY KEY (channel_key, timestamp)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS candidate_pool (
                channel_key TEXT PRIMARY KEY,
                name TEXT,
                url TEXT,
                discovered_at TIMESTAMP,
                last_check TIMESTAMP,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                avg_latency INTEGER DEFAULT 0,
                status TEXT DEFAULT 'observing'
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS ffprobe_cache (
                url TEXT PRIMARY KEY,
                valid INTEGER,
                video_codec TEXT,
                has_video INTEGER,
                updated_at TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS stable_sources (
                channel_name TEXT PRIMARY KEY,
                url TEXT,
                latency INTEGER,
                video_codec TEXT,
                is_fixed INTEGER DEFAULT 0,
                auto_optimize INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                promoted_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        ]
        
        for sql in tables:
            await self._pool.execute(sql)
        
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_channel_cache_updated ON channel_cache(updated_at)",
            "CREATE INDEX IF NOT EXISTS idx_speed_history_key_time ON speed_history(channel_key, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_candidate_status ON candidate_pool(status)",
            "CREATE INDEX IF NOT EXISTS idx_candidate_lastcheck ON candidate_pool(last_check)",
            "CREATE INDEX IF NOT EXISTS idx_stable_channel ON stable_sources(channel_name)",
        ]
        for sql in indexes:
            await self._pool.execute(sql)
        
        await self._pool.commit()
    
    @asynccontextmanager
    async def transaction(self):
        """事务上下文管理器"""
        if self._pool is None:
            raise DatabaseError("数据库未初始化")
        
        try:
            await self._pool.execute("BEGIN")
            yield self._pool
            await self._pool.commit()
        except Exception as e:
            await self._pool.rollback()
            raise DatabaseError(f"事务失败: {e}")
    
    async def execute(self, sql: str, params: tuple = ()) -> Any:
        """执行 SQL"""
        if self._pool is None:
            raise DatabaseError("数据库未初始化")
        cursor = await self._pool.execute(sql, params)
        return cursor
    
    async def execute_many(self, sql: str, params_list: List[tuple]) -> None:
        """批量执行"""
        if self._pool is None:
            raise DatabaseError("数据库未初始化")
        await self._pool.executemany(sql, params_list)
    
    async def fetch_one(self, sql: str, params: tuple = ()) -> Optional[Dict]:
        """查询单条"""
        if self._pool is None:
            raise DatabaseError("数据库未初始化")
        cursor = await self._pool.execute(sql, params)
        row = await cursor.fetchone()
        await cursor.close()
        return dict(row) if row else None
    
    async def fetch_all(self, sql: str, params: tuple = ()) -> List[Dict]:
        """查询多条"""
        if self._pool is None:
            raise DatabaseError("数据库未初始化")
        cursor = await self._pool.execute(sql, params)
        rows = await cursor.fetchall()
        await cursor.close()
        return [dict(row) for row in rows]
    
    async def close(self) -> None:
        """关闭数据库连接"""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("📦 数据库连接已关闭")
    
    def is_available(self) -> bool:
        """检查数据库是否可用"""
        return self._pool is not None


# 全局数据库实例
_db_pool: Optional[DatabasePool] = None


async def get_db() -> DatabasePool:
    """获取数据库连接池实例"""
    global _db_pool
    if _db_pool is None:
        _db_pool = DatabasePool()
        await _db_pool.initialize()
    return _db_pool


def channel_key(name: str, url: str) -> str:
    """生成频道唯一键"""
    return hashlib.md5(f"{name}|{url}".encode()).hexdigest()
