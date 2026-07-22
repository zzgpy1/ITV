# src/repositories/__init__.py
from src.db import db
from src.repositories.source_repo import SourceRepo
from src.repositories.candidate_repo import CandidateRepo
from src.repositories.stable_repo import StableRepo
from src.repositories.history_repo import HistoryRepo
from src.repositories.cache_repo import CacheRepo

class RepoFactory:
    def __init__(self):
        self._conn = None
        self.source = None
        self.candidate = None
        self.stable = None
        self.history = None
        self.cache = None

    async def init(self):
        self._conn = await db.connect()
        self.source = SourceRepo(self._conn)
        self.candidate = CandidateRepo(self._conn)
        self.stable = StableRepo(self._conn)
        self.history = HistoryRepo(self._conn)
        self.cache = CacheRepo(self._conn)

repo_factory = RepoFactory()
