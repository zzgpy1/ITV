import hashlib
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from src.database import get_db
from src.models import Source, Candidate, Stable


def make_key(name: str, url: str) -> str:
    return hashlib.md5(f"{name}|{url}".encode()).hexdigest()


class SourceRepository:
    async def add(self, source: Source) -> None:
        db = await get_db()
        await db._conn.execute(
            """INSERT OR REPLACE INTO source_pool
               (source_key, channel_name, url, source_url, discovered_at, status, fail_count, success_count, latency)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (source.source_key, source.channel_name, source.url,
             source.source_url, source.discovered_at.isoformat(),
             source.status, source.fail_count, source.success_count, source.latency)
        )
        await db._conn.commit()

    async def get_pending(self, limit: int = 1000) -> List[Source]:
        db = await get_db()
        cursor = await db._conn.execute(
            "SELECT * FROM source_pool WHERE status = 'pending' ORDER BY discovered_at LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [Source(
            source_key=r[0], channel_name=r[1], url=r[2],
            source_url=r[3], discovered_at=datetime.fromisoformat(r[4]),
            last_check=datetime.fromisoformat(r[5]) if r[5] else None,
            status=r[6], fail_count=r[7], success_count=r[8], latency=r[9],
            video_codec=r[10] if len(r) > 10 else ""
        ) for r in rows]

    async def update_status(self, key: str, status: str):
        db = await get_db()
        await db._conn.execute(
            "UPDATE source_pool SET status = ?, last_check = ? WHERE source_key = ?",
            (status, datetime.now().isoformat(), key)
        )
        await db._conn.commit()


class CandidateRepository:
    async def add(self, candidate: Candidate) -> None:
        db = await get_db()
        await db._conn.execute(
            """INSERT OR REPLACE INTO candidate_pool
               (source_key, channel_name, url, status, discovered_at, last_check)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (candidate.source_key, candidate.channel_name, candidate.url,
             candidate.status, candidate.discovered_at.isoformat(),
             datetime.now().isoformat())
        )
        await db._conn.commit()

    async def update_latency(self, key: str, latency: int, success: bool):
        db = await get_db()
        # 先检查是否存在记录，若不存在则插入占位记录（仅当更新时发现影响0行时插入）
        # 使用 UPSERT 语法（SQLite 3.24+）
        await db._conn.execute(
            """INSERT INTO candidate_pool (source_key, channel_name, url, status, discovered_at, check_count, success_count, fail_count, total_latency, avg_latency, last_check)
               VALUES (?, '', '', 'observing', ?, 0, 0, 0, 0, 0, ?)
               ON CONFLICT(source_key) DO NOTHING""",
            (key, datetime.now().isoformat(), datetime.now().isoformat())
        )
        # 然后更新
        await db._conn.execute(
            """UPDATE candidate_pool
               SET check_count = check_count + 1,
                   success_count = success_count + ?,
                   fail_count = fail_count + ?,
                   total_latency = total_latency + ?,
                   avg_latency = (total_latency + ?) / (success_count + ?),
                   last_check = ?
               WHERE source_key = ?""",
            (1 if success else 0, 0 if success else 1,
             latency if success else 0,
             latency if success else 0,
             1 if success else 0,
             datetime.now().isoformat(), key)
        )
        await db._conn.commit()

    async def get_observing(self, limit: int = 1000) -> List[Candidate]:
        db = await get_db()
        cursor = await db._conn.execute(
            "SELECT * FROM candidate_pool WHERE status = 'observing' ORDER BY discovered_at LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [self._row_to_candidate(r) for r in rows]

    async def get_stable_candidates(self) -> List[Candidate]:
        db = await get_db()
        cursor = await db._conn.execute(
            "SELECT * FROM candidate_pool WHERE status = 'stable'"
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [self._row_to_candidate(r) for r in rows]

    async def get_by_key(self, key: str) -> Optional[Candidate]:
        db = await get_db()
        cursor = await db._conn.execute(
            "SELECT * FROM candidate_pool WHERE source_key = ?", (key,)
        )
        row = await cursor.fetchone()
        await cursor.close()
        if not row:
            return None
        return self._row_to_candidate(row)

    async def mark_promoted(self, key: str):
        db = await get_db()
        await db._conn.execute(
            "UPDATE candidate_pool SET status = 'promoted', promoted_at = ? WHERE source_key = ?",
            (datetime.now().isoformat(), key)
        )
        await db._conn.commit()

    async def mark_stable(self, key: str):
        db = await get_db()
        await db._conn.execute(
            "UPDATE candidate_pool SET status = 'stable' WHERE source_key = ?",
            (key,)
        )
        await db._conn.commit()

    def _row_to_candidate(self, row) -> Candidate:
        return Candidate(
            source_key=row[0], channel_name=row[1], url=row[2],
            status=row[3], check_count=row[4], success_count=row[5],
            fail_count=row[6], total_latency=row[7], avg_latency=row[8],
            last_check=datetime.fromisoformat(row[9]) if row[9] else None,
            discovered_at=datetime.fromisoformat(row[10]),
            promoted_at=datetime.fromisoformat(row[11]) if row[11] else None
        )


class StableRepository:
    async def get(self, channel_name: str) -> Optional[Stable]:
        db = await get_db()
        cursor = await db._conn.execute(
            "SELECT * FROM stable_sources WHERE channel_name = ?",
            (channel_name,)
        )
        row = await cursor.fetchone()
        await cursor.close()
        if not row:
            return None
        return Stable(
            channel_name=row[0], url=row[1], latency=row[2], video_codec=row[3],
            is_fixed=bool(row[4]), auto_optimize=bool(row[5]),
            promoted_at=datetime.fromisoformat(row[6]),
            last_verified=datetime.fromisoformat(row[7]) if row[7] else None,
            fail_count=row[8], status=row[9]
        )

    async def upsert(self, stable: Stable):
        db = await get_db()
        await db._conn.execute(
            """INSERT OR REPLACE INTO stable_sources
               (channel_name, url, latency, video_codec, is_fixed, auto_optimize,
                promoted_at, last_verified, fail_count, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (stable.channel_name, stable.url, stable.latency, stable.video_codec,
             1 if stable.is_fixed else 0, 1 if stable.auto_optimize else 0,
             stable.promoted_at.isoformat(),
             stable.last_verified.isoformat() if stable.last_verified else None,
             stable.fail_count, stable.status)
        )
        await db._conn.commit()

    async def get_all(self) -> Dict[str, Stable]:
        db = await get_db()
        cursor = await db._conn.execute("SELECT * FROM stable_sources")
        rows = await cursor.fetchall()
        await cursor.close()
        result = {}
        for r in rows:
            stable = Stable(
                channel_name=r[0], url=r[1], latency=r[2], video_codec=r[3],
                is_fixed=bool(r[4]), auto_optimize=bool(r[5]),
                promoted_at=datetime.fromisoformat(r[6]),
                last_verified=datetime.fromisoformat(r[7]) if r[7] else None,
                fail_count=r[8], status=r[9]
            )
            result[stable.channel_name] = stable
        return result

    async def delete(self, channel_name: str):
        db = await get_db()
        await db._conn.execute(
            "DELETE FROM stable_sources WHERE channel_name = ?",
            (channel_name,)
        )
        await db._conn.commit()

    async def record_failure(self, channel_name: str):
        db = await get_db()
        await db._conn.execute(
            "UPDATE stable_sources SET fail_count = fail_count + 1, last_verified = ? WHERE channel_name = ?",
            (datetime.now().isoformat(), channel_name)
        )
        await db._conn.commit()

    async def record_success(self, channel_name: str):
        db = await get_db()
        await db._conn.execute(
            "UPDATE stable_sources SET fail_count = 0, last_verified = ? WHERE channel_name = ?",
            (datetime.now().isoformat(), channel_name)
        )
        await db._conn.commit()


class BlacklistRepository:
    async def add(self, url: str, reason: str = "manual"):
        db = await get_db()
        await db._conn.execute(
            "INSERT OR REPLACE INTO blacklist (url, reason, added_at) VALUES (?, ?, ?)",
            (url, reason, datetime.now().isoformat())
        )
        await db._conn.commit()

    async def is_blacklisted(self, url: str) -> bool:
        db = await get_db()
        cursor = await db._conn.execute("SELECT 1 FROM blacklist WHERE url = ?", (url,))
        row = await cursor.fetchone()
        await cursor.close()
        return row is not None


class CacheRepository:
    async def get(self, key: str, cache_type: str, max_age_hours: int) -> Optional[str]:
        db = await get_db()
        cursor = await db._conn.execute(
            "SELECT data, updated_at FROM cache WHERE cache_key = ? AND cache_type = ?",
            (key, cache_type)
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row:
            updated = datetime.fromisoformat(row[1])
            if datetime.now() - updated < timedelta(hours=max_age_hours):
                return row[0]
        return None

    async def set(self, key: str, data: str, cache_type: str, ttl_hours: int):
        db = await get_db()
        await db._conn.execute(
            "INSERT OR REPLACE INTO cache (cache_key, data, cache_type, updated_at, ttl_hours) VALUES (?, ?, ?, ?, ?)",
            (key, data, cache_type, datetime.now().isoformat(), ttl_hours)
        )
        await db._conn.commit()
