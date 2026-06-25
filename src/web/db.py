# src/web/db.py
"""质量趋势数据存储"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict
from src.config import ROOT_DIR

DB_PATH = ROOT_DIR / "data" / "trend.db"

def get_db():
    """获取数据库连接，自动创建表"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS quality_trend (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_name TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            latency INTEGER,
            success INTEGER,
            UNIQUE(channel_name, timestamp)
        )
    ''')
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_channel_time 
        ON quality_trend(channel_name, timestamp)
    ''')
    conn.commit()
    conn.close()

def record_quality(channel_name: str, latency: int, success: bool):
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute(
        'INSERT OR REPLACE INTO quality_trend (channel_name, timestamp, latency, success) VALUES (?, ?, ?, ?)',
        (channel_name, now, latency, 1 if success else 0)
    )
    conn.commit()
    conn.close()

def get_quality_history(channel_name: str, days: int = 7) -> List[Dict]:
    conn = get_db()
    cursor = conn.execute(
        '''
        SELECT timestamp, latency, success 
        FROM quality_trend 
        WHERE channel_name = ? 
          AND timestamp > datetime('now', '-' || ? || ' days')
        ORDER BY timestamp ASC
        ''',
        (channel_name, days)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_all_channels_with_history(days: int = 7) -> Dict[str, List[Dict]]:
    conn = get_db()
    cursor = conn.execute(
        '''
        SELECT channel_name, timestamp, latency, success 
        FROM quality_trend 
        WHERE timestamp > datetime('now', '-' || ? || ' days')
        ORDER BY channel_name, timestamp ASC
        ''',
        (days,)
    )
    rows = cursor.fetchall()
    conn.close()
    result = {}
    for row in rows:
        name = row['channel_name']
        if name not in result:
            result[name] = []
        result[name].append({'timestamp': row['timestamp'], 'latency': row['latency'], 'success': row['success']})
    return result

init_db()
