# src/ffmpeg_validator.py
# ffmpeg/ffprobe 深度验证模块，必须包含视频流才有效
# 增加 tqdm 进度条

import asyncio
import subprocess
import json
from concurrent.futures import ThreadPoolExecutor
from tqdm.asyncio import tqdm
from src.config import FFMPEG_ENABLE, TIMEOUT, MAX_WORKERS, FFMPEG_STRICT, FFMPEG_WORKERS
from src.database import get_db_cache, channel_key
from src.logger import logger

_thread_pool = None

def get_thread_pool():
    global _thread_pool
    if _thread_pool is None:
        _thread_pool = ThreadPoolExecutor(max_workers=FFMPEG_WORKERS)
    return _thread_pool

def check_ffprobe_sync():
    try:
        result = subprocess.run(["ffprobe", "-version"], capture_output=True, timeout=5, text=True)
        return result.returncode == 0
    except Exception:
        return False

async def check_ffprobe():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(get_thread_pool(), check_ffprobe_sync)

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
        has_video = False
        video_codec = ""
        for s in streams:
            if s.get("codec_type") == "video":
                has_video = True
                video_codec = s.get("codec_name", "").lower()
                break
        valid = has_video
        return {"valid": valid, "has_video": has_video, "video_codec": video_codec}
    except Exception:
        return {"valid": False, "has_video": False, "video_codec": ""}

async def validate_batch(channels: list, pbar: tqdm = None) -> list:
    if not FFMPEG_ENABLE:
        logger.info("⚙️ ffmpeg 深度验证未启用，跳过")
        return channels
    if not await check_ffprobe():
        logger.warning("⚠️ ffprobe 不可用，跳过深度验证，全部频道视为有效")
        return channels

    db = await get_db_cache()
    need_validate = []
    valid_channels = []
    for ch in channels:
        key = channel_key(ch["name"], ch["url"])
        cached = await db.get_speed_result(key)
        if cached and cached.get("video_codec"):
            ch["video_codec"] = cached["video_codec"]
            valid_channels.append(ch)
            if pbar:
                pbar.update(1)
        else:
            need_validate.append(ch)

    logger.info(f"🔍 ffmpeg 深度验证: {len(need_validate)} 个需要验证，{len(valid_channels)} 个来自缓存")
    
    if need_validate:
        semaphore = asyncio.Semaphore(FFMPEG_WORKERS)
        async def validate_one(ch):
            async with semaphore:
                result = await asyncio.get_event_loop().run_in_executor(
                    get_thread_pool(), validate_with_ffprobe_sync, ch["url"], TIMEOUT
                )
                if result.get("valid"):
                    ch["video_codec"] = result.get("video_codec", "")
                    key = channel_key(ch["name"], ch["url"])
                    await db.set_speed_result(key, ch)
                    return ch
                return None
        
        tasks = [validate_one(ch) for ch in need_validate]
        results = []
        for coro in tqdm.as_completed(tasks, desc="🎬 ffmpeg深度验证", unit="频道", total=len(tasks), leave=False, position=0):
            res = await coro
            results.append(res)
            if pbar:
                pbar.update(1)
        valid_need = [r for r in results if r is not None]
        valid_channels.extend(valid_need)
    
    logger.info(f"🔍 ffmpeg 深度验证完成，通过 {len(valid_channels)}/{len(channels)} 个频道")
    return valid_channels

def cleanup():
    global _thread_pool
    if _thread_pool:
        _thread_pool.shutdown(wait=False)
        _thread_pool = None
