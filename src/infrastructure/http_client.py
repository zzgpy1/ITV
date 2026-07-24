# src/infrastructure/http_client.py
"""HTTP 客户端连接池"""

import aiohttp
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Dict, Any

from src.core.config import get_config
from src.core.exceptions import FetchError
from src.infrastructure.logger import get_logger

logger = get_logger(__name__)


class HttpClientPool:
    """HTTP 客户端连接池"""
    
    _instance: Optional["HttpClientPool"] = None
    _session: Optional[aiohttp.ClientSession] = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def get_session(self) -> aiohttp.ClientSession:
        """获取或创建会话"""
        if self._session is None or self._session.closed:
            await self._create_session()
        return self._session
    
    async def _create_session(self) -> None:
        """创建会话"""
        config = get_config()
        
        connector = aiohttp.TCPConnector(
            limit=config.max_workers * 2,
            limit_per_host=config.max_workers,
            ttl_dns_cache=300,
            enable_cleanup_closed=True,
        )
        
        timeout = aiohttp.ClientTimeout(
            total=config.http_timeout + 5,
            connect=config.http_timeout,
            sock_read=config.http_timeout,
        )
        
        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate",
            }
        )
        logger.debug("✅ HTTP 会话已创建")
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[aiohttp.ClientSession, None]:
        """获取会话上下文"""
        session = await self.get_session()
        try:
            yield session
        except aiohttp.ClientError as e:
            logger.error(f"HTTP 请求失败: {e}")
            raise FetchError(f"HTTP 请求失败: {e}")
    
    async def close(self) -> None:
        """关闭会话"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.debug("📦 HTTP 会话已关闭")
    
    async def get(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """GET 请求"""
        session = await self.get_session()
        return await session.get(url, **kwargs)
    
    async def head(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """HEAD 请求"""
        session = await self.get_session()
        return await session.head(url, **kwargs)


# 全局 HTTP 客户端
_http_client: Optional[HttpClientPool] = None


async def get_http_client() -> HttpClientPool:
    """获取 HTTP 客户端实例"""
    global _http_client
    if _http_client is None:
        _http_client = HttpClientPool()
        await _http_client.get_session()
    return _http_client


async def close_http_client() -> None:
    """关闭 HTTP 客户端"""
    global _http_client
    if _http_client:
        await _http_client.close()
        _http_client = None
