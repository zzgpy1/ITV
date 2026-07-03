# src/ffmpeg_validator.py
import asyncio
import subprocess
import json
import time
import atexit
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from src.config import FFMPEG_ENABLE, TIMEOUT, FFMPEG_WORKERS, FFMPEG_MODE, FFPROBE_CACHE_HOURS
from src.database import get_db_cache, channel_key
from src.logger import logger
from src.stable.manager import StableManager

_thread_pool = None
PROGRESS_INTERVAL = 50

def get_thread_pool():
    global _thread_pool
    if _thread_pool is None:
        _thread_pool = ThreadPoolExecutor(max_workers=FFMPEG_WORKERS)
        atexit.register(cleanup)
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

async def quick_http_check(url: str, timeout: int = 3) -> bool:
    import aiohttp
    try:
        timeout_config = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=timeout_config) as session:
            async with session.head(url, allow_redirects=True) as resp:
                if resp.status != 200:
                    return False
                content_type = resp.headers.get("content-type", "").lower()
                if any(ct in content_type for ct in ["video", "mpegurl", "x-mpegurl", "application/vnd.apple.mpegurl"]):
                    return True
                return False
    except Exception:
        return False

async def get_cached_probe_result(db, url: str) -> dict:
    try:
        cursor = await db._conn.execute(
            'SELECT valid, video_codec, has_video, updated_at FROM ffprobe_cache WHERE url = ?',
            (url,)
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row:
            valid, video_codec, has_video, updated_at = row
            if datetime.now() - datetime.fromisoformat(updated_at) < timedelta(hours=FFPROBE_CACHE_HOURS):
                return {"valid": bool(valid), "video_codec": video_codec, "has_video": bool(has_video)}
    except Exception:
        pass
    return None

async def save_probe_result(db, url: str, result: dict):
    try:
        await db._conn.execute(
            'INSERT OR REPLACE INTO ffprobe_cache (url, valid, video_codec, has_video, updated_at) VALUES (?, ?, ?, ?, ?)',
            (url, result.get("valid", False), result.get("video_codec", ""), result.get("has_video", False), datetime.now().isoformat())
        )
        await db._conn.commit()
    except Exception:
        pass

async def ensure_ffprobe_table(db):
    try:
        await db._conn.execute('''
            CREATE TABLE IF NOT EXISTS ffprobe_cache (
                url TEXT PRIMARY KEY,
                valid INTEGER,
                video_codec TEXT,
                has_video INTEGER,
                updated_at TIMESTAMP
            )
        ''')
        await db._conn.commit()
    except Exception:
        pass

async def validate_batch(channels: list) -> list:
    if FFMPEG_MODE == "off" or not FFMPEG_ENABLE:
        logger.info("⚙️ ffmpeg 深度验证已禁用，跳过")
        return channels
    if not await check_ffprobe():
        logger.warning("⚠️ ffprobe 不可用，跳过深度验证")
        return channels

    db = await get_db_cache()
    await ensure_ffprobe_table(db)

    stable_mgr = StableManager()
    stable_names = set(stable_mgr.get_active_sources().keys())

    cached_valid = []
    need_validate = []
    http_only = []

    for ch in channels:
        cached = await get_cached_probe_result(db, ch["url"])
        if cached:
            if cached.get("valid"):
                ch["video_codec"] = cached.get("video_codec", "")
                cached_valid.append(ch)
            continue
        if ch['name'] in stable_names and ch['name']:
            if await quick_http_check(ch['url'], timeout=2):
                ch['video_codec'] = 'h264'
                http_only.append(ch)
            else:
                need_validate.append(ch)
        else:
            need_validate.append(ch)

    logger.info(f"🔍 ffmpeg 深度验证: {len(need_validate)} 个需验证，{len(cached_valid)} 个来自缓存，{len(http_only)} 个仅HTTP通过")

    valid = cached_valid + http_only

    if not need_validate:
        logger.info("✅ 所有频道均来自缓存或仅HTTP验证，无需深度验证")
        return valid

    if FFMPEG_MODE == "quick":
        for ch in need_validate:
            if await quick_http_check(ch["url"]):
                ch["video_codec"] = "http_ok"
                valid.append(ch)
                await save_probe_result(db, ch["url"], {"valid": True, "video_codec": "http_ok", "has_video": True})
        return valid

    # 深度模式
    semaphore = asyncio.Semaphore(FFMPEG_WORKERS)
    async def validate_one(ch):
        async with semaphore:
            result = await asyncio.get_event_loop().run_in_executor(
                get_thread_pool(), validate_with_ffprobe_sync, ch["url"], TIMEOUT
            )
            if result.get("valid"):
                ch["video_codec"] = result.get("video_codec", "")
                await save_probe_result(db, ch["url"], result)
                return ch
            await save_probe_result(db, ch["url"], result)
            return None

    tasks = [validate_one(ch) for ch in need_validate]
    total = len(tasks)
    completed = 0
    last_progress = 0
    start_time = time.time()
    valid_need = []

    logger.info(f"  🎬 开始 ffprobe 验证 {total} 个频道...")
    for coro in asyncio.as_completed(tasks):
        res = await coro
        completed += 1
        if res is not None:
            valid_need.append(res)
        if completed - last_progress >= PROGRESS_INTERVAL or completed == total:
            percent = completed * 100 // total
            elapsed = time.time() - start_time
            speed = completed / elapsed if elapsed > 0 else 0
            logger.info(f"  🎬 验证进度: {completed}/{total} ({percent}%) - 通过: {len(valid_need)} - 速度: {speed:.1f}频道/秒")
            last_progress = completed

    valid.extend(valid_need)
    logger.info(f"✅ ffmpeg 验证完成: 通过 {len(valid)}/{len(channels)} 个频道")
    return valid

def cleanup():
    global _thread_pool
    if _thread_pool:
        _thread_pool.shutdown(wait=False)
        _thread_pool = None
