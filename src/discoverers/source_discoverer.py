# src/discoverers/source_discoverer.py
from src.fetcher import fetch_all_sources
from src.parser import parse_and_dedupe
from src.settings import settings
from src.subscribe_manager import SubscribeManager
from src.logger import logger
from src.classifier import classify_channel

class SourceDiscoverer:
    async def discover(self):
        sub_mgr = SubscribeManager()
        urls = sub_mgr.get_all_subscribe_urls() or settings.raw_sources
        logger.info(f"拉取 {len(urls)} 个订阅源")
        raw = await fetch_all_sources(urls, use_cache=True)
        channels = parse_and_dedupe(raw)
        
        # === 新增：过滤只保留国内频道 ===
        filtered = {}
        kept_categories = {"央视", "卫视", "地方", "港澳台"}
        for key, ch in channels.items():
            cat = classify_channel(ch)
            if cat in kept_categories:
                filtered[key] = ch
        logger.info(f"国内频道过滤: {len(channels)} -> {len(filtered)} (保留 {kept_categories})")
        channels = filtered
        
        result = []
        for key, ch in channels.items():
            result.append({
                "key": key,
                "name": ch["name"],
                "url": ch["url"],
                "source_url": ch.get("source_url", "unknown")
            })
        logger.info(f"发现 {len(result)} 个国内频道")
        return result
