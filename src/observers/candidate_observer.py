# src/observers/candidate_observer.py
from src.repositories import repo_factory
from src.settings import settings
from src.logger import logger

class CandidateObserver:
    async def observe(self):
        """观察候选池，标记稳定的源"""
        observing = await repo_factory.candidate.get_observing()
        if not observing:
            return
        # 这里可以从 speed_history 获取统计，但简化直接基于 candidate 表已有统计
        for cand in observing:
            stats = await repo_factory.candidate.get_stable_candidates()  # 实际应单独查询
            # 这里略，实际应由 orchestrator 调用统一逻辑
        # 标记稳定逻辑在 speed_tester 中已部分更新，此处仅作示例
