# src/services/proxy_utils.py
"""代理工具"""

import asyncio
import aiohttp
from urllib.parse import urlparse
from typing import Tuple, Optional

from src.core.config import get_config
from src.infrastructure.logger import get_logger

logger = get_logger(__name__)


def should_proxy(url: str) -> bool:
    """判断是否需要代理"""
    config = get_config()
    if not config.enable_github_proxy:
        return False
    return "raw.githubusercontent.com" in url


def build_proxy_url(original_url: str, proxy_prefix: str) -> str:
    """构建代理 URL"""
    if proxy_prefix.startswith(("https://ghproxy.net/", "https://gh.api.99988866.xyz/")):
        return f"{proxy_prefix}{original_url}"
    elif "raw.staticdn.net" in proxy_prefix or "raw.githubusercontents.com" in proxy_prefix:
        parsed = urlparse(original_url)
        return f"{proxy_prefix}{parsed.path}"
    else:
        return f"{proxy_prefix}{original_url}"


async def fetch_with_proxy_fallback(session: aiohttp.ClientSession, url: str) -> Tuple[Optional[str], Optional[str]]:
    """使用代理回退获取内容"""
    config = get_config()
    
    if not should_proxy(url):
        try:
            async with session.get(url, timeout=config.timeout) as resp:
                if resp.status == 200:
                    return await resp.text(), None
                return None, None
        except Exception as e:
            logger.debug(f"直连 {url} 失败: {e}")
            return None, None
    
    for proxy_prefix in config.github_raw_proxies:
        proxy_url = build_proxy_url(url, proxy_prefix)
        try:
            async with session.get(proxy_url, timeout=config.github_proxy_timeout) as resp:
                if resp.status == 200:
                    logger.debug(f"✅ 代理拉取成功: {proxy_prefix[:40]}...")
                    return await resp.text(), proxy_prefix
                else:
                    logger.debug(f"代理 {proxy_prefix} 返回 {resp.status}")
        except asyncio.TimeoutError:
            logger.warning(f"⏱️ 代理 {proxy_prefix} 超时")
        except Exception as e:
            logger.debug(f"代理 {proxy_prefix} 失败: {e}")
        await asyncio.sleep(0.2)
    
    return None, None
