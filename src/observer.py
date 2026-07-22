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
        # 转为测速格式
        channels = [{"name": s.channel_name, "url": s.url} for s in sources]
        valid = await test_channels_concurrent(channels)
        # valid 已经更新了候选池统计（在 speed_tester 中调用了 update_latency）
        # 但我们需要将有效的源加入候选池（如果还没有）
        for ch in valid:
            key = make_key(ch['name'], ch['url'])
            # 检查是否已在候选池
            # 由于我们未提供 get 方法，简单插入（存在则忽略）
            cand = Candidate(source_key=key, channel_name=ch['name'], url=ch['url'])
            await self.cand_repo.add(cand)
            # 标记源池为已处理
            await self.source_repo.update_status(key, 'observed')
        # 提升稳定候选
        stable_candidates = await self.cand_repo.get_stable_candidates()
        # 判断条件（由外部调用 promote）
        return stable_candidates
