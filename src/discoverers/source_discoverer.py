# src/discoverers/source_discoverer.py
from src.fetcher import fetch_all_sources
from src.parser import parse_and_dedupe
from src.settings import settings
from src.repositories import repo_factory
from src.logger import logger


class SourceDiscoverer:
    async def discover(self) -> list:
        # 从配置或订阅文件获取源列表
        sources = settings.raw_sources
        logger.info(f"📡 拉取 {len(sources)} 个订阅源")

        raw = await fetch_all_sources(sources, force_refresh=True)
        channels = parse_and_dedupe(raw)

        result = []
        for key, ch in channels.items():
            result.append({
                "key": key,
                "name": ch["name"],
                "url": ch["url"],
                "source_url": ch.get("source_url", "unknown")
            })

        logger.info(f"✅ 发现 {len(result)} 个频道")
        return result
