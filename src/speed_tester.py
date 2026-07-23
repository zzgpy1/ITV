# src/speed_tester.py
import asyncio
import aiohttp
import time
import hashlib
import json
from typing import List, Dict, Tuple
from tqdm.asyncio import tqdm
from src.settings import settings
from src.repositories import repo_factory
from src.logger import logger

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def channel_key(name: str, url: str) -> str:
    return hashlib.md5(f"{name}|{url}".encode()).hexdigest()


class SpeedTester:
    """测速器 - 每次使用时从 repo_factory 获取 repository"""
    
    async def _get_repos(self):
        """获取 repository 实例，确保已初始化"""
        # 如果 repo_factory 未初始化，等待初始化
        if repo_factory.cache is None:
            await repo_factory.init()
        return repo_factory.cache, repo_factory.candidate, repo_factory.history, repo_factory.source

    async def test_batch(self, channels: List[Dict], source_mode: bool = True) -> List[Dict]:
        """测速并返回有效频道列表"""
        if not channels:
            return []

        cache_repo, candidate_repo, history_repo, source_repo = await self._get_repos()

        semaphore = asyncio.Semaphore(settings.max_workers)
        connector = aiohttp.TCPConnector(limit=settings.max_workers, limit_per_host=5)
        timeout = aiohttp.ClientTimeout(total=settings.http_timeout + 5)

        valid = []
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = [
                self._test_one(session, ch, semaphore, source_mode,
                               cache_repo, candidate_repo, history_repo, source_repo)
                for ch in channels
            ]
            pbar = tqdm(total=len(tasks), desc="🚀 测速")
            for coro in asyncio.as_completed(tasks):
                result = await coro
                pbar.update(1)
                if result:
                    valid.append(result)
            pbar.close()
        return valid

    async def _test_one(
        self,
        session: aiohttp.ClientSession,
        channel: Dict,
        semaphore: asyncio.Semaphore,
        source_mode: bool,
        cache_repo,
        candidate_repo,
        history_repo,
        source_repo
    ):
        async with semaphore:
            name = channel.get("name", "未知")
            url = channel.get("url", "")
            key = channel.get("key") or channel_key(name, url)

            # 检查缓存
            try:
                cached = await cache_repo.get(key, "speed")
                if cached:
                    data = json.loads(cached)
                    if data.get("latency", 9999) < settings.slow_speed_threshold:
                        channel["latency"] = data["latency"]
                        channel["video_codec"] = data.get("video_codec", "")
                        # 更新候选池
                        await candidate_repo.update_latency(key, data["latency"], True)
                        await history_repo.add(key, url, data["latency"], True)
                        if source_mode:
                            await source_repo.update_status(key, "verified", data["latency"], True)
                        return channel
            except (json.JSONDecodeError, KeyError, AttributeError):
                pass

            ok, latency, codec = await self._probe(session, url)

            if ok and latency < settings.slow_speed_threshold:
                channel["latency"] = latency
                channel["video_codec"] = codec
                # 更新候选池
                await candidate_repo.update_latency(key, latency, True)
                await history_repo.add(key, url, latency, True)
                await cache_repo.set(key, json.dumps({"latency": latency, "video_codec": codec}),
                                     "speed", settings.cache_speed_hours)
                if source_mode:
                    await source_repo.update_status(key, "verified", latency, True)
                return channel
            else:
                await candidate_repo.update_latency(key, latency, False)
                await history_repo.add(key, url, latency, False)
                if source_mode:
                    await source_repo.update_status(key, "failed", 0, False)
                return None

    async def _probe(self, session: aiohttp.ClientSession, url: str) -> Tuple[bool, int, str]:
        """探测单个 URL 是否有效"""
        if not url or not url.startswith(('http://', 'https://')):
            return False, 0, ""

        try:
            start = time.time()
            async with session.head(url, timeout=5, allow_redirects=True, headers=HEADERS) as resp:
                if resp.status != 200:
                    return False, 0, ""
            head_latency = int((time.time() - start) * 1000)

            start_dl = time.time()
            async with session.get(url, timeout=settings.http_timeout,
                                   headers={**HEADERS, "Range": f"bytes=0-{settings.download_chunk_size-1}"}) as resp:
                if resp.status not in (200, 206):
                    return False, head_latency, ""
                data = await resp.content.read(settings.download_chunk_size)
                if not data:
                    return False, head_latency, ""
            dl_time = time.time() - start_dl
            total_latency = head_latency + int(dl_time * 1000)

            # 检测是否是有效的视频流
            if data.startswith(b'#EXTM3U') or b'#EXTINF' in data:
                return True, total_latency, "h264"
            if any(data.startswith(sig) for sig in
                   [b'\x00\x00\x00\x18ftyp', b'\x00\x00\x00\x1cftyp',
                    b'\x1a\x45\xdf\xa3', b'\x47\x40\x00', b'FLV']):
                return True, total_latency, "h264"

            # 检查是否返回了 HTML 错误页面
            data_lower = data.lower()
            error_keywords = [b'<html', b'<!doctype', b'403', b'forbidden',
                              b'access denied', b'404', b'not found',
                              b'请勿滥用', b'该资源暂不可用']
            for kw in error_keywords:
                if kw in data_lower:
                    return False, total_latency, ""

            return False, total_latency, ""
        except asyncio.TimeoutError:
            logger.debug(f"⏱️ 测速超时: {url[:60]}...")
            return False, 0, ""
        except Exception as e:
            logger.debug(f"测速失败 {url[:60]}...: {e}")
            return False, 0, ""
