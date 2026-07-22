import asyncio
import subprocess
import json
import time
from concurrent.futures import ThreadPoolExecutor
from src.settings import settings
from src.logger import logger
from src.repositories import repo_factory

_thread_pool = None

def get_thread_pool():
    global _thread_pool
    if _thread_pool is None:
        _thread_pool = ThreadPoolExecutor(max_workers=settings.max_workers // 2)
    return _thread_pool

def check_ffprobe_sync():
    try:
        result = subprocess.run(["ffprobe", "-version"], capture_output=True, timeout=5, text=True)
        return result.returncode == 0
    except Exception:
        return False

async def validate_batch(channels: list) -> list:
    if settings.ffmpeg_mode == "off" or not settings.ffmpeg_enable:
        return channels
    if not await asyncio.get_event_loop().run_in_executor(get_thread_pool(), check_ffprobe_sync):
        logger.warning("⚠️ ffprobe 不可用，跳过深度验证")
        return channels

    valid = []
    sem = asyncio.Semaphore(settings.max_workers // 2)

    async def validate_one(ch):
        async with sem:
            # 检查缓存
            cache_key = f"ffprobe_{ch['url']}"
            cached = await repo_factory.cache_repo.get(cache_key)
            if cached:
                if cached == "valid":
                    ch["video_codec"] = "h264"
                    return ch
                return None
            # 执行 ffprobe
            result = await asyncio.get_event_loop().run_in_executor(
                get_thread_pool(), _probe_sync, ch["url"]
            )
            if result.get("valid"):
                ch["video_codec"] = result.get("video_codec", "h264")
                await repo_factory.cache_repo.set(cache_key, "valid", "ffprobe", settings.ffprobe_cache_hours)
                return ch
            else:
                await repo_factory.cache_repo.set(cache_key, "invalid", "ffprobe", settings.ffprobe_cache_hours)
                return None

    tasks = [validate_one(ch) for ch in channels]
    results = await asyncio.gather(*tasks)
    valid = [r for r in results if r is not None]
    logger.info(f"🎬 ffmpeg 验证通过 {len(valid)}/{len(channels)}")
    return valid

def _probe_sync(url: str) -> dict:
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams",
        "-analyzeduration", "5000000", "-probesize", "5000000", url
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=settings.timeout, text=True)
        if result.returncode != 0:
            return {"valid": False}
        data = json.loads(result.stdout)
        for s in data.get("streams", []):
            if s.get("codec_type") == "video":
                return {"valid": True, "video_codec": s.get("codec_name", "h264")}
        return {"valid": False}
    except Exception:
        return {"valid": False}
