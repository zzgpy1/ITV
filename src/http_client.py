# src/http_client.py
import aiohttp
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from src.settings import settings


class HttpClient:
    _instance: Optional[aiohttp.ClientSession] = None

    @classmethod
    def get_session(cls) -> aiohttp.ClientSession:
        if cls._instance is None or cls._instance.closed:
            connector = aiohttp.TCPConnector(limit=100, limit_per_host=20, ttl_dns_cache=300)
            timeout = aiohttp.ClientTimeout(total=settings.TIMEOUT + 5)
            cls._instance = aiohttp.ClientSession(connector=connector, timeout=timeout)
        return cls._instance

    @classmethod
    async def close(cls):
        if cls._instance and not cls._instance.closed:
            await cls._instance.close()
            cls._instance = None

    @classmethod
    @asynccontextmanager
    async def session_context(cls) -> AsyncGenerator[aiohttp.ClientSession, None]:
        session = cls.get_session()
        try:
            yield session
        finally:
            pass
