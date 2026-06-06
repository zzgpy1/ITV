import asyncio
import aiohttp
import time
from tqdm.asyncio import tqdm
from src.config import HEADERS, TIMEOUT, MAX_WORKERS, ENABLE_IP_RESOLVE
from src.ip_resolver import get_resolver

# 将全局超时从10秒提升到15秒，避免慢速源被误判
REAL_TIMEOUT = TIMEOUT + 5 if TIMEOUT else 15

async def probe_channel(session, channel, semaphore, pbar):
    async with semaphore:
        url = channel.url
        try:
            start = time.time()
            # 使用 GET 而不是 HEAD，因为某些源拒绝 HEAD 请求
            async with session.get(url, timeout=REAL_TIMEOUT, headers=HEADERS, allow_redirects=True) as resp:
                latency = int((time.time() - start) * 1000)
                # 接受 200, 206, 302, 301 等状态码
                if resp.status in (200, 206, 302, 301, 303, 307, 308):
                    # 可选：检查 Content-Type 是否包含 video 或 mpeg
                    content_type = resp.headers.get('Content-Type', '')
                    if 'video' in content_type or 'mpeg' in content_type or 'octet-stream' in content_type:
                        ip_info = None
                        if ENABLE_IP_RESOLVE:
                            resolver = get_resolver()
                            if resolver.is_available:
                                ip_info = resolver.resolve_channel_ip(channel)
                        pbar.update(1)
                        return channel, latency, True, ip_info
                # 即使状态码不是视频类型，也允许通过（有些源返回200但内容是文本）
                if resp.status == 200:
                    ip_info = None
                    if ENABLE_IP_RESOLVE:
                        resolver = get_resolver()
                        if resolver.is_available:
                            ip_info = resolver.resolve_channel_ip(channel)
                    pbar.update(1)
                    return channel, latency, True, ip_info
                else:
                    pbar.update(1)
                    return channel, latency, False, None
        except asyncio.TimeoutError:
            pbar.update(1)
            return channel, 0, False, None
        except Exception:
            pbar.update(1)
            return channel, 0, False, None

async def test_channels_concurrent(channels_dict: dict) -> list:
    channels = list(channels_dict.values())
    print(f"⚡ 开始测速，共 {len(channels)} 个频道，并发数 {MAX_WORKERS}，超时 {REAL_TIMEOUT}s...")

    semaphore = asyncio.Semaphore(MAX_WORKERS)
    connector = aiohttp.TCPConnector(limit=MAX_WORKERS, limit_per_host=5, ttl_dns_cache=300)
    timeout_config = aiohttp.ClientTimeout(total=REAL_TIMEOUT, connect=REAL_TIMEOUT // 2)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout_config, headers=HEADERS) as session:
        pbar = tqdm(total=len(channels), desc="测速进度", unit="个")
        tasks = [probe_channel(session, ch, semaphore, pbar) for ch in channels]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        pbar.close()
    
    valid = []
    for res in results:
        if isinstance(res, Exception):
            continue
        ch, latency, ok, ip_info = res
        if ok:
            ch.latency = latency
            ch.ip_info = ip_info
            valid.append(ch)
    
    # 按延迟排序
    valid.sort(key=lambda x: getattr(x, 'latency', 9999))
    print(f"✅ 测速完成，有效频道 {len(valid)}/{len(channels)}")
    return valid
