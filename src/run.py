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
from src.generator import generate_outputs_from_demo
from src.special_categories import collect_and_append_special_categories
from src.alias_matcher import get_alias_matcher


async def run_legacy_mode():
    logger.info("🚀 IPTV 智能整理平台启动 (传统模式)")
    logger.info(f"📡 配置：超时={config.timeout}s, 并发={config.max_workers}, ffmpeg={config.ffmpeg_enable}")

    # 初始化数据库
    db = await get_db_cache()
    stable_mgr = StableManager()
    
    # ===== 关键修正：先同步固定源（写入数据库） =====
    await stable_mgr.sync_fixed_sources()
    logger.info("📌 固定源已同步到数据库")

    # 1. 获取订阅源列表
    sub_mgr = SubscribeManager()
    subscribe_urls = sub_mgr.get_all_subscribe_urls()
    if subscribe_urls:
        logger.info(f"📋 使用订阅源：{len(subscribe_urls)} 个")
        sources = subscribe_urls
    else:
        sources = config.raw_sources
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

    # 5. 使用稳定源覆盖（但保留固定源优先）
    # 先获取所有稳定源
    all_stable = await stable_mgr.get_stable_sources()
    if all_stable:
        # 获取别名匹配器
        matcher = get_alias_matcher()
        fixed_count = 0
        for ch in ordered_channels:
            raw_name = ch.get('name')
            if not raw_name:
                continue
            # 归一化频道名
            std_name = matcher.normalize(raw_name) if matcher else raw_name
            if std_name in all_stable:
                src = all_stable[std_name]
                # 如果是固定源，强制使用固定源 URL（即使数据库有旧记录）
                if src.get('is_fixed', False):
                    ch['url'] = src['url']
                    ch['latency'] = src.get('latency', 50)
                    ch['video_codec'] = src.get('video_codec', 'h264')
                    ch['is_fixed'] = True
                    if 'urls' in ch:
                        if src['url'] not in ch['urls']:
                            ch['urls'] = [src['url']] + [u for u in ch['urls'] if u != src['url']]
                    fixed_count += 1
                else:
                    # 非固定源可以覆盖（但您的合并逻辑已经处理了）
                    pass
        logger.info(f"🔄 固定源覆盖 {fixed_count} 个频道")

    # 6. 生成输出
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

    logger.info("🎉 全部完成！")
    await db.close()
    return 0


if __name__ == "__main__":
    try:
        asyncio.run(run_legacy_mode())
    except KeyboardInterrupt:
        logger.warning("⚠️ 用户中断")
        sys.exit(1)
