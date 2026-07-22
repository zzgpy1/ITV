import aiohttp
from src.settings import settings

_session = None

def get_session():
    global _session
    if _session is None or _session.closed:
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=20)
        timeout = aiohttp.ClientTimeout(total=settings.http_timeout+5)
        _session = aiohttp.ClientSession(connector=connector, timeout=timeout)
    return _session

async def close_session():
    global _session
    if _session:
        await _session.close()
        _session = None
