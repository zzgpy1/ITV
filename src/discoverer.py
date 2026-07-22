from src.fetcher import Fetcher
from src.parser import parse_and_dedupe
from src.repositories import SourceRepository, make_key
from src.models import Source
from src.settings import settings
from src.logger import logger

class Discoverer:
    def __init__(self):
        self.fetcher = Fetcher()
        self.source_repo = SourceRepository()

    async def discover(self, force_refresh: bool = False) -> int:
        logger.info("开始发现新源...")
        sources = settings.iptv_sources
        raw = await self.fetcher.fetch_all(sources, force_refresh)
        channels = parse_and_dedupe(raw)
        added = 0
        for ch in channels:
            key = make_key(ch['name'], ch['url'])
            src = Source(
                source_key=key,
                channel_name=ch['name'],
                url=ch['url'],
                source_url=ch.get('source_url', 'unknown'),
                status='pending'
            )
            await self.source_repo.add(src)
            added += 1
        logger.info(f"发现 {added} 个新源")
        return added
