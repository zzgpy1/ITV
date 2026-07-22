# src/repository/__init__.py
from src.db import db
from src.repository.source_repo import SourceRepo
from src.repository.candidate_repo import CandidateRepo
from src.repository.stable_repo import StableRepo
from src.repository.cache_repo import CacheRepo
from src.repository.history_repo import HistoryRepo

class RepoFactory:
    def __init__(self):
        self._conn = None

    async def init(self):
        self._conn = await db.get_connection()

    @property
    def source(self) -> SourceRepo:
        return SourceRepo(self._conn)

    @property
    def candidate(self) -> CandidateRepo:
        return CandidateRepo(self._conn)

    @property
    def stable(self) -> StableRepo:
        return StableRepo(self._conn)

    @property
    def cache(self) -> CacheRepo:
        return CacheRepo(self._conn)

    @property
    def history(self) -> HistoryRepo:
        return HistoryRepo(self._conn)

repo_factory = RepoFactory()
