from src.repositories import CandidateRepository, SourceRepository, make_key
from src.models import Candidate
from src.speed_tester import test_channels_concurrent
from src.settings import settings
from src.logger import logger

class Observer:
    def __init__(self):
        self.cand_repo = CandidateRepository()
        self.source_repo = SourceRepository()

    async def observe(self, limit: int = 1000):
        logger.info("观察候选源...")
        sources = await self.source_repo.get_pending(limit)
        if not sources:
            return
        channels = [{"name": s.channel_name, "url": s.url} for s in sources]
        valid = await test_channels_concurrent(channels)
        # valid 已经更新了候选池统计，但需要将有效的源标记为已加入候选池
        for ch in valid:
            key = make_key(ch['name'], ch['url'])
            # 确保在候选池中存在（如果不存在则添加）
            # 但 test_channels_concurrent 内部调用了 update_latency，如果记录不存在会插入占位记录，所以无需再插入
            # 只需更新源池状态
            await self.source_repo.update_status(key, 'observed')
        # 获取所有稳定候选（用于后续提升）
        stable_candidates = await self.cand_repo.get_stable_candidates()
        logger.info(f"观察完成，有效 {len(valid)} 个，稳定候选 {len(stable_candidates)} 个")
        return stable_candidates
