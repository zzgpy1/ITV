import asyncio
import aiohttp
from src.config_loader import config
from src.logger import logger
from src.proxy_utils import fetch_with_proxy_fallback
from src.http_client import HttpClient


class FetchError(Exception):
    pass


async def _do_fetch(url: str, db, force_refresh: bool):
    """实际拉取逻辑，不含超时包装"""
    if not force_refresh and db:
        cached = await db.get_raw_source(url)
        if cached:
            logger.debug(f"✅ 使用缓存: {url}")
            return cached

    logger.info(f"🔄 拉取: {url}")
    async with HttpClient.session_context() as session:
        content, _ = await fetch_with_proxy_fallback(session, url)
        if content is not None:
            if db:
                await db.set_raw_source(url, content)
            return content
        raise FetchError(f"拉取失败: {url}")


async def fetch_url_with_metadata(url: str, db, force_refresh: bool = False):
    """
    带单源超时的拉取：
    - 从 config.get_group_timeout(url) 或 config.fetch_timeout 获取超时秒数
    - 超时后回退到缓存
    """
    timeout = config.get_group_timeout(url)
    try:
        return await asyncio.wait_for(
            _do_fetch(url, db, force_refresh),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        logger.warning(f"⏱️ 源 {url} 拉取超时（{timeout}s），尝试使用缓存")
        if db:
            cached = await db.get_raw_source(url)
            if cached:
                logger.info(f"📦 超时回退到旧缓存: {url}")
                return cached
        return None
    except Exception as e:
        logger.warning(f"⚠️ 拉取失败 {url}: {e}")
        if db:
            cached = await db.get_raw_source(url)
            if cached:
                logger.info(f"📦 失败回退到旧缓存: {url}")
                return cached
        return None


async def fetch_all_sources_incremental(sources: list, db, force_refresh: bool = False) -> dict:
    """并发拉取所有源（每个源独立超时，互不阻塞）"""
    tasks = [fetch_url_with_metadata(url, db, force_refresh) for url in sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    output = {}
    for url, res in zip(sources, results):
        if isinstance(res, Exception):
            logger.warning(f"⚠️ 拉取异常 {url}: {res}")
            output[url] = None
        else:
            output[url] = res
    # 报告概况
    ok = sum(1 for v in output.values() if v)
    logger.info(f"📥 拉取完成: {ok}/{len(sources)} 个源成功")
    return output
