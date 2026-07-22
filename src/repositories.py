from src.database import db
from src.models import Source, Candidate, StableSource, ChannelCache
from datetime import datetime
from typing import List, Optional

class SourceRepository:
    async def add(self, source: Source):
        await db.execute(
            """INSERT OR REPLACE INTO source_pool
               (source_key, channel_name, url, source_url, discovered_at, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (source.get_key(), source.channel_name, source.url,
             source.source_url, source.discovered_at.isoformat(), source.status)
        )
        await db.commit()

    async def update_status(self, key: str, status: str, latency: int = 0, success: bool = True):
        if success:
            await db.execute(
                """UPDATE source_pool SET status=?, latency=?, success_count=success_count+1,
                   last_check=? WHERE source_key=?""",
                (status, latency, datetime.now().isoformat(), key)
            )
        else:
            await db.execute(
                """UPDATE source_pool SET status=?, fail_count=fail_count+1,
                   last_check=? WHERE source_key=?""",
                (status, datetime.now().isoformat(), key)
            )
        await db.commit()

    async def get_pending(self, limit: int = 1000) -> List[Source]:
        cursor = await db.execute(
            "SELECT * FROM source_pool WHERE status='pending' ORDER BY discovered_at LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [self._row_to_source(row) for row in rows]

    def _row_to_source(self, row) -> Source:
        return Source(
            channel_name=row[1],
            url=row[2],
            source_url=row[3],
            discovered_at=datetime.fromisoformat(row[4]),
            status=row[6],
            fail_count=row[7],
            success_count=row[8],
            latency=row[9],
            video_codec=row[10],
        )

class CandidateRepository:
    async def add(self, candidate: Candidate):
        await db.execute(
            """INSERT OR REPLACE INTO candidate_pool
               (source_key, channel_name, url, status, discovered_at)
               VALUES (?, ?, ?, ?, ?)""",
            (candidate.source_key, candidate.channel_name, candidate.url,
             candidate.status, candidate.discovered_at.isoformat())
        )
        await db.commit()

    async def update_latency(self, key: str, latency: int, success: bool):
        # 使用原子更新
        await db.execute(
            """UPDATE candidate_pool
               SET check_count = check_count + 1,
                   success_count = success_count + ?,
                   fail_count = fail_count + ?,
                   total_latency = total_latency + ?,
                   avg_latency = (total_latency + ?) / (success_count + ?),
                   last_check = ?
               WHERE source_key = ?""",
            (1 if success else 0, 0 if success else 1,
             latency if success else 0, latency if success else 0,
             1 if success else 0, datetime.now().isoformat(), key)
        )
        await db.commit()

    async def get_observing(self, limit: int = 1000) -> List[Candidate]:
        cursor = await db.execute(
            "SELECT * FROM candidate_pool WHERE status='observing' ORDER BY discovered_at LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [self._row_to_candidate(row) for row in rows]

    async def get_stable_candidates(self) -> List[Candidate]:
        cursor = await db.execute("SELECT * FROM candidate_pool WHERE status='stable'")
        rows = await cursor.fetchall()
        await cursor.close()
        return [self._row_to_candidate(row) for row in rows]

    async def update_status(self, key: str, status: str, promoted_at: Optional[datetime] = None):
        if promoted_at:
            await db.execute(
                "UPDATE candidate_pool SET status=?, promoted_at=? WHERE source_key=?",
                (status, promoted_at.isoformat(), key)
            )
        else:
            await db.execute(
                "UPDATE candidate_pool SET status=? WHERE source_key=?",
                (status, key)
            )
        await db.commit()

    def _row_to_candidate(self, row) -> Candidate:
        return Candidate(
            source_key=row[0],
            channel_name=row[1],
            url=row[2],
            status=row[3],
            check_count=row[4],
            success_count=row[5],
            fail_count=row[6],
            total_latency=row[7],
            avg_latency=row[8],
            last_check=datetime.fromisoformat(row[9]) if row[9] else None,
            discovered_at=datetime.fromisoformat(row[10]),
            promoted_at=datetime.fromisoformat(row[11]) if row[11] else None,
        )

class StableRepository:
    async def get(self, channel_name: str) -> Optional[StableSource]:
        cursor = await db.execute(
            "SELECT * FROM stable_sources WHERE channel_name=?", (channel_name,)
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row:
            return StableSource(
                channel_name=row[0],
                url=row[1],
                latency=row[2],
                video_codec=row[3],
                is_fixed=bool(row[4]),
                auto_optimize=bool(row[5]),
                promoted_at=datetime.fromisoformat(row[6]),
                last_verified=datetime.fromisoformat(row[7]) if row[7] else None,
                fail_count=row[8],
                status=row[9],
            )
        return None

    async def upsert(self, stable: StableSource):
        await db.execute(
            """INSERT OR REPLACE INTO stable_sources
               (channel_name, url, latency, video_codec, is_fixed, auto_optimize,
                promoted_at, last_verified, fail_count, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (stable.channel_name, stable.url, stable.latency, stable.video_codec,
             int(stable.is_fixed), int(stable.auto_optimize),
             stable.promoted_at.isoformat(),
             stable.last_verified.isoformat() if stable.last_verified else None,
             stable.fail_count, stable.status)
        )
        await db.commit()

    async def get_all(self) -> List[StableSource]:
        cursor = await db.execute("SELECT * FROM stable_sources")
        rows = await cursor.fetchall()
        await cursor.close()
        return [StableSource(
            channel_name=r[0], url=r[1], latency=r[2], video_codec=r[3],
            is_fixed=bool(r[4]), auto_optimize=bool(r[5]),
            promoted_at=datetime.fromisoformat(r[6]),
            last_verified=datetime.fromisoformat(r[7]) if r[7] else None,
            fail_count=r[8], status=r[9]
        ) for r in rows]

    async def update_fail_count(self, channel_name: str, fail_count: int, status: str):
        await db.execute(
            "UPDATE stable_sources SET fail_count=?, status=?, last_verified=? WHERE channel_name=?",
            (fail_count, status, datetime.now().isoformat(), channel_name)
        )
        await db.commit()

class CacheRepository:
    async def get(self, cache_key: str) -> Optional[str]:
        cursor = await db.execute(
            "SELECT data, updated_at, ttl_hours FROM cache WHERE cache_key=?",
            (cache_key,)
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row:
            data, updated_at, ttl_hours = row
            if (datetime.now() - datetime.fromisoformat(updated_at)).total_seconds() / 3600 < ttl_hours:
                return data
        return None

    async def set(self, cache_key: str, data: str, cache_type: str, ttl_hours: int):
        await db.execute(
            "INSERT OR REPLACE INTO cache (cache_key, data, cache_type, updated_at, ttl_hours) VALUES (?, ?, ?, ?, ?)",
            (cache_key, data, cache_type, datetime.now().isoformat(), ttl_hours)
        )
        await db.commit()

# 工厂类
class RepositoryFactory:
    def __init__(self):
        self.source_repo = SourceRepository()
        self.candidate_repo = CandidateRepository()
        self.stable_repo = StableRepository()
        self.cache_repo = CacheRepository()

repo_factory = RepositoryFactory()
