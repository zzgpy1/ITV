import asyncio
import aiohttp
import time
import re
from urllib.parse import urlparse
from tqdm.asyncio import tqdm

from src.config_loader import config
from src.logger import logger
from src.database import get_db_cache, channel_key
from src.http_client import HttpClient

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
HTTP_TIMEOUT = config.http_timeout
DOWNLOAD_CHUNK_SIZE = config.download_chunk_size
MAX_RETRY_BEFORE_BLACKLIST = config.max_retry_before_blacklist
SLOW_SPEED_THRESHOLD = config.slow_speed_threshold
CACHE_SPEED_HOURS = config.cache_speed_hours
HOST_CACHE_TTL = int(config.get("host_cache_ttl_seconds", 300))
FINAL_VERIFY_ENABLE = bool(config.get("final_verify_enable", True))

INVALID_CONTENT_PATTERNS = [r'<html', r'<!DOCTYPE', r'404 not found', r'access denied',
                            r'forbidden', r'请勿滥用', r'该资源暂不可用', r'live\.twitch\.tv/embed', r'youtube\.com']

# Host 级进程内缓存：host -> (latency_ms, success, timestamp)
_HOST_CACHE: dict = {}


def _get_host(url: str) -> str:
    try:
        return urlparse(url).netloc
    except Exception:
        return ""


async def _head_verify(session: aiohttp.ClientSession, url: str, timeout: int = 5) -> bool:
    """最终轻量校验（只 HEAD，不下载）"""
    try:
        async with session.head(url, timeout=timeout, allow_redirects=True, headers=HEADERS) as resp:
            return resp.status == 200
    except Exception:
        return False


async def probe_channel_advanced(session: aiohttp.ClientSession, channel: dict, db):
    """
    返回: (channel, latency, is_valid, speed, is_slow)
    """
    url = channel["url"]

    # 冻结源：若已到期则解冻进入测速
    if await db.is_frozen(url):
        logger.debug(f"⛔ 冻结中跳过: {url[:80]}")
        return channel, 0, False, 0, False

    # 速度缓存
    key = channel_key(channel["name"], url)
    cached = await db.get_speed_result(key, max_age_hours=CACHE_SPEED_HOURS)
    if cached and cached.get("latency", 9999) < SLOW_SPEED_THRESHOLD:
        channel["latency"] = cached["latency"]
        channel["video_codec"] = cached.get("video_codec", "")
        return channel, cached["latency"], True, 0, False

    # Host 缓存
    host = _get_host(url)
    if host:
        h = _HOST_CACHE.get(host)
        if h and (time.time() - h[2]) < HOST_CACHE_TTL and h[1] and h[0] < SLOW_SPEED_THRESHOLD:
            channel["latency"] = h[0]
            channel["_host_cache_hit"] = True
            return channel, h[0], True, 0, False

    try:
        start = time.time()
        async with session.head(url, timeout=5, allow_redirects=True, headers=HEADERS) as resp:
            if resp.status != 200:
                await _record_failure(db, url, key)
                return channel, 0, False, 0, False
            content_type = resp.headers.get("content-type", "").lower()
            if ("video" not in content_type and "mpegurl" not in content_type
                    and "x-mpegurl" not in content_type):
                await _record_failure(db, url, key)
                return channel, 0, False, 0, False

        head_latency = int((time.time() - start) * 1000)
        start_download = time.time()
        range_header = {"Range": f"bytes=0-{DOWNLOAD_CHUNK_SIZE-1}"}
        async with session.get(url, timeout=HTTP_TIMEOUT, headers={**HEADERS, **range_header}) as resp:
            if resp.status not in [200, 206]:
                await _record_failure(db, url, key)
                return channel, head_latency, False, 0, False

            data = await resp.content.read(DOWNLOAD_CHUNK_SIZE)
            if not data:
                await _record_failure(db, url, key)
                return channel, head_latency, False, 0, False

            data_lower = data.lower()
            for pattern in INVALID_CONTENT_PATTERNS:
                if re.search(pattern.encode(), data_lower):
                    await _record_failure(db, url, key)
                    return channel, head_latency, False, 0, False

            is_valid = False
            if data.startswith(b'#EXTM3U') or b'#EXTINF' in data:
                is_valid = True
            else:
                for sig in [b'\x00\x00\x00\x18ftyp', b'\x00\x00\x00\x1cftyp',
                            b'\x1a\x45\xdf\xa3', b'\x47\x40\x00', b'FLV']:
                    if data.startswith(sig):
                        is_valid = True
                        break
            if not is_valid:
                await _record_failure(db, url, key)
                return channel, head_latency, False, 0, False

            download_time = time.time() - start_download
            speed = len(data) / max(download_time, 0.001) / 1024
            final_latency = head_latency + int(download_time * 1000)
            is_slow = final_latency > SLOW_SPEED_THRESHOLD

            # 记录成功 + 解冻
            await db.update_candidate_latency(key, final_latency, True)
            await db.save_speed_history(key, url, final_latency, True)
            if await db.is_frozen(url):
                await db.unfreeze_source(url)
            if host:
                _HOST_CACHE[host] = (final_latency, True, time.time())
            channel["latency"] = final_latency
            channel["speed"] = speed
            return channel, final_latency, True, speed, is_slow

    except Exception as e:
        logger.debug(f"测速失败 {url}: {e}")
        await _record_failure(db, url, key)
        return channel, 0, False, 0, False


