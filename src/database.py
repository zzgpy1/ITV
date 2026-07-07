# src/database.py
import json
import hashlib
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pathlib import Path

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
        # 频道缓存表
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
        # 原始内容缓存
        await self._conn.execute('''
            CREATE TABLE IF NOT EXISTS raw_cache (
                url TEXT PRIMARY KEY,
                content TEXT,
                updated_at TIMESTAMP
            )
        ''')
        # 元数据
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
        # 速度历史
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
        # 候选池（核心）
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
                status TEXT DEFAULT 'observing'
            )
        ''')
        # ffprobe 缓存
        await self._conn.execute('''
            CREATE TABLE IF NOT EXISTS ffprobe_cache (
                url TEXT PRIMARY KEY,
                valid INTEGER,
                video_codec TEXT,
                has_video INTEGER,
                updated_at TIMESTAMP
            )
        ''')
        # 稳定源表
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
        # 索引
        await self._conn.execute('CREATE INDEX IF NOT EXISTS idx_channel_cache_updated ON channel_cache(updated_at)')
        await self._conn.execute('CREATE INDEX IF NOT EXISTS idx_speed_history_key_time ON speed_history(channel_key, timestamp)')
        await self._conn.execute('CREATE INDEX IF NOT EXISTS idx_candidate_status ON candidate_pool(status)')
        await self._conn.execute('CREATE INDEX IF NOT EXISTS idx_candidate_lastcheck ON candidate_pool(last_check)')
        await self._conn.execute('CREATE INDEX IF NOT EXISTS idx_stable_channel ON stable_sources(channel_name)')
        await self._conn.commit()

    # ---------- 原始缓存 ----------
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

    # ---------- 速度结果缓存 ----------
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

    # ---------- 元数据 ----------
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

    # ---------- 候选池 (核心) ----------
    async def add_to_candidate(self, channel_key: str, name: str, url: str, latency: int = 0):
        """将新源加入候选池（如果不存在）"""
        if not self._conn:
            return
        try:
            # 检查是否已存在
            cursor = await self._conn.execute(
                'SELECT channel_key FROM candidate_pool WHERE channel_key = ?', (channel_key,)
            )
            exists = await cursor.fetchone()
            await cursor.close()
            if exists:
                return
            await self._conn.execute(
                '''INSERT INTO candidate_pool 
                   (channel_key, name, url, discovered_at, last_check, avg_latency, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (channel_key, name, url, datetime.now().isoformat(), datetime.now().isoformat(), latency, 'observing')
            )
            await self._conn.commit()
        except Exception as e:
            logger.warning(f"添加候选源失败: {e}")

    async def update_candidate_latency(self, channel_key: str, latency: int, success: bool):
        """更新候选池统计，若不存在则创建（仅当成功时创建）"""
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
                        avg = (avg * (sc - 1) + latency) // sc  # 整数平均
                else:
                    fc += 1
                await self._conn.execute(
                    '''UPDATE candidate_pool SET success_count=?, fail_count=?, avg_latency=?, last_check=?
                       WHERE channel_key=?''',
                    (sc, fc, avg, datetime.now().isoformat(), channel_key)
                )
            else:
                # 首次记录，仅当成功时才插入（失败时无数据可记录）
                if success:
                    await self._conn.execute(
                        '''INSERT INTO candidate_pool 
                           (channel_key, success_count, fail_count, avg_latency, last_check, status)
                           VALUES (?, ?, ?, ?, ?, ?)''',
                        (channel_key, 1, 0, latency, datetime.now().isoformat(), 'observing')
                    )
                # 如果第一次就是失败，暂时不创建记录（后续成功时会创建）
            await self._conn.commit()
        except Exception as e:
            logger.warning(f"更新候选池统计失败: {e}")

    async def get_candidates_for_promotion(self, limit: int = 500) -> List[Dict]:
        """获取已达到稳定标准但未晋升的候选源"""
        if not self._conn:
            return []
        try:
            cursor = await self._conn.execute(
                '''SELECT channel_key, name, url, avg_latency, success_count, fail_count
                   FROM candidate_pool 
                   WHERE status = 'stable' AND fail_count < 3
                   ORDER BY last_check ASC LIMIT ?''',
                (limit,)
            )
            rows = await cursor.fetchall()
            await cursor.close()
            return [{'key': r[0], 'name': r[1], 'url': r[2], 'latency': r[3], 'success': r[4], 'fail': r[5]} for r in rows]
        except Exception as e:
            logger.warning(f"获取待晋升候选源失败: {e}")
            return []

    async def mark_candidate_promoted(self, channel_key: str):
        """标记候选源已晋升为稳定源"""
        if not self._conn:
            return
        try:
            await self._conn.execute(
                "UPDATE candidate_pool SET status = 'promoted' WHERE channel_key = ?",
                (channel_key,)
            )
            await self._conn.commit()
        except Exception as e:
            logger.warning(f"标记晋升失败: {e}")

    async def get_candidate_stats_batch(self) -> Dict[str, Dict]:
        """批量获取所有候选池统计（用于观察阶段）"""
        if not self._conn:
            return {}
        try:
            cursor = await self._conn.execute(
                "SELECT channel_key, success_count, fail_count, avg_latency FROM candidate_pool"
            )
            rows = await cursor.fetchall()
            await cursor.close()
            stats = {}
            for row in rows:
                key, sc, fc, avg = row
                stats[key] = {"success": sc, "fail": fc, "avg": avg}
            return stats
        except Exception as e:
            logger.warning(f"批量获取候选统计失败: {e}")
            return {}

    # ---------- 速度历史 ----------
    async def save_speed_history(self, channel_key: str, url: str, latency: int, success: bool):
        if not self._conn:
            return
        try:
            await self._conn.execute(
                'INSERT OR REPLACE INTO speed_history (channel_key, url, timestamp, latency, success) VALUES (?, ?, ?, ?, ?)',
                (channel_key, url, datetime.now().isoformat(), latency, 1 if success else 0)
            )
            await self._conn.commit()
        except Exception:
            pass

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

    # ---------- ffprobe 缓存 ----------
    async def get_cached_probe_result(self, url: str) -> Optional[Dict]:
        if not self._conn:
            return None
        try:
            cursor = await self._conn.execute(
                'SELECT valid, video_codec, has_video, updated_at FROM ffprobe_cache WHERE url = ?',
                (url,)
            )
            row = await cursor.fetchone()
            await cursor.close()
            if row:
                valid, video_codec, has_video, updated_at = row
                if datetime.now() - datetime.fromisoformat(updated_at) < timedelta(hours=config.ffprobe_cache_hours):
                    return {"valid": bool(valid), "video_codec": video_codec, "has_video": bool(has_video)}
        except Exception:
            pass
        return None

    async def save_probe_result(self, url: str, result: Dict):
        if not self._conn:
            return
        try:
            await self._conn.execute(
                'INSERT OR REPLACE INTO ffprobe_cache (url, valid, video_codec, has_video, updated_at) VALUES (?, ?, ?, ?, ?)',
                (url, result.get("valid", False), result.get("video_codec", ""), result.get("has_video", False), datetime.now().isoformat())
            )
            await self._conn.commit()
        except Exception:
            pass

    # ---------- 稳定源 ----------
    async def get_stable_source(self, channel_name: str) -> Optional[Dict]:
        if not self._conn:
            return None
        try:
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
        except Exception:
            pass
        return None

    async def upsert_stable_source(self, channel_name: str, url: str, latency: int, video_codec: str = '', is_fixed: bool = False):
        if not self._conn:
            return
        try:
            await self._conn.execute(
                '''INSERT OR REPLACE INTO stable_sources (channel_name, url, latency, video_codec, is_fixed, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (channel_name, url, latency, video_codec, 1 if is_fixed else 0, datetime.now().isoformat())
            )
            await self._conn.commit()
        except Exception as e:
            logger.warning(f"更新稳定源失败: {e}")

    async def delete_stable_source(self, channel_name: str):
        if not self._conn:
            return
        try:
            await self._conn.execute('DELETE FROM stable_sources WHERE channel_name = ?', (channel_name,))
            await self._conn.commit()
        except Exception as e:
            logger.warning(f"删除稳定源失败: {e}")

    async def get_all_stable_sources(self) -> Dict[str, Dict]:
        if not self._conn:
            return {}
        try:
            cursor = await self._conn.execute('SELECT channel_name, url, latency, video_codec, is_fixed, updated_at FROM stable_sources')
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
        except Exception as e:
            logger.warning(f"获取所有稳定源失败: {e}")
            return {}

    # ---------- 关闭 ----------
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
