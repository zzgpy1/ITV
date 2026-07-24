# src/services/__init__.py
"""服务模块"""

from src.services.fetcher import fetch_source, fetch_all_sources
from src.services.parser import parse_content, parse_m3u, parse_txt, apply_alias_to_channels
from src.services.speed_tester import SpeedTester
from src.services.validator import Validator
from src.services.merger import Merger
from src.services.generator import Generator
from src.services.demo_service import load_demo_order, match_channel_name
from src.services.subscribe_manager import get_subscribe_urls, SubscribeManager
from src.services.special_categories import collect_and_append_special_categories
from src.services.proxy_utils import fetch_with_proxy_fallback, should_proxy

__all__ = [
    "fetch_source",
    "fetch_all_sources",
    "parse_content",
    "parse_m3u",
    "parse_txt",
    "apply_alias_to_channels",
    "SpeedTester",
    "Validator",
    "Merger",
    "Generator",
    "load_demo_order",
    "match_channel_name",
    "get_subscribe_urls",
    "SubscribeManager",
    "collect_and_append_special_categories",
    "fetch_with_proxy_fallback",
    "should_proxy",
]
