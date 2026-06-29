# src/speed_tester.py
import asyncio
import aiohttp
import time
import re
from src.config import HEADERS, HTTP_TIMEOUT, DOWNLOAD_CHUNK_SIZE, MAX_RETRY_BEFORE_BLACKLIST, SLOW_SPEED_THRESHOLD
from src.database import get_db_cache, channel_key
from src.logger import logger
from tqdm.asyncio import tqdm

AD_PATTERNS = [...原有...]
INVALID_CONTENT_PATTERNS = [...原有...]

def is_suspicious_url(url: str) -> bool:
    ...

async def probe_channel_advanced(session: aiohttp.ClientSession, channel: dict, db) -> tuple:
    """增强探测，返回 (channel, latency, is_valid, speed, is_slow)"""
    url = channel["url"]
    # 黑名单检查
    if await db.is_blacklisted(url):
        return channel, 0, False, 0, False
    
    # 检查缓存
    key = channel_key(channel["name"], url)
    cached = await db.get_speed_result(key)
    if cached and cached.get("latency", 9999) < 5000:
        channel["latency"] = cached["latency"]
        channel["video_codec"] = cached.get("video_codec", "")
        return channel, cached["latency"], True, 0, False

    try:
        start = time.time()
        # HEAD 请求
        async with session.head(url, timeout=5, allow_redirects=True, headers=HEADERS) as resp:
            if resp.status != 200:
                # 记录失败
                await db.increment_fail_count(url)
                return channel, 0, False, 0, False
            content_type = resp.headers.get("content-type", "").lower()
            if "video" not in content_type and "mpegurl" not in content_type and "x-mpegurl" not in content_type:
                await db.increment_fail_count(url)
                return channel, 0, False, 0, False
        
        head_latency = int((time.time() - start) * 1000)
        start_download = time.time()
        # 分段下载
        async with session.get(url, timeout=HTTP_TIMEOUT, headers={**HEADERS, "Range": f"bytes=0-{DOWNLOAD_CHUNK_SIZE-1}"}) as resp:
            if resp.status not in [200, 206]:
                await db.increment_fail_count(url)
                return channel, head_latency, False, 0, False
            
            data = await resp.content.read(DOWNLOAD_CHUNK_SIZE)
            # 检查无效内容
            data_lower = data.lower()
            for pattern in INVALID_CONTENT_PATTERNS:
                if re.search(pattern.encode(), data_lower):
                    await db.increment_fail_count(url)
                    return channel, head_latency, False, 0, False
            
            # 检查视频格式
            is_valid = False
            if data.startswith(b'#EXTM3U') or b'#EXTINF' in data:
                is_valid = True
            else:
                for sig in [b'\x00\x00\x00\x18ftyp', b'\x00\x00\x00\x1cftyp', b'\x1a\x45\xdf\xa3', b'\x47\x40\x00', b'FLV']:
                    if data.startswith(sig):
                        is_valid = True; break
            
            if not is_valid:
                await db.increment_fail_count(url)
                return channel, head_latency, False, 0, False
            
            download_time = time.time() - start_download
            speed = len(data) / download_time / 1024  # KB/s
            final_latency = head_latency + int(download_time * 1000)
            is_slow = final_latency > SLOW_SPEED_THRESHOLD
            return channel, final_latency, True, speed, is_slow
    except Exception:
        fail_count = await db.increment_fail_count(url)
        if fail_count >= MAX_RETRY_BEFORE_BLACKLIST:
            await db.add_to_blacklist(url, "连续失败")
        return channel, 0, False, 0, False

async def test_channels_concurrent(channels_dict: dict) -> list:
    db = await get_db_cache()
    channels = list(channels_dict.values())
    results = []
    semaphore = asyncio.Semaphore(20)
    async with aiohttp.ClientSession() as session:
        tasks = []
        for ch in channels:
            if await db.is_blacklisted(ch["url"]):
                continue
            tasks.append(self._probe_wrapper(session, ch, db, semaphore))
        for coro in tqdm.as_completed(tasks, desc="🔍 测速+过滤", unit="频道"):
            result = await coro
            if result:
                results.append(result)
    return results

async def _probe_wrapper(session, ch, db, sem):
    async with sem:
        ch, latency, ok, speed, is_slow = await probe_channel_advanced(session, ch, db)
        if ok:
            ch["latency"] = latency
            ch["speed"] = speed
            # 更新候选池
            key = channel_key(ch["name"], ch["url"])
            await db.update_candidate_latency(key, latency, True)
            await db.save_speed_history(key, ch["url"], latency, True)
            # 如果速度慢，加入候选池等待下次再测
            if is_slow:
                await db.add_to_candidate(key, ch["name"], ch["url"], latency)
                return None  # 不立即返回，等待下次
            return ch
        else:
            key = channel_key(ch["name"], ch["url"])
            await db.update_candidate_latency(key, 0, False)
            await db.save_speed_history(key, ch["url"], 0, False)
            return None
