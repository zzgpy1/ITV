#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPTV 频道缓存数据库管理器（增量更新版）
- 永不删除数据，只标记失效
- 支持增量更新
- 输出时按时间筛选
"""

import sqlite3
import json
import time
import os
from typing import List, Dict, Optional, Any

DB_PATH = "iptv_cache.db"

# 数据时效配置（秒）
# 验证成功后，在这个时间内都认为有效，无需重新验证
DATA_VALID_SECONDS = 7 * 24 * 3600  # 7天

# 数据过期配置（秒）
# 超过这个时间未验证，视为过期，输出时排除，并触发增量验证
DATA_EXPIRY_SECONDS = 30 * 24 * 3600  # 30天

# 失效标记阈值
FAILURE_THRESHOLD = 3

class IPTVDatabase:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # 主数据表（新增 status 和 last_seen 字段）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    group_title TEXT,
                    tvg_id TEXT,
                    tvg_logo TEXT,
                    latency INTEGER DEFAULT 9999,
                    video_codec TEXT,
                    ip_info TEXT,
                    first_seen INTEGER DEFAULT 0,
                    last_verified INTEGER DEFAULT 0,
                    last_attempt INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active',
                    UNIQUE(name, url)
                )
            ''')
            # 索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON channels(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_last_verified ON channels(last_verified)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_name ON channels(name)')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            conn.commit()
            print("✅ 数据库初始化完成（增量更新模式）")

    def get_last_update_time(self) -> Optional[int]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM metadata WHERE key = 'last_update'")
            row = cursor.fetchone()
            if row:
                return int(row[0])
        return None

    def set_last_update_time(self, timestamp: int = None):
        if timestamp is None:
            timestamp = int(time.time())
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                           ("last_update", str(timestamp)))
            conn.commit()

    def upsert_channel(self, channel: Dict[str, Any], verified: bool = True):
        """
        插入或更新频道（增量更新）
        verified: 本次验证是否成功
        """
        now = int(time.time())
        name = channel.get("name", "")
        url = channel.get("url", "")
        if not url:
            return

        group_title = channel.get("group_title", "")
        tvg_id = channel.get("id", "")
        tvg_logo = channel.get("logo", "")
        latency = channel.get("latency", 9999)
        video_codec = channel.get("video_codec", "")
        ip_info = json.dumps(channel.get("ip_info")) if channel.get("ip_info") else None

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, failure_count, status FROM channels WHERE name = ? AND url = ?", (name, url))
            existing = cursor.fetchone()

            if existing:
                if verified:
                    cursor.execute('''
                        UPDATE channels SET
                            group_title = ?, tvg_id = ?, tvg_logo = ?,
                            latency = ?, video_codec = ?, ip_info = ?,
                            last_verified = ?, last_attempt = ?,
                            failure_count = 0, status = 'active'
                        WHERE name = ? AND url = ?
                    ''', (group_title, tvg_id, tvg_logo, latency, video_codec, ip_info,
                          now, now, name, url))
                else:
                    cursor.execute('''
                        UPDATE channels SET
                            last_attempt = ?,
                            failure_count = failure_count + 1,
                            status = CASE 
                                WHEN failure_count + 1 >= ? THEN 'inactive'
                                ELSE status
                            END
                        WHERE name = ? AND url = ?
                    ''', (now, FAILURE_THRESHOLD, name, url))
            else:
                if verified:
                    cursor.execute('''
                        INSERT INTO channels
                        (name, url, group_title, tvg_id, tvg_logo, latency, video_codec, ip_info,
                         first_seen, last_verified, last_attempt, failure_count, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'active')
                    ''', (name, url, group_title, tvg_id, tvg_logo, latency, video_codec, ip_info,
                          now, now, now))
            conn.commit()

    def batch_upsert(self, channels: List[Dict[str, Any]], verified: bool = True):
        for ch in channels:
            self.upsert_channel(ch, verified)

    def load_active_channels(self, max_age: int = DATA_VALID_SECONDS) -> List[Dict[str, Any]]:
        """加载最近验证成功的活跃频道（max_age 天内验证过的）"""
        now = int(time.time())
        threshold = now - max_age
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM channels
                WHERE status = 'active' AND last_verified >= ?
                ORDER BY name, latency
            ''', (threshold,))
            channels = []
            for row in cursor.fetchall():
                ch = dict(row)
                if ch.get("ip_info"):
                    ch["ip_info"] = json.loads(ch["ip_info"])
                else:
                    ch["ip_info"] = None
                channels.append(ch)
        return channels

    def get_stats(self) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM channels")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM channels WHERE status = 'active'")
            active = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM channels WHERE status = 'inactive'")
            inactive = cursor.fetchone()[0]
            now = int(time.time())
            threshold = now - DATA_VALID_SECONDS
            cursor.execute("SELECT COUNT(*) FROM channels WHERE status = 'active' AND last_verified >= ?", (threshold,))
            recent = cursor.fetchone()[0]
        return {
            "total": total,
            "active": active,
            "inactive": inactive,
            "recent": recent,
            "valid_days": DATA_VALID_SECONDS // 86400,
            "expiry_days": DATA_EXPIRY_SECONDS // 86400
        }

    def is_expired(self) -> bool:
        """检查是否需要全量更新：没有活跃频道或所有活跃频道都已超过 expiry_days 天"""
        threshold = int(time.time()) - DATA_EXPIRY_SECONDS
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM channels WHERE status = 'active' AND last_verified >= ?", (threshold,))
            recent = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM channels WHERE status = 'active'")
            active = cursor.fetchone()[0]
        return active == 0 or recent == 0
