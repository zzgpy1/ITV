# src/observers/candidate_observer.py
from src.repositories import repo_factory
from src.settings import settings
from src.logger import logger


class CandidateObserver:
    def __init__(self):
        self.candidate_repo = None
        self._initialized = False

    async def _ensure_init(self):
        if not self._initialized:
            self.candidate_repo = repo_factory.candidate
            self._initialized = True

    async def observe(self):
        """观察候选池，标记稳定的源"""
        await self._ensure_init()

        # 获取所有正在观察的候选源
        observing = await self.candidate_repo.get_observing()
        if not observing:
            logger.info("📭 没有正在观察的候选源")
            return

        logger.info(f"🔍 检查 {len(observing)} 个候选源的状态")

        stable_count = 0
        for cand in observing:
            stats = await self.candidate_repo.get_stats(cand["key"])
            check_count = stats.get("check_count", 0)
            success_count = stats.get("success_count", 0)
            fail_count = stats.get("fail_count", 0)
            avg_latency = stats.get("avg_latency", 9999)

            # 判断是否达到稳定标准
            min_success = settings.candidate_min_success
            min_rate = settings.candidate_min_success_rate
            max_latency = settings.candidate_max_latency

            if (check_count >= min_success and
                success_count / max(check_count, 1) >= min_rate and
                avg_latency <= max_latency):
                await self.candidate_repo.mark_stable(cand["key"])
                logger.info(f"✅ 候选源稳定: {cand['name']} (成功率: {success_count}/{check_count}, 延迟: {avg_latency}ms)")
                stable_count += 1
            elif fail_count >= 5:
                logger.debug(f"❌ 候选源被拒绝: {cand['name']} (失败 {fail_count} 次)")

        logger.info(f"📊 观察完成: {stable_count} 个源达到稳定标准")