async def _record_failure(db, url: str, key: str):
    """记录失败并按阈值触发冻结"""
    fail_streak = await db.increment_fail_count(url)
    if fail_streak >= MAX_RETRY_BEFORE_BLACKLIST:
        # increment_fail_count 内部已冻结，这里仅打日志
        logger.debug(f"❄️ 源连续失败 {fail_streak} 次，已冻结: {url[:80]}")
    await db.update_candidate_latency(key, 0, False)
    await db.save_speed_history(key, url, 0, False)


async def _final_verify_batch(session: aiohttp.ClientSession, channels: list, sem: asyncio.Semaphore) -> list:
    """对入选频道做最终 HEAD 校验，剔除不可用的"""
    if not FINAL_VERIFY_ENABLE or not channels:
        return channels

    async def check(ch):
        async with sem:
            if ch.get("_host_cache_hit") and await _head_verify(session, ch["url"], timeout=5):
                return ch
            # 未走缓存或校验通过
            if not ch.get("_host_cache_hit"):
                return ch  # 已经实际下载测速，无需再校验
            return None

    results = await asyncio.gather(*[check(ch) for ch in channels])
    kept = [r for r in results if r is not None]
    removed = len(channels) - len(kept)
    if removed > 0:
        logger.info(f"🔎 最终校验剔除 {removed} 个 Host 缓存假阳性频道")
    return kept


async def test_channels_concurrent(channels_dict: dict) -> list:
    db = await get_db_cache()
    channels = list(channels_dict.values())
    valid = []
    semaphore = asyncio.Semaphore(config.max_workers)

    # --- 冻结源统计 ---
    frozen_in_batch = 0
    normal_channels = []
    for ch in channels:
        url = ch.get("url")
        if not url or not isinstance(url, str):
            continue
        if await db.is_frozen(url):
            frozen_in_batch += 1
        else:
            normal_channels.append(ch)

    # --- 到期解冻：额外取一批可重测的冻结源加入测速队列 ---
    retest_urls = await db.get_sources_to_retest(limit=500)
    if retest_urls:
        existing_urls = {ch.get("url") for ch in normal_channels}
        for u in retest_urls:
            if u and u not in existing_urls:
                normal_channels.append({"name": "retest", "url": u, "source_key": u})

    frozen_total = await db.get_frozen_count()
    if frozen_in_batch or retest_urls:
        logger.info(f"❄️ 冻结源 {frozen_in_batch} 个跳过；解冻重测 {len(retest_urls)} 个；冻结表总数 {frozen_total}")

    if not normal_channels:
        logger.warning("⚠️ 无可用源测速")
        return []

    async with HttpClient.session_context() as session:
        async def probe_with_semaphore(ch):
            async with semaphore:
                return await probe_channel_advanced(session, ch, db)

        tasks = [probe_with_semaphore(ch) for ch in normal_channels]
        pbar = tqdm(total=len(tasks), desc="🔍 测速+过滤", unit="频道")
        for coro in asyncio.as_completed(tasks):
            ch, latency, ok, speed, is_slow = await coro
            pbar.update(1)
            if ok:
                if not is_slow:
                    valid.append(ch)
                else:
                    # 慢速入候选池
                    k = channel_key(ch["name"], ch["url"])
                    await db.add_to_candidate(k, ch["name"], ch["url"], latency)
                    logger.debug(f"🐢 慢速源: {ch['name']} {latency}ms")
        pbar.close()

        # --- 最终校验 ---
        verified = await _final_verify_batch(session, valid, semaphore)

    logger.info(f"📊 测速完成，有效频道: {len(verified)}/{len(normal_channels)}"
                f"（冻结跳过 {frozen_in_batch}，解冻重测 {len(retest_urls)}）")
    return verified
