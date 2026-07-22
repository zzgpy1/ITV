from datetime import datetime
from src.repositories import StableRepository, CandidateRepository
from src.models import Stable, Candidate
from src.settings import settings
from src.logger import logger


class StableManager:
    def __init__(self):
        self.stable_repo = StableRepository()
        self.cand_repo = CandidateRepository()

    async def promote(self, candidate: Candidate) -> bool:
        """
        将候选源提升为稳定源。
        如果频道已是固定源，或现有稳定源延迟更优，则跳过。
        """
        if not candidate:
            return False

        existing = await self.stable_repo.get(candidate.channel_name)
        if existing and existing.is_fixed:
            logger.warning(f"{candidate.channel_name} 是固定源，跳过自动提升")
            return False

        if existing and existing.latency < candidate.avg_latency:
            logger.info(f"{candidate.channel_name} 现有延迟更优 ({existing.latency}ms vs {candidate.avg_latency}ms)，跳过")
            return False

        stable = Stable(
            channel_name=candidate.channel_name,
            url=candidate.url,
            latency=candidate.avg_latency,
            video_codec='',
            is_fixed=False,
            auto_optimize=False,
            promoted_at=datetime.now(),
            last_verified=datetime.now(),
            fail_count=0,
            status="active"
        )
        await self.stable_repo.upsert(stable)
        await self.cand_repo.mark_promoted(candidate.source_key)
        logger.info(f"✅ 提升 {candidate.channel_name} 为稳定源 (延迟 {candidate.avg_latency}ms)")
        return True

    async def sync_fixed_sources(self):
        """从 fixed_sources.py 同步固定源到数据库"""
        try:
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
                    auto_optimize=True,
                    promoted_at=datetime.now(),
                    last_verified=datetime.now(),
                    fail_count=0,
                    status="active"
                )
                await self.stable_repo.upsert(stable)
            logger.info("📌 固定源同步完成")
        except ImportError:
            logger.warning("fixed_sources.py 未找到，跳过固定源同步")

    async def replace_source(self, channel_name: str, new_url: str, latency: int, video_codec: str = '') -> bool:
        """替换稳定源，保留固定标记"""
        existing = await self.stable_repo.get(channel_name)
        if existing and existing.is_fixed and not existing.auto_optimize:
            logger.warning(f"{channel_name} 是固定源且禁止自动优化，拒绝替换")
            return False
        is_fixed = existing.is_fixed if existing else False
        auto_optimize = existing.auto_optimize if existing else False
        stable = Stable(
            channel_name=channel_name,
            url=new_url,
            latency=latency,
            video_codec=video_codec,
            is_fixed=is_fixed,
            auto_optimize=auto_optimize,
            promoted_at=datetime.now(),
            last_verified=datetime.now(),
            fail_count=0,
            status="active"
        )
        await self.stable_repo.upsert(stable)
        logger.info(f"🔄 {channel_name} 已替换为 {new_url[:60]}...")
        return True

    async def get_all_stables(self) -> dict:
        return await self.stable_repo.get_all()

    async def record_failure(self, channel_name: str):
        await self.stable_repo.record_failure(channel_name)

    async def record_success(self, channel_name: str):
        await self.stable_repo.record_success(channel_name)
