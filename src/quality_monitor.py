import aiohttp
import time
from src.settings import settings
from src.logger import logger
from src.repositories import repo_factory

class QualityMonitor:
    async def check_channel(self, channel_name: str, url: str) -> tuple:
        """返回 (是否可用, 延迟ms)"""
        try:
            async with aiohttp.ClientSession() as session:
                start = time.time()
                async with session.head(url, timeout=5) as resp:
                    if resp.status != 200:
                        return False, 0
                async with session.get(url, timeout=settings.timeout) as resp:
                    data = await resp.content.read(settings.download_chunk_size)
                    if not data:
                        return False, 0
                    latency = int((time.time() - start) * 1000)
                    if data.startswith(b'#EXTM3U') or data.startswith(b'\x00\x00\x00\x18ftyp'):
                        return True, latency
                    return False, 0
        except Exception:
            return False, 0
