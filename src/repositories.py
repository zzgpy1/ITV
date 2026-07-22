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
        async with db.transaction() as conn:
            await conn.execute(
                """INSERT OR REPLACE INTO source_pool
                   (source_key, channel_name, url, source_url, discovered_at, status, fail_count, success_count, latency, video_codec)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (source.source_key, source.channel_name, source.url,
                 source.source_url, source.discovered_at.isoformat(),
                 source.status, source.fail_count, source.success_count,
                 source.latency, source.video_codec)
            )

    async def get_pending(self, limit: int = 1000) -> List[Source]:
        db = await get_db()
        cursor = await db._conn.execute(
            "SELECT * FROM source_pool WHERE status = 'pending' ORDER BY discovered_at LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        await cursor.close()
        result = []
        for r in rows:
            result.append(Source(
                source_key=r[0],
                channel_name=r[1],
                url=r[2],
                source_url=r[3] if len(r) > 3 else "",
                discovered_at=datetime.fromisoformat(r[4]) if r[4] else datetime.now(),
                last_check=datetime.fromisoformat(r[5]) if r[5] else None,
                status=r[6] if len(r) > 6 else "pending",
                fail_count=r[7] if len(r) > 7 else 0,
                success_count=r[8] if len(r) > 8 else 0,
                latency=r[9] if len(r) > 9 else 0,
                video_codec=r[10] if len(r) > 10 else ""
            ))
        return result

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
        async with db.transaction() as conn:
            await conn.execute(
                """INSERT OR REPLACE INTO candidate_pool
                   (source_key, channel_name, url, status, discovered_at, last_check)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (candidate.source_key, candidate.channel_name, candidate.url,
                 candidate.status, candidate.discovered_at.isoformat(),
                 datetime.now().isoformat())
            )

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

    async def update_latency(self, key: str, latency: int, success: bool):
        db = await get_db()
        async with db.transaction() as conn:
            await conn.execute(
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
            source_key=row[0],
            channel_name=row[1],
            url=row[2],
            status=row[3] if len(row) > 3 else "observing",
            check_count=row[4] if len(row) > 4 else 0,
            success_count=row[5] if len(row) > 5 else 0,
            fail_count=row[6] if len(row) > 6 else 0,
            total_latency=row[7] if len(row) > 7 else 0,
            avg_latency=row[8] if len(row) > 8 else 0,
            last_check=datetime.fromisoformat(row[9]) if row[9] else None,
            discovered_at=datetime.fromisoformat(row[10]) if row[10] else datetime.now(),
            promoted_at=datetime.fromisoformat(row[11]) if len(row) > 11 and row[11] else None
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
            channel_name=row[0],
            url=row[1],
            latency=row[2],
            video_codec=row[3],
            is_fixed=bool(row[4]) if len(row) > 4 else False,
            auto_optimize=bool(row[5]) if len(row) > 5 else False,
            promoted_at=datetime.fromisoformat(row[6]) if row[6] else datetime.now(),
            last_verified=datetime.fromisoformat(row[7]) if row[7] else None,
            fail_count=row[8] if len(row) > 8 else 0,
            status=row[9] if len(row) > 9 else "active"
        )

    async def upsert(self, stable: Stable):
        db = await get_db()
        async with db.transaction() as conn:
            await conn.execute(
                """INSERT OR REPLACE INTO stable_sources
                   (channel_name, url, latency, video_codec, is_fixed, auto_optimize,
                    promoted_at, last_verified, fail_count, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (stable.channel_name, stable.url, stable.latency, stable.video_codec,
                 1 if stable.is_fixed else 0,
                 1 if stable.auto_optimize else 0,
                 stable.promoted_at.isoformat(),
                 stable.last_verified.isoformat() if stable.last_verified else None,
                 stable.fail_count,
                 stable.status)
            )

    async def get_all(self) -> Dict[str, Stable]:
        db = await get_db()
        cursor = await db._conn.execute("SELECT * FROM stable_sources")
        rows = await cursor.fetchall()
        await cursor.close()
        result = {}
        for r in rows:
            stable = Stable(
                channel_name=r[0],
                url=r[1],
                latency=r[2],
                video_codec=r[3],
                is_fixed=bool(r[4]) if len(r) > 4 else False,
                auto_optimize=bool(r[5]) if len(r) > 5 else False,
                promoted_at=datetime.fromisoformat(r[6]) if r[6] else datetime.now(),
                last_verified=datetime.fromisoformat(r[7]) if r[7] else None,
                fail_count=r[8] if len(r) > 8 else 0,
                status=r[9] if len(r) > 9 else "active"
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
