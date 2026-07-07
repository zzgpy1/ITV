# src/database.py
import json
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pathlib import Path
import hashlib

from src.config_loader import config
from src.logger import logger


class DatabaseCache:
    _instance = None
    _conn = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def init(self):
        if not config.database_enable:
            return
        try:
            db_path = Path(config.data_dir) / "iptv_cache.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = await aiosqlite.connect(str(db_path))
            await self._create_tables()
            logger.info(f"✅ 数据库缓存已启用: {db_path}")
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
        await self._conn.execute('''
            CREATE TABLE IF NOT EXISTS blacklist (
                url TEXT PRIMARY KEY,
                reason TEXT,
                added_at TIMESTAMP,
                fail_count INTEGER DEFAULT 1
            )
        ''')
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
        # 候选池表（新增）
        await self._conn.execute('''
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
        ''')
        # 稳定源表（新增）
        await self._conn.execute('''
            CREATE TABLE IF NOT EXISTS stable_sources (
                channel_name TEXT PRIMARY KEY,
                url TEXT,
                latency INTEGER,
                video_codec TEXT,
                is_fixed INTEGER DEFAULT 0,
                updated_at TIMESTAMP
            )
        ''')
        await self._conn.execute('''
            CREATE TABLE IF NOT EXISTS ffprobe_cache (
                url TEXT PRIMARY KEY,
                valid INTEGER,
                video_codec TEXT,
                has_video INTEGER,
                updated_at TIMESTAMP
            )
        ''')
        # 索引
        await self._conn.execute('CREATE INDEX IF NOT EXISTS idx_channel_cache_updated ON channel_cache(updated_at)')
        await self._conn.execute('CREATE INDEX IF NOT EXISTS idx_speed_history_key_time ON speed_history(channel_key, timestamp)')
        await self._conn.execute('CREATE INDEX IF NOT EXISTS idx_candidate_status ON candidate_pool(status)')
        await self._conn.execute('CREATE INDEX IF NOT EXISTS idx_candidate_lastcheck ON candidate_pool(last_check)')
        await self._conn.execute('CREATE INDEX IF NOT EXISTS idx_stable_channel ON stable_sources(channel_name)')
        await self._conn.commit()

    # ---------- 原有方法 ----------
    async def get_raw_source(self, url: str) -> Optional[str]:
        if not self._conn:
            return None
        try:
            cursor = await self._conn.execute(
                'SELECT content, updated_at FROM raw_cache WHERE url = ?', (url,)
            )
            row = await cursor.fetchone()
            await cursor.close()
            if row:
                content, updated_at = row
                if datetime.now() - datetime.fromisoformat(updated_at) < timedelta(hours=config.cache_raw_hours):
                    return content
        except Exception:
            pass
        return None

    async def set_raw_source(self, url: str, content: str):
        if not self._conn:
            return
        try:
            await self._conn.execute(
                'INSERT OR REPLACE INTO raw_cache (url, content, updated_at) VALUES (?, ?, ?)',
                (url, content, datetime.now().isoformat())
            )
            await self._conn.commit()
        except Exception:
            pass

    async def get_speed_result(self, channel_key: str, max_age_hours: int = None) -> Optional[Dict]:
        if not self._conn:
            return None
        try:
            cursor = await self._conn.execute(
                'SELECT name, url, latency, video_codec, updated_at FROM channel_cache WHERE channel_key = ?',
                (channel_key,)
            )
            row = await cursor.fetchone()
            await cursor.close()
            if row:
                name, url, latency, video_codec, updated_at = row
                age_limit = max_age_hours if max_age_hours is not None else config.cache_speed_hours
                if datetime.now() - datetime.fromisoformat(updated_at) < timedelta(hours=age_limit):
                    return {
                        "name": name,
                        "url": url,
                        "latency": latency,
                        "video_codec": video_codec
                    }
        except Exception:
            pass
        return None

    async def set_speed_result(self, channel_key: str, channel_data: Dict):
        if not self._conn:
            return
        try:
            await self._conn.execute(
                '''INSERT OR REPLACE INTO channel_cache 
                   (channel_key, name, url, latency, video_codec, updated_at) 
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (
                    channel_key,
                    channel_data.get("name", ""),
                    channel_data.get("url", ""),
                    channel_data.get("latency", 9999),
                    channel_data.get("video_codec", ""),
                    datetime.now().isoformat()
                )
            )
            await self._conn.commit()
        except Exception:
            pass

    async def save_speed_results(self, channels: List[Dict]):
        if not self._conn or not channels:
            return
        try:
            data = []
            now = datetime.now().isoformat()
            for ch in channels:
                key = f"{ch['name']}|{ch['url']}"
                data.append((
                    key,
                    ch.get("name", ""),
                    ch.get("url", ""),
                    ch.get("latency", 9999),
                    ch.get("video_codec", ""),
                    now
                ))
            await self._conn.executemany(
                '''INSERT OR REPLACE INTO channel_cache 
                   (channel_key, name, url, latency, video_codec, updated_at) 
                   VALUES (?, ?, ?, ?, ?, ?)''',
                data
            )
            await self._conn.commit()
        except Exception as e:
            logger.warning(f"批量插入失败: {e}")

    async def get_last_update_time(self) -> Optional[int]:
        if not self._conn:
            return None
        cursor = await self._conn.execute("SELECT value FROM metadata WHERE key = 'last_update'")
        row = await cursor.fetchone()
        await cursor.close()
        if row:
            return int(row[0])
        return None

    async def set_last_update_time(self, timestamp: int = None):
        if timestamp is None:
            timestamp = int(datetime.now().timestamp())
        if not self._conn:
            return
        await self._conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            ("last_update", str(timestamp))
        )
        await self._conn.commit()

    # ---------- 黑名单 ----------
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

    # ---------- 候选池 ----------
    async def update_candidate_latency(self, channel_key: str, latency: int, success: bool):
        if not self._conn:
            return
        try:
            cursor = await self._conn.execute(
                'SELECT success_count, fail_count, avg_latency FROM candidate_pool WHERE channel_key = ?',
                (channel_key,)
            )
            row = await cursor.fetchone()
            await cursor.close()

            if row:
                sc, fc, avg = row
                if success:
                    sc += 1
                    if sc == 1:
                        avg = latency
                    else:
                        avg = (avg * (sc - 1) + latency) // sc
                else:
                    fc += 1
                await self._conn.execute(
                    '''UPDATE candidate_pool SET success_count=?, fail_count=?, avg_latency=?, last_check=?
                       WHERE channel_key=?''',
                    (sc, fc, avg, datetime.now().isoformat(), channel_key)
                )
            else:
                if success:
                    await self._conn.execute(
                        '''INSERT INTO candidate_pool 
                           (channel_key, name, url, success_count, fail_count, avg_latency, last_check, status, discovered_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (channel_key, '', '', 1, 0, latency, datetime.now().isoformat(), 'observing', datetime.now().isoformat())
                    )
            await self._conn.commit()
        except Exception as e:
            logger.warning(f"更新候选池统计失败: {e}")

    async def get_candidate_stats_batch(self) -> Dict[str, Dict]:
        if not self._conn:
            return {}
        cursor = await self._conn.execute(
            'SELECT channel_key, success_count, fail_count, avg_latency FROM candidate_pool'
        )
        rows = await cursor.fetchall()
        await cursor.close()
        result = {}
        for row in rows:
            result[row[0]] = {
                'success': row[1],
                'fail': row[2],
                'avg': row[3]
            }
        return result

    async def import_candidate_pool_from_json(self, json_path: Path):
        if not json_path.exists():
            return
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for key, obs in data.items():
                cursor = await self._conn.execute('SELECT 1 FROM candidate_pool WHERE channel_key = ?', (key,))
                exists = await cursor.fetchone()
                await cursor.close()
                if exists:
                    continue
                await self._conn.execute(
                    '''INSERT INTO candidate_pool 
                       (channel_key, name, url, discovered_at, last_check, success_count, fail_count, avg_latency, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        key,
                        obs.get('channel_name', ''),
                        obs.get('url', ''),
                        obs.get('discovered_at', datetime.now().isoformat()),
                        obs.get('last_check', datetime.now().isoformat()),
                        obs.get('success_count', 0),
                        obs.get('fail_count', 0),
                        obs.get('avg_latency', 0),
                        obs.get('status', 'observing')
                    )
                )
            await self._conn.commit()
            logger.info(f"📥 从 JSON 导入候选池 {len(data)} 条记录")
        except Exception as e:
            logger.warning(f"导入候选池 JSON 失败: {e}")

    # ---------- 稳定源 ----------
    async def get_stable_source(self, channel_name: str) -> Optional[Dict]:
        if not self._conn:
            return None
        cursor = await self._conn.execute(
            'SELECT channel_name, url, latency, video_codec, is_fixed, updated_at FROM stable_sources WHERE channel_name = ?',
            (channel_name,)
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row:
            return {
                'channel_name': row[0],
                'url': row[1],
                'latency': row[2],
                'video_codec': row[3],
                'is_fixed': bool(row[4]),
                'updated_at': row[5]
            }
        return None

    async def upsert_stable_source(self, channel_name: str, url: str, latency: int, video_codec: str = '', is_fixed: bool = False):
        if not self._conn:
            return
        await self._conn.execute(
            '''INSERT OR REPLACE INTO stable_sources (channel_name, url, latency, video_codec, is_fixed, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (channel_name, url, latency, video_codec, 1 if is_fixed else 0, datetime.now().isoformat())
        )
        await self._conn.commit()

    async def delete_stable_source(self, channel_name: str):
        if not self._conn:
            return
        await self._conn.execute('DELETE FROM stable_sources WHERE channel_name = ?', (channel_name,))
        await self._conn.commit()

    async def get_all_stable_sources(self) -> Dict[str, Dict]:
        if not self._conn:
            return {}
        cursor = await self._conn.execute(
            'SELECT channel_name, url, latency, video_codec, is_fixed, updated_at FROM stable_sources'
        )
        rows = await cursor.fetchall()
        await cursor.close()
        result = {}
        for row in rows:
            result[row[0]] = {
                'url': row[1],
                'latency': row[2],
                'video_codec': row[3],
                'is_fixed': bool(row[4]),
                'updated_at': row[5]
            }
        return result

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None


_db_cache = None

async def get_db_cache() -> DatabaseCache:
    global _db_cache
    if _db_cache is None:
        _db_cache = DatabaseCache()
        await _db_cache.init()
    elif _db_cache._conn is None:
        await _db_cache.init()
    return _db_cache

def channel_key(name: str, url: str) -> str:
    return hashlib.md5(f"{name}|{url}".encode()).hexdigest()
