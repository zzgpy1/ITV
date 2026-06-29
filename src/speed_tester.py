# src/speed_tester.py
import asyncio
import aiohttp
import time
import re
from tqdm.asyncio import tqdm
from src.config import HEADERS, HTTP_TIMEOUT, DOWNLOAD_CHUNK_SIZE, MAX_RETRY_BEFORE_BLACKLIST, SLOW_SPEED_THRESHOLD
from src.database import get_db_cache, channel_key
from src.logger import logger

AD_PATTERNS = [
    r'ads?\.', r'adserver', r'doubleclick', r'googlead', r'googlesyndication',
    r'amazon-adsystem', r'criteo', r'taboola', r'outbrain', r'scorecardresearch',
    r'moatads', r'openx', r'pubmatic', r'/ad/', r'/ads/', r'/sponsor', r'/promo',
]

INVALID_CONTENT_PATTERNS = [
    r'<html', r'<!DOCTYPE', r'404 not found', r'access denied',
    r'forbidden', r'请勿滥用', r'该资源暂不可用', r'live\.twitch\.tv/embed', r'youtube\.com',
]

def is_suspicious_url(url: str) -> bool:
    url_lower = url.lower()
    for pattern in AD_PATTERNS:
        if re.search(pattern, url_lower):
            return True
    return False

async def probe_channel_advanced(session: aiohttp.ClientSession, channel: dict, db) -> tuple:
    """
    返回 (channel, latency, is_valid, speed, is_slow)
    """
    url = channel["url"]
    # 黑名单检查
    if await db.is_blacklisted(url):
        logger.debug(f"⛔ 黑名单跳过: {url[:80]}")
        return channel, 0, False, 0, False
    
    # 缓存检查
    key = channel_key(channel["name"], url)
    cached = await db.get_speed_result(key)
    if cached and cached.get("latency", 9999) < SLOW_SPEED_THRESHOLD:
        channel["latency"] = cached["latency"]
        channel["video_codec"] = cached.get("video_codec", "")
        return channel, cached["latency"], True, 0, False

    try:
        start = time.time()
        # HEAD 请求
        async with session.head(url, timeout=5, allow_redirects=True, headers=HEADERS) as resp:
            if resp.status != 200:
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
            
            # 视频格式检测
            is_valid = False
            if data.startswith(b'#EXTM3U') or b'#EXTINF' in data:
                is_valid = True
            else:
                for sig in [b'\x00\x00\x00\x18ftyp', b'\x00\x00\x00\x1cftyp', b'\x1a\x45\xdf\xa3', b'\x47\x40\x00', b'FLV']:
                    if data.startswith(sig):
                        is_valid = True
                        break
            
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
    valid = []
    semaphore = asyncio.Semaphore(20)
    
    connector = aiohttp.TCPConnector(limit=20, limit_per_host=3)
    timeout_config = aiohttp.ClientTimeout(total=HTTP_TIMEOUT + 5)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout_config) as session:
        tasks = []
        for ch in channels:
            # 先查黑名单
            if await db.is_blacklisted(ch["url"]):
                logger.debug(f"⛔ 黑名单跳过: {ch['url'][:80]}")
                continue
            tasks.append(probe_channel_advanced(session, ch, db))
        
        # 使用信号量限制并发
        async def probe_with_semaphore(task):
            async with semaphore:
                return await task
        
        # 进度条
        for coro in tqdm.as_completed([probe_with_semaphore(t) for t in tasks], desc="🔍 测速+过滤", unit="频道"):
            ch, latency, ok, speed, is_slow = await coro
            if ok:
                ch["latency"] = latency
                ch["speed"] = speed
                key = channel_key(ch["name"], ch["url"])
                await db.update_candidate_latency(key, latency, True)
                await db.save_speed_history(key, ch["url"], latency, True)
                if is_slow:
                    # 慢速源放入候选池，暂不加入有效列表
                    await db.add_to_candidate(key, ch["name"], ch["url"], latency)
                    logger.debug(f"🐢 慢速源: {ch['name']} {latency}ms")
                else:
                    valid.append(ch)
            else:
                key = channel_key(ch["name"], ch["url"])
                await db.update_candidate_latency(key, 0, False)
                await db.save_speed_history(key, ch["url"], 0, False)
    return valid
