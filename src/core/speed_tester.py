# src/core/speed_tester.py
import asyncio
import aiohttp
import time
import json
import hashlib
from typing import List, Dict, Tuple
from tqdm.asyncio import tqdm
from src.settings import settings
from src.repositories import repo_factory
from src.logger import logger

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def channel_key(name: str, url: str) -> str:
    return hashlib.md5(f"{name}|{url}".encode()).hexdigest()


class SpeedTester:
    def __init__(self):
        self.candidate_repo = None
        self.history_repo = None
        self.cache_repo = None

    async def _ensure_repos(self):
        """确保 repository 已初始化"""
        if self.candidate_repo is None:
            self.candidate_repo = repo_factory.candidate
            self.history_repo = repo_factory.history
            self.cache_repo = repo_factory.cache

    async def test_batch(self, channels: List[Dict]) -> List[Dict]:
        """测速并返回有效频道列表，同时更新候选池和缓存"""
        if not channels:
            return []

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
        logger.info(f"测速完成: {len(valid)}/{len(channels)} 有效")
        return valid

    async def _test_one(self, session: aiohttp.ClientSession, channel: Dict, semaphore: asyncio.Semaphore):
        async with semaphore:
            name = channel.get("name", "")
            url = channel.get("url", "")
            if not name or not url:
                return None

            key = channel_key(name, url)

            # 快速失败缓存：最近失败过则跳过（1小时内）
            fail_cache_key = f"fail_{key}"
            try:
                fail_cached = await self.cache_repo.get(fail_cache_key, "fail")
                if fail_cached:
                    return None
            except Exception:
                pass

            # 检查测速缓存
            try:
                cached = await self.cache_repo.get(key, "speed")
                if cached:
                    data = json.loads(cached)
                    if data.get("latency", 9999) < settings.slow_speed_threshold:
                        channel["latency"] = data["latency"]
                        channel["video_codec"] = data.get("video_codec", "")
                        return channel
            except Exception:
                pass

            # 执行测速
            try:
                ok, latency, video_codec = await self._probe(session, url)
            except Exception as e:
                logger.debug(f"测速异常 {url}: {e}")
                ok, latency, video_codec = False, 0, ""

            if ok and latency < settings.slow_speed_threshold:
                channel["latency"] = latency
                channel["video_codec"] = video_codec
                try:
                    await self.candidate_repo.update_latency(key, latency, True)
                    await self.history_repo.add(key, url, latency, True)
                    await self.cache_repo.set(key, json.dumps({"latency": latency, "video_codec": video_codec}), "speed", settings.cache_speed_hours)
                except Exception as e:
                    logger.warning(f"更新缓存失败: {e}")
                return channel
            else:
                try:
                    await self.candidate_repo.update_latency(key, latency, False)
                    await self.history_repo.add(key, url, latency, False)
                    # 写入失败缓存，TTL 1小时
                    await self.cache_repo.set(fail_cache_key, "1", "fail", 1)
                except Exception as e:
                    logger.warning(f"更新失败缓存失败: {e}")
                return None

    async def _probe(self, session: aiohttp.ClientSession, url: str) -> Tuple[bool, int, str]:
        """探测单个URL，返回 (是否有效, 延迟ms, 视频编码)"""
        try:
            start = time.time()
            # HEAD 快速检查
            async with session.head(url, timeout=5, allow_redirects=True, headers=HEADERS) as resp:
                if resp.status != 200:
                    return False, 0, ""
            head_latency = int((time.time() - start) * 1000)

            # GET 下载片段
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

            # 简单检测视频流
            is_valid = False
            codec = ""

            # M3U8 检测
            if data.startswith(b'#EXTM3U') or b'#EXTINF' in data:
                is_valid = True
                codec = "h264"
            # 常见容器格式
            elif any(data.startswith(sig) for sig in [
                b'\x00\x00\x00\x18ftyp', b'\x00\x00\x00\x1cftyp',
                b'\x1a\x45\xdf\xa3', b'\x47\x40\x00', b'FLV'
            ]):
                is_valid = True
                codec = "h264"
            else:
                # 尝试检测是否是播放列表（文本）
                try:
                    text = data.decode('utf-8', errors='ignore').lower()
                    if '#extm3u' in text or '#extinf' in text:
                        is_valid = True
                        codec = "h264"
                except Exception:
                    pass

            if is_valid and total_latency < settings.slow_speed_threshold:
                return True, total_latency, codec
            else:
                return False, total_latency, codec

        except asyncio.TimeoutError:
            return False, 0, ""
        except Exception as e:
            logger.debug(f"探测 {url} 异常: {e}")
            return False, 0, ""
