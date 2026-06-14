# src/ffmpeg_validator.py - 纯批量日志版本

import asyncio
import subprocess
import json
import time
from concurrent.futures import ThreadPoolExecutor
from src.config import FFMPEG_ENABLE, TIMEOUT, FFMPEG_WORKERS
from src.database import get_db_cache, channel_key
from src.logger import logger

_thread_pool = None

# 进度输出间隔（每处理多少个频道输出一次）
PROGRESS_INTERVAL = 200


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
        return {"valid": has_video, "has_video": has_video, "video_codec": video_codec}
    except Exception:
        return {"valid": False, "has_video": False, "video_codec": ""}


async def validate_batch(channels: list) -> list:
    if not FFMPEG_ENABLE:
        logger.info("⚙️ ffmpeg 深度验证未启用，跳过")
        return channels
    
    if not await check_ffprobe():
        logger.warning("⚠️ ffprobe 不可用，跳过深度验证")
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
        else:
            need_validate.append(ch)

    logger.info(f"🔍 ffmpeg 深度验证: {len(need_validate)} 个需验证，{len(valid_channels)} 个来自缓存")
    
    if not need_validate:
        logger.info("✅ 所有频道均来自缓存，无需验证")
        return valid_channels
    
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
    
    total = len(tasks)
    completed = 0
    last_log_count = 0
    start_time = time.time()
    valid_need = []
    
    logger.info(f"  🎬 开始验证 {total} 个频道，每 {PROGRESS_INTERVAL} 个输出一次进度...")
    
    for coro in asyncio.as_completed(tasks):
        res = await coro
        completed += 1
        
        if res is not None:
            valid_need.append(res)
        
        # 每完成 PROGRESS_INTERVAL 个或全部完成时输出一次日志
        if completed - last_log_count >= PROGRESS_INTERVAL or completed == total:
            percent = completed * 100 // total
            elapsed = time.time() - start_time
            speed = completed / elapsed if elapsed > 0 else 0
            logger.info(f"  🎬 验证进度: {completed}/{total} ({percent}%) - 通过: {len(valid_need)} - 速度: {speed:.1f}频道/秒")
            last_log_count = completed
    
    valid_channels.extend(valid_need)
    
    logger.info(f"✅ ffmpeg 验证完成: 通过 {len(valid_channels)}/{len(channels)} 个频道")
    return valid_channels


def cleanup():
    global _thread_pool
    if _thread_pool:
        _thread_pool.shutdown(wait=False)
        _thread_pool = None
