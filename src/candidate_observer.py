from src.repositories import repo_factory
from src.models import Candidate
from src.settings import settings
from src.logger import logger

class CandidateObserver:
    async def evaluate_candidates(self):
        """评估候选池，将满足条件的标记为 stable"""
        candidates = await repo_factory.candidate_repo.get_observing(limit=5000)
        promoted = 0
        for cand in candidates:
            if cand.check_count >= settings.candidate_min_success and \
               cand.success_rate >= settings.candidate_min_success_rate and \
               cand.avg_latency <= settings.candidate_max_latency:
                await repo_factory.candidate_repo.update_status(cand.source_key, 'stable')
                promoted += 1
        if promoted:
            logger.info(f"📌 {promoted} 个候选源达到稳定标准")
        return promoted
