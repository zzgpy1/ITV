import aiohttp, asyncio, time
from src.settings import settings
from src.repositories import repo_factory
from src.models import Candidate

async def test_channels_concurrent(channels):
    valid = []
    sem = asyncio.Semaphore(settings.max_workers)
    async with aiohttp.ClientSession() as session:
        tasks = [probe_one(session, ch, sem) for ch in channels]
        for result in await asyncio.gather(*tasks):
            if result:
                valid.append(result)
    return valid

async def probe_one(session, channel, sem):
    async with sem:
        url = channel['url']
        try:
            start = time.time()
            async with session.head(url, timeout=5) as resp:
                if resp.status != 200: return None
            # 下载小片段
            async with session.get(url, timeout=settings.timeout) as resp:
                data = await resp.content.read(settings.download_chunk_size)
                if not data: return None
                # 简单验证
                if data.startswith(b'#EXTM3U') or data.startswith(b'\x00\x00\x00\x18ftyp'):
                    latency = int((time.time() - start) * 1000)
                    channel['latency'] = latency
                    # 更新候选池
                    key = f"{channel['name']}|{url}"
                    # 检查是否存在候选，若无则创建
                    cand = Candidate(source_key=key, channel_name=channel['name'], url=url)
                    await repo_factory.candidate_repo.add(cand)
                    await repo_factory.candidate_repo.update_latency(key, latency, True)
                    return channel
        except Exception:
            # 记录失败
            key = f"{channel['name']}|{url}"
            await repo_factory.candidate_repo.update_latency(key, 0, False)
        return None
