# src/ffmpeg_validator.py
import asyncio
import subprocess
import json
import atexit
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from src.settings import settings
from src.repositories import repo_factory
from src.logger import logger

_thread_pool = None


def get_thread_pool():
    global _thread_pool
    if _thread_pool is None:
        _thread_pool = ThreadPoolExecutor(max_workers=settings.max_workers)
        atexit.register(lambda: _thread_pool.shutdown(wait=False))
    return _thread_pool


async def check_ffprobe():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(get_thread_pool(), _check_ffprobe_sync)


def _check_ffprobe_sync():
    try:
        result = subprocess.run(["ffprobe", "-version"], capture_output=True, timeout=5, text=True)
        return result.returncode == 0
    except Exception:
        return False


def validate_with_ffprobe_sync(url: str, timeout: int) -> dict:
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams",
        "-analyzeduration", "5000000", "-probesize", "5000000", url
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=timeout, text=True)
        if result.returncode != 0:
            return {"valid": False, "has_video": False, "video_codec": ""}
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        for s in streams:
            if s.get("codec_type") == "video":
                return {"valid": True, "has_video": True, "video_codec": s.get("codec_name", "").lower()}
        return {"valid": False, "has_video": False, "video_codec": ""}
    except Exception:
        return {"valid": False, "has_video": False, "video_codec": ""}


async def validate_batch(channels: list) -> list:
    if settings.ffmpeg_mode == "off" or not settings.ffmpeg_enable:
        logger.info("⚙️ ffmpeg 深度验证已禁用，跳过")
        return channels

    if not await check_ffprobe():
        logger.warning("⚠️ ffprobe 不可用，跳过深度验证")
        return channels

    cache_repo = repo_factory.cache
    valid = []
    need_validate = []

    for ch in channels:
        cached = await cache_repo.get(ch["url"], "ffprobe")
        if cached:
            import json
            data = json.loads(cached)
            if data.get("valid"):
                ch["video_codec"] = data.get("video_codec", "")
                valid.append(ch)
            continue
        need_validate.append(ch)

    if not need_validate:
        logger.info("✅ 所有频道均来自缓存，无需深度验证")
        return valid

    logger.info(f"🔍 ffmpeg 深度验证: {len(need_validate)} 个频道")

    semaphore = asyncio.Semaphore(settings.max_workers)

    async def validate_one(ch):
        async with semaphore:
            result = await asyncio.get_event_loop().run_in_executor(
                get_thread_pool(), validate_with_ffprobe_sync, ch["url"], settings.timeout
            )
            await cache_repo.set(ch["url"], json.dumps(result), "ffprobe", settings.ffprobe_cache_hours)
            if result.get("valid"):
                ch["video_codec"] = result.get("video_codec", "")
                return ch
            return None

    tasks = [validate_one(ch) for ch in need_validate]
    results = await asyncio.gather(*tasks)
    valid.extend([r for r in results if r is not None])

    logger.info(f"✅ ffmpeg 验证完成: 通过 {len(valid)}/{len(channels)} 个频道")
    return valid
