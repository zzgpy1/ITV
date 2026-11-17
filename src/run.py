#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path

from src.config_loader import config
from src.logger import logger
from src.subscribe_manager import SubscribeManager
from src.fetcher import fetch_all_sources_incremental
from src.parser import parse_and_dedupe
from src.speed_tester import test_channels_concurrent
from src.ffmpeg_validator import validate_batch
from src.merger import merge_channels_by_name
from src.blacklist_filter import get_blacklist_filter
from src.demo_filter import parse_demo_order_with_categories
from src.database import get_db_cache
from src.stable.manager import StableManager
from src.generator import generate_outputs_from_demo, quick_generate_from_stable
from src.orchestrator import run_autonomous_mode
from src.fixed_sources import CCTV_FIXED_SOURCES
from src.http_client import HttpClient


async def main():
    logger.info("🚀 IPTV 智能整理平台启动")
    db = await get_db_cache()

    try:
        await db.cleanup_frozen()
        n_frozen = await db.get_frozen_count()
        logger.info(f"❄️ 当前冻结源: {n_frozen}")
    except Exception as e:
        logger.warning(f"清理冻结源失败: {e}")

    stable_mgr = StableManager()

    for name, urls in CCTV_FIXED_SOURCES.items():
        url = urls[0] if isinstance(urls, list) and urls else urls
        if url:
            await stable_mgr.set_fixed_source(name, url, auto_optimize=True)
    logger.info("📌 固定源已同步")

    demo_order = parse_demo_order_with_categories() if config.enable_demo_filter else []

    # 阶段 1：缓存初版
    try:
        stable_all = await stable_mgr.get_stable_sources()
        if stable_all:
            n = quick_generate_from_stable(stable_all, demo_order)
            logger.info(f"⚡ 缓存初版已生成: {n} 个频道")
    except Exception as e:
        logger.warning(f"缓存初版失败: {e}")

    # 阶段 2：完整流程
    sub_mgr = SubscribeManager()
    sources = sub_mgr.get_all_subscribe_urls() or config.iptv_sources
    logger.info(f"📋 使用 {len(sources)} 个源")

    raw_contents = await fetch_all_sources_incremental(sources, db)
    channels_dict = parse_and_dedupe(raw_contents)
    if not channels_dict:
        logger.warning("⚠️ 未获取到任何频道，保留缓存初版输出")
        await db.close()
        await HttpClient.close()
        return 0

    valid_channels = await test_channels_concurrent(channels_dict)
    logger.info(f"📊 通过测速: {len(valid_channels)}")

    if config.ffmpeg_enable and valid_channels:
        valid_channels = await validate_batch(valid_channels)
        logger.info(f"📊 通过ffmpeg: {len(valid_channels)}")

    fixed_sources = await stable_mgr.get_stable_sources()
    merged = merge_channels_by_name(valid_channels, fixed_sources, fixed_sources)
    logger.info(f"📊 合并: {len(merged)}")

    if config.enable_blacklist:
        merged = get_blacklist_filter().filter_channels(merged)
        logger.info(f"📊 黑名单过滤后: {len(merged)}")

    # ===== 关键：直接让 Generator 做分类，不再预先调用 filter_and_order_by_demo =====
    generate_outputs_from_demo(merged, demo_order)
    logger.info(f"✅ 最终输出已生成")

    if config.autonomous_mode:
        await run_autonomous_mode(skip_discover=True)

    logger.info("🎉 全部完成！")
    await db.close()
    await HttpClient.close()
    return 0


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("⚠️ 用户中断")
        sys.exit(1)
