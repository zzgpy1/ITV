# src/core/speed_tester.py
import asyncio
import aiohttp
import time
from typing import List, Dict, Tuple
from tqdm.asyncio import tqdm
from src.settings import settings
from src.repositories import repo_factory
from src.logger import logger
import hashlib

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def channel_key(name: str, url: str) -> str:
    return hashlib.md5(f"{name}|{url}".encode()).hexdigest()

class SpeedTester:
    def __init__(self):
        # 延迟获取 repo，避免在 init 时未初始化
        self._cache_repo = None
        self._candidate_repo = None
        self._history_repo = None

    async def _ensure_repos(self):
        if self._cache_repo is None:
            self._cache_repo = repo_factory.cache
            self._candidate_repo = repo_factory.candidate
            self._history_repo = repo_factory.history

    async def test_batch(self, channels: List[Dict]) -> List[Dict]:
        """测速并返回有效频道列表，同时更新候选池和缓存"""
        await self._ensure_repos()
        semaphore = asyncio.Semaphore(settings.max_workers)
        connector = aiohttp.TCPConnector(limit=settings.max_workers, limit_per_host=5)
        timeout = aiohttp.ClientTimeout(total=settings.http_timeout + 5)

        valid = []
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = [self._test_one(session, ch, semaphore) for ch in channels]
            pbar = tqdm(total=len(tasks), desc="🚀 测速")
            for coro in asyncio.as_completed(tasks):
                result = await coro
                pbar.update(1)
                if result:
                    valid.append(result)
            pbar.close()
        return valid

    async def _test_one(self, session: aiohttp.ClientSession, channel: Dict, semaphore: asyncio.Semaphore):
        async with semaphore:
            name = channel["name"]
            url = channel["url"]
            key = channel_key(name, url)

            # 检查缓存
            cached = await self._cache_repo.get(key, "speed")
            if cached:
                import json
                data = json.loads(cached)
                if data.get("latency", 9999) < settings.slow_speed_threshold:
                    channel["latency"] = data["latency"]
                    channel["video_codec"] = data.get("video_codec", "")
                    return channel

            # 执行测速
            ok, latency, video_codec = await self._probe(session, url)
            if ok and latency < settings.slow_speed_threshold:
                channel["latency"] = latency
                channel["video_codec"] = video_codec
                # 更新候选池和缓存
                await self._candidate_repo.update_latency(key, latency, True)
                await self._history_repo.add(key, url, latency, True)
                await self._cache_repo.set(key, f'{{"latency": {latency}, "video_codec": "{video_codec}"}}', "speed", settings.cache_speed_hours)
                return channel
            else:
                await self._candidate_repo.update_latency(key, latency, False)
                await self._history_repo.add(key, url, latency, False)
                return None

    async def _probe(self, session: aiohttp.ClientSession, url: str) -> Tuple[bool, int, str]:
        try:
            start = time.time()
            async with session.head(url, timeout=5, allow_redirects=True, headers=HEADERS) as resp:
                if resp.status != 200:
                    return False, 0, ""
            head_latency = int((time.time() - start) * 1000)

            start_dl = time.time()
            async with session.get(url, timeout=settings.http_timeout, headers={**HEADERS, "Range": f"bytes=0-{settings.download_chunk_size-1}"}) as resp:
                if resp.status not in (200, 206):
                    return False, head_latency, ""
                data = await resp.content.read(settings.download_chunk_size)
                if not data:
                    return False, head_latency, ""
            dl_time = time.time() - start_dl
            total_latency = head_latency + int(dl_time * 1000)

            # 简单视频检测
            if data.startswith(b'#EXTM3U') or b'#EXTINF' in data:
                is_valid = True
                codec = "h264"
            elif any(data.startswith(sig) for sig in [b'\x00\x00\x00\x18ftyp', b'\x00\x00\x00\x1cftyp', b'\x1a\x45\xdf\xa3', b'\x47\x40\x00', b'FLV']):
                is_valid = True
                codec = "h264"
            else:
                is_valid = False
                codec = ""

            if is_valid and total_latency < settings.slow_speed_threshold:
                return True, total_latency, codec
            else:
                return False, total_latency, codec
        except Exception as e:
            logger.debug(f"测速失败 {url}: {e}")
            return False, 0, ""
