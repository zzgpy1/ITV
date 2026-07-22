# src/proxy_utils.py
import aiohttp
from src.config_loader import config

async def fetch_with_proxy_fallback(session: aiohttp.ClientSession, url: str):
    try:
        async with session.get(url, timeout=config.http_timeout) as resp:
            if resp.status == 200:
                return await resp.text(), None
    except Exception:
        pass
    return None, None
