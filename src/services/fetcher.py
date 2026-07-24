# src/services/fetcher.py
"""源获取服务"""

import asyncio
import aiohttp
from typing import Optional, Dict, List

from src.core.config import get_config
from src.core.exceptions import FetchError
from src.infrastructure.database import get_db
from src.infrastructure.http_client import get_http_client
from src.infrastructure.logger import get_logger
from src.services.proxy_utils import fetch_with_proxy_fallback

logger = get_logger(__name__)


async def fetch_source(url: str, db=None, force_refresh: bool = False, http_client=None) -> Optional[str]:
    """
    获取单个源内容
    """
    # 检查缓存
    if not force_refresh and db:
        cached = await db.fetch_one(
            "SELECT content, updated_at FROM raw_cache WHERE url = ?",
            (url,)
        )
        if cached:
            config = get_config()
            from datetime import datetime, timedelta
            if datetime.now() - datetime.fromisoformat(cached["updated_at"]) < timedelta(hours=config.cache_raw_hours):
                logger.debug(f"✅ 使用缓存: {url}")
                return cached["content"]
    
    logger.info(f"🔄 拉取: {url}")
    
    try:
        if http_client is None:
            http_client = await get_http_client()
        
        session = await http_client.get_session()
        content, used_proxy = await fetch_with_proxy_fallback(session, url)
        
        if content is None:
            # 尝试直连
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise FetchError(f"HTTP {resp.status}")
                content = await resp.text()
        
        if content and db:
            await db.execute(
                "INSERT OR REPLACE INTO raw_cache (url, content, updated_at) VALUES (?, ?, ?)",
                (url, content, datetime.now().isoformat())
            )
        
        return content
        
    except aiohttp.ClientError as e:
        logger.warning(f"⚠️ 拉取失败 {url}: {e}")
        raise FetchError(str(e))
    except Exception as e:
        logger.warning(f"⚠️ 拉取失败 {url}: {e}")
        raise FetchError(str(e))


async def fetch_all_sources(sources: List[str], force_refresh: bool = False) -> Dict[str, Optional[str]]:
    """并发拉取所有源"""
    if not sources:
        return {}
    
    db = await get_db()
    http_client = await get_http_client()
    session = await http_client.get_session()
    
    async def fetch_one(url: str) -> tuple:
        try:
            content = await fetch_source(url, db, force_refresh, http_client)
            return url, content
        except FetchError:
            return url, None
    
    tasks = [fetch_one(url) for url in sources]
    results = await asyncio.gather(*tasks)
    
    return dict(results)
