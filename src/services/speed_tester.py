# src/services/speed_tester.py
import aiohttp
import time
from src.settings import settings
from src.repository import repo_factory
from src.logger import logger
from src.deduplicator import channel_key

async def probe_channel(session, channel, candidate_repo, history_repo, cache_repo):
    url = channel["url"]
    key = channel_key(channel["name"], url)

    # 缓存检查
    cached = await cache_repo.get(key, "speed", settings.cache_speed_hours)
    if cached:
        try:
            data = eval(cached)  # 存储为 repr(dict)
            if data.get("latency", 9999) < settings.slow_speed_threshold:
                channel["latency"] = data["latency"]
                return channel, data["latency"], True
        except:
            pass

    try:
        start = time.time()
        async with session.head(url, timeout=5, allow_redirects=True) as resp:
            if resp.status != 200:
                await candidate_repo.update_latency(key, 0, False)
                await history_repo.add(key, url, 0, False)
                return channel, 0, False

        head_latency = int((time.time() - start) * 1000)
        start_dl = time.time()
        async with session.get(url, timeout=settings.http_timeout,
                               headers={"Range": f"bytes=0-{settings.download_chunk_size-1}"}) as resp:
            if resp.status not in (200, 206):
                await candidate_repo.update_latency(key, 0, False)
                await history_repo.add(key, url, 0, False)
                return channel, 0, False
            data = await resp.content.read(settings.download_chunk_size)
            # 简单验证
            if not data or data.startswith(b'<html'):
                await candidate_repo.update_latency(key, 0, False)
                await history_repo.add(key, url, 0, False)
                return channel, 0, False

        dl_time = time.time() - start_dl
        final_latency = head_latency + int(dl_time * 1000)
        if final_latency > settings.slow_speed_threshold:
            # 慢速，但不丢弃，仅标记
            channel["latency"] = final_latency
            await candidate_repo.update_latency(key, final_latency, True)
            await history_repo.add(key, url, final_latency, True)
            await cache_repo.set(key, repr({"latency": final_latency}), "speed", settings.cache_speed_hours)
            return channel, final_latency, False  # 标记为慢速，但返回有效

        channel["latency"] = final_latency
        await candidate_repo.update_latency(key, final_latency, True)
        await history_repo.add(key, url, final_latency, True)
        await cache_repo.set(key, repr({"latency": final_latency}), "speed", settings.cache_speed_hours)
        return channel, final_latency, True
    except Exception as e:
        logger.debug(f"测速失败 {url}: {e}")
        await candidate_repo.update_latency(key, 0, False)
        await history_repo.add(key, url, 0, False)
        return channel, 0, False
