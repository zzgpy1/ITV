from src.repositories import StableRepository, CandidateRepository
from src.models import Stable
from src.settings import settings
from src.logger import logger

class StableManager:
    def __init__(self):
        self.stable_repo = StableRepository()
        self.cand_repo = CandidateRepository()

    async def promote(self, candidate_key: str):
        cand = await self.cand_repo.get_by_key(candidate_key)  # 需实现，暂略
        if not cand:
            return
        # 检查是否已存在
        existing = await self.stable_repo.get(cand.channel_name)
        if existing and existing.is_fixed:
            logger.warning(f"{cand.channel_name} 是固定源，跳过提升")
            return
        if existing and existing.latency < cand.avg_latency:
            logger.info(f"{cand.channel_name} 现有延迟更优，跳过")
            return
        stable = Stable(
            channel_name=cand.channel_name,
            url=cand.url,
            latency=cand.avg_latency,
            video_codec='',
            is_fixed=False,
            auto_optimize=False,
            promoted_at=datetime.now()
        )
        await self.stable_repo.upsert(stable)
        await self.cand_repo.mark_promoted(candidate_key)
        logger.info(f"提升 {cand.channel_name} 为稳定源")

    async def sync_fixed_sources(self):
        from src.fixed_sources import CCTV_FIXED_SOURCES, ENABLE_FIXED_SOURCES
        if not ENABLE_FIXED_SOURCES:
            return
        for name, urls in CCTV_FIXED_SOURCES.items():
            if isinstance(urls, list):
                url = urls[0] if urls else None
            else:
                url = urls
            if not url:
                continue
            stable = Stable(
                channel_name=name,
                url=url,
                latency=50,
                video_codec='h264',
                is_fixed=True,
                auto_optimize=True
            )
            await self.stable_repo.upsert(stable)
        logger.info("固定源同步完成")
