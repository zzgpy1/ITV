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

async def run_once(self, skip_discover: bool = False) -> Dict:
    # 确保候选池数据在数据库中
    db = await get_db_cache()
    # 检查 candidate_pool 表是否有记录
    cursor = await db._conn.execute("SELECT COUNT(*) FROM candidate_pool")
    row = await cursor.fetchone()
    count = row[0] if row else 0
    if count == 0:
        logger.info("📥 候选池数据库为空，从 JSON 导入初始数据...")
        # 从 self.candidate_observer._observations 导入
        for key, obs in self.candidate_observer._observations.items():
            await db._conn.execute(
                '''INSERT OR IGNORE INTO candidate_pool 
                   (channel_key, name, url, discovered_at, last_check, success_count, fail_count, avg_latency, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (obs.source_key, obs.channel_name, obs.url,
                 obs.discovered_at.isoformat(), obs.last_check.isoformat() if obs.last_check else None,
                 obs.success_count, obs.fail_count, obs.avg_latency, obs.status)
            )
        await db._conn.commit()
        logger.info(f"✅ 导入了 {len(self.candidate_observer._observations)} 条候选记录")
        
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

 # 5. 使用稳定源覆盖（从数据库读取）
    stable_sources = await stable_mgr.get_stable_sources()
    if stable_sources:
        # 导入别名匹配器
        from src.alias_matcher import get_alias_matcher
        matcher = get_alias_matcher()
        for ch in ordered_channels:
            raw_name = ch.get('name')
            if not raw_name:
                continue
            # 归一化频道名
            std_name = matcher.normalize(raw_name) if matcher else raw_name
            if std_name in stable_sources:
                src = stable_sources[std_name]
                ch['url'] = src['url']
                ch['latency'] = src['latency']
                ch['video_codec'] = src['video_codec']
                ch['is_fixed'] = src.get('is_fixed', False)
                # 同时更新 urls 列表（如果有）
                if 'urls' in ch and src['url'] not in ch['urls']:
                    ch['urls'] = [src['url']] + [u for u in ch['urls'] if u != src['url']]
        logger.info(f"🔄 稳定源覆盖 {len(stable_sources)} 个频道（匹配后实际覆盖数量见上方）")

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
