from src.repositories import StableRepository, CandidateRepository
from src.speed_tester import test_channels_concurrent
from src.logger import logger

class QualityMonitor:
    def __init__(self):
        self.stable_repo = StableRepository()
        self.cand_repo = CandidateRepository()

    async def check_all(self):
        stables = await self.stable_repo.get_all()
        if not stables:
            return
        # 转为测速格式
        channels = [{"name": name, "url": s.url} for name, s in stables.items()]
        valid = await test_channels_concurrent(channels)  # 返回有效的列表
        valid_names = {c['name'] for c in valid}
        for name, stable in stables.items():
            if name not in valid_names:
                await self.stable_repo.record_failure(name)
                # 如果失败次数超过阈值，触发替换
                if stable.fail_count >= 3 and not stable.is_fixed:
                    logger.warning(f"{name} 连续失败，尝试替换")
                    # 从候选池找替代
                    candidates = await self.cand_repo.get_stable_candidates()
                    for cand in candidates:
                        if cand.channel_name == name:
                            # 更新稳定源
                            stable.url = cand.url
                            stable.latency = cand.avg_latency
                            await self.stable_repo.upsert(stable)
                            break
            else:
                await self.stable_repo.record_success(name)
