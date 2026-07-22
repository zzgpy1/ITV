#!/usr/bin/env python3
import asyncio
import sys
from src.config_loader import config
from src.logger import logger
from src.subscribe_manager import SubscribeManager
from src.fetcher import fetch_all_sources_incremental
from src.parser import parse_and_dedupe
from src.speed_tester import test_channels_concurrent
from src.ffmpeg_validator import validate_batch
from src.merger import merge_channels_by_name
from src.blacklist_filter import get_blacklist_filter
from src.demo_filter import filter_and_order_by_demo, parse_demo_order_with_categories
from src.database import get_db_cache
from src.stable_manager import StableManager
from src.generator import generate_outputs_from_demo
from src.special_categories import collect_and_append_special_categories
from src.alias_matcher import get_alias_matcher

async def run_legacy_mode():
    logger.info("🚀 IPTV 智能整理平台启动 (传统模式)")
    db = await get_db_cache()
    stable_mgr = StableManager()
    await stable_mgr.sync_fixed_sources()

    sub_mgr = SubscribeManager()
    sources = sub_mgr.get_all_subscribe_urls() or config.raw_sources

    raw_contents = await fetch_all_sources_incremental(sources, db)
    channels_dict = parse_and_dedupe(raw_contents)
    if not channels_dict:
        logger.error("❌ 未获取到任何频道")
        return 1

    valid_channels = await test_channels_concurrent(channels_dict)
    if config.ffmpeg_enable and valid_channels:
        valid_channels = await validate_batch(valid_channels)

    merged_channels = merge_channels_by_name(valid_channels)
    if config.enable_blacklist:
        merged_channels = get_blacklist_filter().filter_channels(merged_channels)

    demo_order = parse_demo_order_with_categories() if config.enable_demo_filter else []
    if config.enable_demo_filter and demo_order:
        ordered_channels, _ = filter_and_order_by_demo(merged_channels)
    else:
        ordered_channels = merged_channels

    # 固定源覆盖（强制）
    all_stable = await stable_mgr.get_stable_sources()
    if all_stable:
        fixed_sources = {n: s for n, s in all_stable.items() if s.get('is_fixed', False)}
        for ch in ordered_channels:
            std_name = ch.get('name')
            if std_name in fixed_sources:
                src = fixed_sources[std_name]
                ch['url'] = src['url']
                ch['latency'] = src.get('latency', 50)
                ch['is_fixed'] = True

    generate_outputs_from_demo(ordered_channels, demo_order)
    await collect_and_append_special_categories(config.output_dir, db)

    if config.autonomous_mode:
        from src.orchestrator import run_autonomous_mode
        await run_autonomous_mode(skip_discover=True)

    logger.info("🎉 全部完成！")
    await db.close()
    return 0

if __name__ == "__main__":
    try:
        asyncio.run(run_legacy_mode())
    except KeyboardInterrupt:
        logger.warning("⚠️ 用户中断")
        sys.exit(1)
