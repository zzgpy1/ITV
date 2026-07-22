import asyncio
import subprocess
import json
from src.settings import settings
from src.logger import logger
from src.repositories import CacheRepository, make_key

async def validate_with_ffprobe(url: str) -> dict:
    if not settings.ffmpeg_enable or settings.ffmpeg_mode == "off":
        return {"valid": True, "video_codec": "", "has_video": True}
    # 检查缓存
    cache = CacheRepository()
    key = f"ffprobe_{make_key('', url)}"
    cached = await cache.get(key, "ffprobe", settings.ffprobe_cache_hours)
    if cached:
        import json
        return json.loads(cached)
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams",
           "-analyzeduration", "5000000", "-probesize", "5000000", url]
    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=settings.timeout)
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return {"valid": False, "video_codec": "", "has_video": False}
        data = json.loads(stdout.decode())
        streams = data.get("streams", [])
        has_video = False
        codec = ""
        for s in streams:
            if s.get("codec_type") == "video":
                has_video = True
                codec = s.get("codec_name", "").lower()
                break
        result = {"valid": has_video, "video_codec": codec, "has_video": has_video}
        await cache.set(key, json.dumps(result), "ffprobe", settings.ffprobe_cache_hours)
        return result
    except Exception:
        return {"valid": False, "video_codec": "", "has_video": False}

async def validate_batch(channels: list) -> list:
    if settings.ffmpeg_mode == "off" or not settings.ffmpeg_enable:
        return channels
    sem = asyncio.Semaphore(settings.max_workers)
    valid = []
    for ch in channels:
        async with sem:
            result = await validate_with_ffprobe(ch['url'])
            if result.get('valid'):
                ch['video_codec'] = result.get('video_codec', '')
                valid.append(ch)
    logger.info(f"ffprobe 验证后有效 {len(valid)}/{len(channels)}")
    return valid
