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
from src.demo_filter import filter_and_order_by_demo, parse_demo_order_with_categories
from src.database import get_db_cache
from src.stable_manager import StableManager
from src.aggregator import ResultAggregator
from src.generator import generate_outputs_from_demo
from src.special_categories import collect_and_append_special_categories
import datetime

async def run_legacy_mode():
    logger.info("🚀 IPTV 智能整理平台启动 (传统模式)")
    logger.info(f"📡 配置：超时={config.timeout}s, 并发={config.max_workers}, ffmpeg={config.ffmpeg_enable}")

    # 初始化数据库
    db = await get_db_cache()
    stable_mgr = StableManager()
    await stable_mgr.sync_fixed_sources()  # 导入固定源

    # 1. 获取订阅源列表
    sub_mgr = SubscribeManager()
    subscribe_urls = sub_mgr.get_all_subscribe_urls()
    if subscribe_urls:
        logger.info(f"📋 使用订阅源：{len(subscribe_urls)} 个")
        sources = subscribe_urls
    else:
        sources = config.raw_sources  # 使用默认
        logger.info(f"📋 使用默认源：{len(sources)} 个")

    # 2. 拉取
    raw_contents = await fetch_all_sources_incremental(sources, db)
    channels_dict = parse_and_dedupe(raw_contents)
    if not channels_dict:
        logger.error("❌ 未获取到任何频道")
        return 1

    # 3. 测速与验证
    valid_channels = await test_channels_concurrent(channels_dict)
    logger.info(f"📊 通过测速的频道数: {len(valid_channels)}")
    if config.ffmpeg_enable and valid_channels:
        valid_channels = await validate_batch(valid_channels)
        logger.info(f"📊 通过ffmpeg验证的频道数: {len(valid_channels)}")

    # 4. 合并
    merged_channels = merge_channels_by_name(valid_channels)
    logger.info(f"📊 合并后的频道数: {len(merged_channels)}")

    # 黑名单过滤
    if config.enable_blacklist:
        blacklist_filter = get_blacklist_filter()
        merged_channels = blacklist_filter.filter_channels(merged_channels)
        logger.info(f"📊 黑名单过滤后: {len(merged_channels)}")

    # Demo 筛选
    demo_order = parse_demo_order_with_categories() if config.enable_demo_filter else []
    if config.enable_demo_filter and demo_order:
        ordered_channels, unmatched = filter_and_order_by_demo(merged_channels)
        logger.info(f"📊 Demo筛选后: {len(ordered_channels)}")
    else:
        ordered_channels = merged_channels

    # 5. 使用稳定源覆盖（从数据库读取）
    stable_sources = await stable_mgr.get_stable_sources()
    if stable_sources:
        for ch in ordered_channels:
            name = ch.get('name')
            if name in stable_sources:
                src = stable_sources[name]
                ch['url'] = src['url']
                ch['latency'] = src['latency']
                ch['video_codec'] = src['video_codec']
                ch['is_fixed'] = src.get('is_fixed', False)
        logger.info(f"🔄 稳定源覆盖 {len(stable_sources)} 个频道")

    # 6. 生成输出（实时写入由 Aggregator 负责，这里做最终输出）
    demo_order = parse_demo_order_with_categories() if config.enable_demo_filter else []
    generate_outputs_from_demo(ordered_channels, demo_order)

    # 智能补充采集
    try:
        await collect_and_append_special_categories(Path(config.output_dir), db)
    except Exception as e:
        logger.warning(f"⚠️ 智能补充采集失败: {e}")

    # 7. 自治模式（候选池提升）
    if config.autonomous_mode:
        from src.orchestrator import run_autonomous_mode
        await run_autonomous_mode(skip_discover=True)

    # 8. 实时写入聚合器（如果启用）
    if config.open_realtime_write:
        aggregator = ResultAggregator(ordered_channels, Path(config.output_dir))
        # 此处聚合器已内置，但在测速过程中已经实时写入，这里不再重复

    logger.info("🎉 全部完成！")
    await db.close()
    return 0

if __name__ == "__main__":
    try:
        asyncio.run(run_legacy_mode())
    except KeyboardInterrupt:
        logger.warning("⚠️ 用户中断")
        sys.exit(1)
