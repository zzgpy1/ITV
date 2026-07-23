# src/observers/candidate_observer.py
from src.repositories import repo_factory
from src.settings import settings
from src.logger import logger


class CandidateObserver:
    async def observe(self):
        """观察候选池，标记稳定的源"""
        # 获取所有正在观察的候选源
        observing = await repo_factory.candidate.get_observing()
        if not observing:
            logger.info("📭 没有正在观察的候选源")
            return

        logger.info(f"🔍 检查 {len(observing)} 个候选源的状态")

        stable_count = 0
        for cand in observing:
            stats = await repo_factory.candidate.get_stats(cand["key"])
            check_count = stats["check_count"]
            success_count = stats["success_count"]
            fail_count = stats["fail_count"]
            avg_latency = stats["avg_latency"]

            # 判断是否达到稳定标准
            if (check_count >= settings.candidate_min_success and
                success_count / max(check_count, 1) >= settings.candidate_min_success_rate and
                avg_latency <= settings.candidate_max_latency):
                await repo_factory.candidate.mark_stable(cand["key"])
                logger.info(f"✅ 候选源稳定: {cand['name']} (成功率: {success_count}/{check_count}, 延迟: {avg_latency}ms)")
                stable_count += 1
            elif fail_count >= 5:
                # 失败过多，标记为拒绝
                logger.debug(f"❌ 候选源被拒绝: {cand['name']} (失败 {fail_count} 次)")
                # 这里可以记录拒绝状态，暂不实现

        logger.info(f"📊 观察完成: {stable_count} 个源达到稳定标准")
