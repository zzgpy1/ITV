from src.repositories import repo_factory
from src.models import StableSource
from datetime import datetime
from typing import Optional, List

class StableManager:
    async def get(self, channel_name: str) -> Optional[StableSource]:
        return await repo_factory.stable_repo.get(channel_name)

    async def get_all(self) -> List[StableSource]:
        return await repo_factory.stable_repo.get_all()

    async def upsert(self, stable: StableSource):
        await repo_factory.stable_repo.upsert(stable)

    async def promote(self, channel_name: str, url: str, latency: int, video_codec: str = "") -> bool:
        existing = await self.get(channel_name)
        if existing and existing.is_fixed:
            return False
        stable = StableSource(
            channel_name=channel_name,
            url=url,
            latency=latency,
            video_codec=video_codec,
            is_fixed=False,
            auto_optimize=False,
            promoted_at=datetime.now()
        )
        await self.upsert(stable)
        return True

    async def record_failure(self, channel_name: str):
        src = await self.get(channel_name)
        if src:
            await repo_factory.stable_repo.update_fail_count(channel_name, src.fail_count + 1, 'degraded')

    async def record_success(self, channel_name: str):
        await repo_factory.stable_repo.update_fail_count(channel_name, 0, 'active')
