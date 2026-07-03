#!/usr/bin/env python3
# src/run.py

import asyncio
import sys
import json
import datetime
import os
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import (
    IPTV_SOURCES,
    ENABLE_DEMO_FILTER,
    ENABLE_ALIAS,
    ENABLE_BLACKLIST,
    DATABASE_ENABLE,
    OUTPUT_DIR,
    MAX_WORKERS,
    TIMEOUT,
    FFMPEG_ENABLE,
    ENABLE_JSON_OUTPUT,
    ENABLE_LITE_VERSION,
    ENABLE_EPG_OUTPUT,
    ENABLE_INCREMENTAL_FETCH,
    CACHE_RAW_HOURS,
    AUTONOMOUS_MODE,
)
from src.fetcher import fetch_all_sources_incremental
from src.parser import parse_and_dedupe
from src.speed_tester import test_channels_concurrent
from src.ffmpeg_validator import validate_batch, cleanup as ffmpeg_cleanup
from src.generator import generate_outputs_from_demo
from src.merger import merge_channels_by_name
from src.blacklist_filter import get_blacklist_filter
from src.demo_filter import (
    filter_and_order_by_demo,
    write_shai_file,
    parse_demo_order_with_categories,
)
from src.database import get_db_cache
from src.logger import logger

# 新增：新源集成
from src.hmtj_source import integrate_hmtj_source

# 新增：智能补充采集（abc123 源）
from src.special_categories import collect_and_append_special_categories

# 增强输出
from src.generator_enhanced import EnhancedOutputGenerator

# ========== 注意：已移除 iptv_org_adapter、global_channels、overseas_filter ==========


