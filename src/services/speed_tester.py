# src/services/speed_tester.py
"""速度测试服务"""

import asyncio
import time
import aiohttp
from typing import Dict, List, Optional, Tuple

from src.core.config import get_config
from src.core.exceptions import SpeedTestError
from src.infrastructure.database import get_db, channel_key
from src.infrastructure.http_client import get_http_client
from src.infrastructure.logger import get_logger
from tqdm.asyncio import tqdm

logger = get_logger(__name__)


class SpeedTester:
    """速度测试器"""
    
    def __init__(self):
        self.config = get_config()
        self.db = None
    
    async def probe_channel(self, channel: Dict, session: aiohttp.ClientSession) -> Tuple[Dict, int, bool, float]:
        """探测单个频道"""
        url = channel["url"]
        
        # 检查黑名单
        self.db = await get_db()
        blacklisted = await self.db.fetch_one(
            "SELECT url FROM blacklist WHERE url = ?",
            (url,)
        )
        if blacklisted:
            logger.debug(f"⛔ 黑名单跳过: {url[:80]}")
            return channel, 0, False, 0
        
        try:
            start = time.time()
            
            # HEAD 请求快速判断
            async with session.head(url, timeout=5, allow_redirects=True) as resp:
                if resp.status != 200:
                    await self._record_failure(url)
                    return channel, 0, False, 0
                
                content_type = resp.headers.get("content-type", "").lower()
                if "video" not in content_type and "mpegurl" not in content_type:
                    await self._record_failure(url)
                    return channel, 0, False, 0
            
            head_latency = int((time.time() - start) * 1000)
            start_download = time.time()
            
            # 下载小片段
            range_header = {"Range": f"bytes=0-{self.config.download_chunk_size-1}"}
            async with session.get(url, timeout=self.config.http_timeout, headers=range_header) as resp:
                if resp.status not in [200, 206]:
                    await self._record_failure(url)
                    return channel, head_latency, False, 0
                
                data = await resp.content.read(self.config.download_chunk_size)
                
                # 检测无效内容
                data_lower = data.lower()
                invalid_patterns = [
                    b"<html", b"<!doctype", b"403", b"forbidden",
                    b"404", b"not found", b"请勿滥用", b"该资源暂不可用"
                ]
                for pattern in invalid_patterns:
                    if pattern in data_lower:
                        await self._record_failure(url)
                        return channel, head_latency, False, 0
                
                # 验证媒体格式
                is_valid = False
                if data.startswith(b'#EXTM3U') or b'#EXTINF' in data:
                    is_valid = True
                else:
                    signatures = [
                        b'\x00\x00\x00\x18ftyp', b'\x00\x00\x00\x1cftyp',
                        b'\x1a\x45\xdf\xa3', b'\x47\x40\x00', b'FLV', b'RIFF'
                    ]
                    for sig in signatures:
                        if data.startswith(sig):
                            is_valid = True
                            break
                
                if not is_valid:
                    await self._record_failure(url)
                    return channel, head_latency, False, 0
                
                download_time = time.time() - start_download
                speed = len(data) / download_time / 1024  # KB/s
                final_latency = head_latency + int(download_time * 1000)
                
                # 记录成功
                await self._record_success(url, final_latency)
                channel["latency"] = final_latency
                channel["speed"] = speed
                
                return channel, final_latency, True, speed
                
        except Exception as e:
            logger.debug(f"测速失败 {url}: {e}")
            await self._record_failure(url)
            return channel, 0, False, 0
    
    async def _record_success(self, url: str, latency: int):
        """记录成功"""
        if self.db:
            await self.db.execute(
                "INSERT INTO speed_history (channel_key, url, timestamp, latency, success) VALUES (?, ?, ?, ?, ?)",
                (channel_key("", url), url, datetime.now().isoformat(), latency, 1)
            )
    
    async def _record_failure(self, url: str):
        """记录失败"""
        if self.db:
            await self.db.execute(
                "INSERT INTO speed_history (channel_key, url, timestamp, latency, success) VALUES (?, ?, ?, ?, ?)",
                (channel_key("", url), url, datetime.now().isoformat(), 0, 0)
            )
    
    async def test_all(self, channels: List[Dict]) -> List[Dict]:
        """测试所有频道"""
        if not channels:
            return []
        
        self.db = await get_db()
        config = get_config()
        semaphore = asyncio.Semaphore(config.max_workers)
        http_client = await get_http_client()
        session = await http_client.get_session()
        
        valid = []
        
        async def test_one(channel: Dict):
            async with semaphore:
                result, latency, ok, speed = await self.probe_channel(channel, session)
                if ok:
                    return result
                return None
        
        tasks = [test_one(ch) for ch in channels]
        
        pbar = tqdm(total=len(tasks), desc="🔍 测速", unit="频道")
        for coro in asyncio.as_completed(tasks):
            result = await coro
            pbar.update(1)
            if result:
                valid.append(result)
        pbar.close()
        
        logger.info(f"📊 测速完成，有效频道: {len(valid)}/{len(channels)}")
        return valid
