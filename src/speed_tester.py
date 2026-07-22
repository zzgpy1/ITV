import asyncio
import aiohttp
import time
from src.settings import settings
from src.logger import logger
from src.repositories import CandidateRepository, BlacklistRepository, CacheRepository, make_key
from src.models import Candidate

HEADERS = {"User-Agent": "Mozilla/5.0"}
AD_PATTERNS = ['ads?\.', 'adserver', 'doubleclick', 'googlead']

async def is_suspicious(url: str) -> bool:
    import re
    for pat in AD_PATTERNS:
        if re.search(pat, url, re.I):
            return True
    return False

async def probe_channel(session: aiohttp.ClientSession, ch: dict, cand_repo: CandidateRepository, black_repo: BlacklistRepository):
    url = ch['url']
    if await black_repo.is_blacklisted(url):
        return None
    if await is_suspicious(url):
        return None
    key = make_key(ch['name'], url)
    try:
        start = time.time()
        async with session.head(url, timeout=5, allow_redirects=True) as resp:
            if resp.status != 200:
                return None
            ct = resp.headers.get('content-type', '')
            if not any(x in ct for x in ['video', 'mpegurl', 'x-mpegurl']):
                return None
        head_lat = int((time.time() - start) * 1000)
        async with session.get(url, timeout=settings.http_timeout, headers={**HEADERS, "Range": f"bytes=0-{settings.download_chunk_size-1}"}) as resp:
            if resp.status not in [200, 206]:
                return None
            data = await resp.content.read(settings.download_chunk_size)
            if b'#EXTM3U' in data or b'#EXTINF' in data:
                valid = True
            else:
                valid = any(data.startswith(sig) for sig in [b'\x00\x00\x00\x18ftyp', b'\x00\x00\x00\x1cftyp', b'\x1a\x45\xdf\xa3', b'\x47\x40\x00', b'FLV'])
            if not valid:
                return None
            download_time = time.time() - start
            latency = head_lat + int(download_time * 1000)
            # 写入候选统计
            await cand_repo.update_latency(key, latency, True)
            return ch
    except Exception:
        await cand_repo.update_latency(key, 0, False)
        return None

async def test_channels_concurrent(channels: list) -> list:
    cand_repo = CandidateRepository()
    black_repo = BlacklistRepository()
    valid = []
    sem = asyncio.Semaphore(settings.max_workers)
    connector = aiohttp.TCPConnector(limit=settings.max_workers, limit_per_host=5)
    async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=settings.http_timeout+5)) as session:
        tasks = []
        for ch in channels:
            tasks.append(probe_channel(session, ch, cand_repo, black_repo))
        for coro in asyncio.as_completed(tasks):
            res = await coro
            if res:
                valid.append(res)
    logger.info(f"测速完成，有效 {len(valid)}/{len(channels)}")
    return valid
