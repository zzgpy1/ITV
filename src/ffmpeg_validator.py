# src/ffmpeg_validator.py
# ffmpeg/ffprobe 深度验证模块，包含缓存、分级验证和轻量级模式

import asyncio
import subprocess
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from src.config import (
    FFMPEG_ENABLE, TIMEOUT, FFMPEG_WORKERS,
    FFMPEG_MODE, FFPROBE_CACHE_HOURS
)
from src.database import get_db_cache, channel_key
from src.logger import logger

_thread_pool = None

# 进度输出间隔
PROGRESS_INTERVAL = 50


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
    """同步执行 ffprobe 验证"""
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
    """快速 HTTP HEAD 检查，用于初筛"""
    import aiohttp
    try:
        timeout_config = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=timeout_config) as session:
            async with session.head(url, allow_redirects=True) as resp:
                if resp.status != 200:
                    return False
                content_type = resp.headers.get("content-type", "").lower()
                # 检查是否为视频流
                if any(ct in content_type for ct in ["video", "mpegurl", "x-mpegurl", "application/vnd.apple.mpegurl"]):
                    return True
                return False
    except Exception:
        return False


async def get_cached_probe_result(db, url: str) -> dict:
    """获取缓存的 ffprobe 结果"""
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
    """保存 ffprobe 结果到缓存"""
    try:
        await db._conn.execute(
            'INSERT OR REPLACE INTO ffprobe_cache (url, valid, video_codec, has_video, updated_at) VALUES (?, ?, ?, ?, ?)',
            (url, result.get("valid", False), result.get("video_codec", ""), result.get("has_video", False), datetime.now().isoformat())
        )
        await db._conn.commit()
    except Exception:
        pass


async def ensure_ffprobe_table(db):
    """确保 ffprobe_cache 表存在"""
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
    """
    分级验证：缓存 → HTTP快速初筛 → ffprobe深度验证
    """
    # 检查模式
    if FFMPEG_MODE == "off":
        logger.info("⚙️ ffmpeg 深度验证已禁用，跳过")
        return channels
    
    if not FFMPEG_ENABLE:
        logger.info("⚙️ ffmpeg 深度验证未启用，跳过")
        return channels
    
    if not await check_ffprobe():
        logger.warning("⚠️ ffprobe 不可用，跳过深度验证")
        return channels

    db = await get_db_cache()
    await ensure_ffprobe_table(db)
    
    # 1. 检查缓存
    cached_valid = []
    need_validate = []
    for ch in channels:
        cached = await get_cached_probe_result(db, ch["url"])
        if cached:
            if cached.get("valid"):
                ch["video_codec"] = cached.get("video_codec", "")
                cached_valid.append(ch)
            # 无效的也跳过，不再重复验证
        else:
            need_validate.append(ch)
    
    logger.info(f"🔍 ffmpeg 深度验证: {len(need_validate)} 个需验证，{len(cached_valid)} 个来自缓存")
    
    # 2. 快速模式或深度模式
    valid = cached_valid.copy()
    
    if not need_validate:
        logger.info("✅ 所有频道均来自缓存，无需验证")
        return valid
    
    if FFMPEG_MODE == "quick":
        # 快速模式：仅 HTTP HEAD 检查
        logger.info("⚡ 快速模式：仅进行 HTTP 快速检查")
        for ch in need_validate:
            if await quick_http_check(ch["url"]):
                ch["video_codec"] = "http_ok"
                valid.append(ch)
                # 缓存结果（快速模式标记）
                await save_probe_result(db, ch["url"], {"valid": True, "video_codec": "http_ok", "has_video": True})
        return valid
    
    # 3. 深度模式（默认）：HTTP 初筛 + ffprobe
    logger.info("🔍 深度模式：HTTP 初筛 + ffprobe 验证")
    
    # HTTP 初筛
    http_passed = []
    http_failed = 0
    for ch in need_validate:
        if await quick_http_check(ch["url"], timeout=3):
            http_passed.append(ch)
        else:
            http_failed += 1
    logger.info(f"📊 HTTP 初筛: {len(http_passed)} 个通过，{http_failed} 个失败")
    
    if not http_passed:
        logger.info("⚠️ 无频道通过 HTTP 初筛，跳过 ffprobe")
        return valid
    
    # ffprobe 深度验证
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
            # 缓存无效结果，避免重复验证
            await save_probe_result(db, ch["url"], result)
            return None
    
    tasks = [validate_one(ch) for ch in http_passed]
    
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
        
        # 每 PROGRESS_INTERVAL 个或全部完成时输出进度
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