# ========== 传统模式 ==========
async def run_legacy_mode():
    logger.info("🚀 IPTV 智能整理平台启动 (传统模式)")
    logger.info(f"📡 配置：超时={TIMEOUT}s, 并发={MAX_WORKERS}, ffmpeg={FFMPEG_ENABLE}")
    logger.info(
        f"📋 增强过滤: demo={ENABLE_DEMO_FILTER}, alias={ENABLE_ALIAS}, blacklist={ENABLE_BLACKLIST}"
    )

    demo_order = parse_demo_order_with_categories() if ENABLE_DEMO_FILTER else []
    logger.info(f"📋 Demo 顺序: {len(demo_order)} 个频道")

    db = await get_db_cache()

    # 增量更新
    raw_contents = {}
    last_update = await db.get_last_update_time() if DATABASE_ENABLE else None
    is_fresh = last_update and (datetime.datetime.now().timestamp() - last_update) < CACHE_RAW_HOURS * 3600

    if is_fresh and ENABLE_INCREMENTAL_FETCH:
        logger.info("⚡ 启用增量更新模式（缓存有效）")
        for url in IPTV_SOURCES:
            cached = await db.get_raw_source(url)
            if cached:
                raw_contents[url] = cached
            else:
                logger.info(f"🔄 缓存未命中，拉取: {url}")
                fetched = await fetch_all_sources_incremental([url], db)
                raw_contents.update(fetched)
    else:
        if last_update:
            logger.info(f"📊 缓存已过期，执行完整采集")
        else:
            logger.info("📊 首次运行，执行完整采集")
        raw_contents = await fetch_all_sources_incremental(IPTV_SOURCES, db)

    channels_dict = parse_and_dedupe(raw_contents)
    if not channels_dict:
        logger.error("❌ 未获取到任何频道")
        return 1

    logger.info(f"📊 原始频道数（去重后）: {len(channels_dict)}")

    # HTTP 测速
    logger.info("🔍 开始 HTTP 测速...")
    valid_channels = await test_channels_concurrent(channels_dict)
    logger.info(f"📊 通过HTTP测速的频道数: {len(valid_channels)}")

    # ffmpeg 验证
    if FFMPEG_ENABLE and valid_channels:
        logger.info("🎬 开始 ffmpeg 深度验证...")
        valid_channels = await validate_batch(valid_channels)
        logger.info(f"📊 通过ffmpeg验证的频道数: {len(valid_channels)}")

    if DATABASE_ENABLE and valid_channels:
        await db.save_speed_results(valid_channels)
        await db.set_last_update_time()

    merged_channels = merge_channels_by_name(valid_channels)
    logger.info(f"📊 合并后的频道数: {len(merged_channels)}")

    if ENABLE_BLACKLIST:
        blacklist_filter = get_blacklist_filter()
        before = len(merged_channels)
        merged_channels = blacklist_filter.filter_channels(merged_channels)
        logger.info(f"📊 黑名单过滤后: {len(merged_channels)} (减少 {before - len(merged_channels)})")

    # Demo 筛选
    unmatched_channels = []
    if ENABLE_DEMO_FILTER:
        before = len(merged_channels)
        ordered_channels, unmatched_channels = filter_and_order_by_demo(merged_channels)
        logger.info(f"📊 Demo筛选后: {len(ordered_channels)} (减少 {before - len(ordered_channels)})")
        if unmatched_channels:
            write_shai_file(unmatched_channels, len(ordered_channels), before)
        if not ordered_channels:
            logger.warning("❌ Demo 筛选后无频道，尝试不筛选")
            ordered_channels = merged_channels
    else:
        ordered_channels = merged_channels

    if not ordered_channels:
        logger.error("❌ 过滤后无有效频道")
        return 1

    # ===== 集成新源：央视/卫视/地方存入稳定源，体育赛事追加输出 =====
    try:
        from src.hmtj_source import integrate_hmtj_source
        from src.stable.manager import StableManager
        hmtj_classified = await integrate_hmtj_source()
        if hmtj_classified:
            stable_mgr = StableManager()
            for cat, channels in hmtj_classified.items():
                if cat in ["央视", "卫视", "地方"]:
                    # 将这些频道作为固定源存入稳定源
                    fixed_count = 0
                    for ch in channels:
                        name = ch.get("name")
                        url = ch.get("url")
                        if name and url:
                            # 检查是否已存在固定源（防止覆盖用户手动添加的）
                            existing = stable_mgr.stable_sources.get(name)
                            if existing and existing.is_fixed:
                                logger.debug(f"⏭️ {name} 已是固定源，跳过")
                                continue
                            # 设置为固定源
                            if stable_mgr.set_fixed_source(name, url):
                                fixed_count += 1
                                logger.info(f"📌 从新源固定: {name}")
                    logger.info(f"📌 新源贡献固定源: {fixed_count} 个")
                elif cat == "体育赛事":
                    # 体育赛事追加到输出
                    for ch in channels:
                        ch["demo_category"] = cat
                        ordered_channels.append(ch)
                    logger.info(f"🌐 从新源追加 {len(channels)} 个体育赛事频道")
    except Exception as e:
        logger.warning(f"⚠️ 集成新源失败: {e}")

    # 最终分类统计
    cat_counter = Counter(ch.get("demo_category", "其他") for ch in ordered_channels)
    logger.info("\n🎉 最终有效频道分类统计：")
    for cat, cnt in cat_counter.items():
        logger.info(f"  {cat}: {cnt} 个频道")

    # 生成输出
    generate_outputs_from_demo(ordered_channels, demo_order)

    output_gen = EnhancedOutputGenerator()
    output_gen.generate_all_outputs(
        ordered_channels,
        demo_order,
        enable_json=ENABLE_JSON_OUTPUT,
        enable_lite=ENABLE_LITE_VERSION,
        enable_epg=ENABLE_EPG_OUTPUT
    )

    # 智能补充采集
    special_stats = {}
    try:
        special_stats = await collect_and_append_special_categories(OUTPUT_DIR, db)
        if special_stats:
            logger.info("🎉 智能补充分类内容已追加到输出文件")
    except Exception as e:
        logger.warning(f"⚠️ 智能补充采集失败: {e}")

    total = len(ordered_channels)
    logger.info(f"🎉 完成！有效频道总数: {total}")

    # 保存统计
    stats = {
        "total_channels": total,
        "timestamp": datetime.datetime.now().isoformat(),
        "category_stats": dict(cat_counter),
        "unmatched_count": len(unmatched_channels) if unmatched_channels else 0,
        "features": {
            "epg_injection_enabled": ENABLE_EPG_OUTPUT,
            "incremental_mode": is_fresh and ENABLE_INCREMENTAL_FETCH
        }
    }
    if special_stats:
        stats["special_categories"] = special_stats

    stats_path = OUTPUT_DIR / "stats.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    ffmpeg_cleanup()
    await db.close()
    return 0


# ========== 自治模式 ==========
async def run_autonomous_mode():
    logger.info("=" * 60)
    logger.info("🤖 IPTV 自治系统启动 (发现新源)")
    logger.info("=" * 60)
    try:
        from src.orchestrator import IPTVOrchestrator
        orchestrator = IPTVOrchestrator()
        stats = await orchestrator.run_once()
        new_stable_count = stats.get("new_stable_count", 0)
        logger.info("=" * 60)
        logger.info(f"📊 自治模式完成: 新提升 {new_stable_count} 个稳定源")
        return stats
    except ImportError as e:
        logger.warning(f"⚠️ 自治模式模块未找到: {e}")
        return {}
    except Exception as e:
        logger.warning(f"⚠️ 自治模式运行失败: {e}")
        return {}


# ========== 主入口 ==========
async def main():
    if AUTONOMOUS_MODE:
        logger.info("🔀 根据 AUTONOMOUS_MODE=true 启用自治模式")
        logger.info("📌 自治模式将先发现新源，然后执行传统模式完整采集")
        await run_autonomous_mode()
        logger.info("=" * 60)
        logger.info("🔄 执行传统模式完整采集...")
        logger.info("=" * 60)
        return await run_legacy_mode()
    else:
        logger.info("🔀 根据 AUTONOMOUS_MODE=false 使用传统模式")
        return await run_legacy_mode()


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.warning("\n⚠️ 用户中断")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"❌ 发生错误: {e}")
        sys.exit(1)
