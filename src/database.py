# src/database.py
import json
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from pathlib import Path
import hashlib

from src.config import DATABASE_ENABLE, DATABASE_PATH, CACHE_HOURS, SLOW_SPEED_THRESHOLD, MAX_RETRY_BEFORE_BLACKLIST, AUTO_PROMOTE_THRESHOLD
from src.logger import logger

class DatabaseCache:
    _instance = None
    _conn = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def init(self):
        if not DATABASE_ENABLE:
            return
        try:
            DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
            self._conn = await aiosqlite.connect(str(DATABASE_PATH))
            await self._create_tables()
            logger.info(f"✅ 数据库缓存已启用: {DATABASE_PATH}")
        except Exception as e:
            logger.warning(f"⚠️ 数据库初始化失败: {e}")
            self._conn = None
    
    async def _create_tables(self):
        # 原有表
        await self._conn.execute('''
            CREATE TABLE IF NOT EXISTS channel_cache (
                channel_key TEXT PRIMARY KEY,
                name TEXT,
                url TEXT,
                latency INTEGER,
                video_codec TEXT,
                updated_at TIMESTAMP
            )
        ''')
        await self._conn.execute('''
            CREATE TABLE IF NOT EXISTS raw_cache (
                url TEXT PRIMARY KEY,
                content TEXT,
                updated_at TIMESTAMP
            )
        ''')
        await self._conn.execute('''
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        # 黑名单
        await self._conn.execute('''
            CREATE TABLE IF NOT EXISTS blacklist (
                url TEXT PRIMARY KEY,
                reason TEXT,
                added_at TIMESTAMP,
                fail_count INTEGER DEFAULT 1
            )
        ''')
        # 速度历史（健康度预测）
        await self._conn.execute('''
            CREATE TABLE IF NOT EXISTS speed_history (
                channel_key TEXT,
                url TEXT,
                timestamp TIMESTAMP,
                latency INTEGER,
                success INTEGER,
                PRIMARY KEY (channel_key, timestamp)
            )
        ''')
        # 候选池（扩展）
        await self._conn.execute('''
            CREATE TABLE IF NOT EXISTS candidate_pool (
                channel_key TEXT PRIMARY KEY,
                name TEXT,
                url TEXT,
                discovered_at TIMESTAMP,
                last_check TIMESTAMP,
                fail_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                avg_latency INTEGER DEFAULT 0,
                status TEXT DEFAULT 'observing'  -- observing, stable, promoted, blacklisted
            )
        ''')
        await self._conn.commit()
    
    # ----- 黑名单操作 -----
    async def add_to_blacklist(self, url: str, reason: str = "多次失败"):
        if not self._conn:
            return
        try:
            await self._conn.execute(
                'INSERT OR REPLACE INTO blacklist (url, reason, added_at, fail_count) VALUES (?, ?, ?, ?)',
                (url, reason, datetime.now().isoformat(), 1)
            )
            await self._conn.commit()
        except Exception:
            pass
    
    async def is_blacklisted(self, url: str) -> bool:
        if not self._conn:
            return False
        cursor = await self._conn.execute('SELECT url FROM blacklist WHERE url = ?', (url,))
        row = await cursor.fetchone()
        await cursor.close()
        return row is not None
    
    async def increment_fail_count(self, url: str) -> int:
        if not self._conn:
            return 0
        cursor = await self._conn.execute(
            'SELECT fail_count FROM blacklist WHERE url = ?', (url,)
        )
        row = await cursor.fetchone()
        if row:
            new_count = row[0] + 1
            await self._conn.execute(
                'UPDATE blacklist SET fail_count = ?, added_at = ? WHERE url = ?',
                (new_count, datetime.now().isoformat(), url)
            )
            await self._conn.commit()
            return new_count
        else:
            await self.add_to_blacklist(url, "首次失败")
            return 1
    
    # ----- 候选池操作 -----
    async def add_to_candidate(self, channel_key: str, name: str, url: str, latency: int = 0):
        if not self._conn:
            return
        await self._conn.execute(
            '''INSERT OR REPLACE INTO candidate_pool 
               (channel_key, name, url, discovered_at, last_check, avg_latency, status)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (channel_key, name, url, datetime.now().isoformat(), datetime.now().isoformat(), latency, 'observing')
        )
        await self._conn.commit()
    
    async def update_candidate_latency(self, channel_key: str, latency: int, success: bool):
        if not self._conn:
            return
        cursor = await self._conn.execute(
            'SELECT success_count, fail_count, avg_latency FROM candidate_pool WHERE channel_key = ?',
            (channel_key,)
        )
        row = await cursor.fetchone()
        if row:
            sc, fc, avg = row
            if success:
                sc += 1
                avg = (avg * (sc - 1) + latency) // sc if sc > 0 else latency
            else:
                fc += 1
            status = 'stable' if sc >= AUTO_PROMOTE_THRESHOLD and avg < SLOW_SPEED_THRESHOLD else 'observing'
            await self._conn.execute(
                '''UPDATE candidate_pool SET success_count=?, fail_count=?, avg_latency=?, last_check=?, status=?
                   WHERE channel_key=?''',
                (sc, fc, avg, datetime.now().isoformat(), status, channel_key)
            )
        else:
            # 如果不存在，则添加
            await self.add_to_candidate(channel_key, '', '', latency)
        await self._conn.commit()
    
    async def get_candidates_for_promotion(self) -> List[Dict]:
        if not self._conn:
            return []
        cursor = await self._conn.execute(
            '''SELECT channel_key, name, url, avg_latency, success_count, fail_count
               FROM candidate_pool WHERE status = 'stable' AND fail_count < 3'''
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [{'key': r[0], 'name': r[1], 'url': r[2], 'latency': r[3], 'success': r[4], 'fail': r[5]} for r in rows]
    
    # ----- 速度历史（健康度预测）-----
    async def save_speed_history(self, channel_key: str, url: str, latency: int, success: bool):
        if not self._conn:
            return
        await self._conn.execute(
            'INSERT OR REPLACE INTO speed_history (channel_key, url, timestamp, latency, success) VALUES (?, ?, ?, ?, ?)',
            (channel_key, url, datetime.now().isoformat(), latency, 1 if success else 0)
        )
        await self._conn.commit()
    
    async def get_speed_history(self, channel_key: str, days: int = 30) -> List[Dict]:
        if not self._conn:
            return []
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cursor = await self._conn.execute(
            'SELECT timestamp, latency, success FROM speed_history WHERE channel_key = ? AND timestamp > ? ORDER BY timestamp ASC',
            (channel_key, cutoff)
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [{'timestamp': r[0], 'latency': r[1], 'success': r[2]} for r in rows]

# 全局单例
_db_cache = None

async def get_db_cache() -> DatabaseCache:
    global _db_cache
    if _db_cache is None:
        _db_cache = DatabaseCache()
        await _db_cache.init()
    return _db_cache

def channel_key(name: str, url: str) -> str:
    return hashlib.md5(f"{name}|{url}".encode()).hexdigest()
