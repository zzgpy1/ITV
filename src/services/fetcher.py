import aiohttp
import asyncio
from src.settings import settings
from src.logger import logger
from src.repositories import repo_factory

async def fetch_all_sources(sources):
    connector = aiohttp.TCPConnector(limit=100)
    timeout = aiohttp.ClientTimeout(total=settings.http_timeout + 5)
    results = {}
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = []
        for url in sources:
            tasks.append(fetch_one(session, url))
        for url, content in zip(sources, await asyncio.gather(*tasks)):
            results[url] = content
    return results

async def fetch_one(session, url):
    # 尝试从缓存读取
    cached = await repo_factory.cache_repo.get(url)
    if cached:
        return cached
    try:
        async with session.get(url, timeout=settings.http_timeout) as resp:
            if resp.status == 200:
                content = await resp.text()
                await repo_factory.cache_repo.set(url, content, 'raw', settings.cache_raw_hours)
                return content
    except Exception as e:
        logger.warning(f"拉取 {url} 失败: {e}")
    return None
