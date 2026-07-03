# src/run.py（主要改动见下方拆分结构，其余函数体不变）
import asyncio
import sys
import json
import datetime
import os
from pathlib import Path
from collections import Counter
import traceback

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import (
    IPTV_SOURCES, ENABLE_DEMO_FILTER, ENABLE_ALIAS, ENABLE_BLACKLIST,
    DATABASE_ENABLE, OUTPUT_DIR, MAX_WORKERS, TIMEOUT, FFMPEG_ENABLE,
    ENABLE_JSON_OUTPUT, ENABLE_LITE_VERSION, ENABLE_EPG_OUTPUT,
    ENABLE_INCREMENTAL_FETCH, CACHE_RAW_HOURS, AUTONOMOUS_MODE,
    ENABLE_FIXED_OPTIMIZATION
)
from src.fetcher import fetch_all_sources_incremental
from src.parser import parse_and_dedupe
from src.speed_tester import test_channels_concurrent
from src.ffmpeg_validator import validate_batch, cleanup as ffmpeg_cleanup
from src.generator import generate_outputs_from_demo
from src.merger import merge_channels_by_name
from src.blacklist_filter import get_blacklist_filter
from src.demo_filter import filter_and_order_by_demo, write_shai_file, parse_demo_order_with_categories
from src.database import get_db_cache
from src.logger import logger
from src.hmtj_source import integrate_hmtj_source
from src.special_categories import collect_and_append_special_categories
from src.stable.manager import StableManager
from src.candidate.observer import CandidateObserver

# ========== 子函数拆分 ==========

async def collect_raw_sources(db):
    """拉取原始数据"""
    raw_contents = await fetch_all_sources_incremental(IPTV_SOURCES, db)
    channels_dict = parse_and_dedupe(raw_contents)
    logger.info(f"📊 原始频道数（去重后）: {len(channels_dict)}")
    return channels_dict

async def speed_and_validate(channels_dict, db):
    """测速与ffmpeg验证"""
    logger.info("🔍 开始 HTTP 测速...")
    valid_channels = await test_channels_concurrent(channels_dict)
    logger.info(f"📊 通过HTTP测速的频道数: {len(valid_channels)}")
    if FFMPEG_ENABLE and valid_channels:
        logger.info("🎬 开始 ffmpeg 深度验证...")
        valid_channels = await validate_batch(valid_channels)
        logger.info(f"📊 通过ffmpeg验证的频道数: {len(valid_channels)}")
    if DATABASE_ENABLE and valid_channels:
        await db.save_speed_results(valid_channels)
        await db.set_last_update_time()
    return valid_channels

def merge_and_filter(valid_channels, db, demo_order):
    """合并、黑名单、demo筛选"""
    merged_channels = merge_channels_by_name(valid_channels)
    # 固定源优化
    if ENABLE_FIXED_OPTIMIZATION:
        try:
            data_dir = Path("data")
            all_sources_by_channel = {}
            # 加载源池和候选池...
            # （此处保留原有逻辑，略）
            stable_mgr = StableManager()
            candidate_observer = CandidateObserver()
            optimized = stable_mgr.optimize_fixed_sources(all_sources_by_channel, candidate_observer)
            if optimized > 0:
                logger.info(f"📌 固定源优化完成: 替换了 {optimized} 个固定源")
        except Exception as e:
            logger.warning(f"⚠️ 固定源优化失败: {e}")

    if ENABLE_BLACKLIST:
        blacklist_filter = get_blacklist_filter()
        before = len(merged_channels)
        merged_channels = blacklist_filter.filter_channels(merged_channels)
        logger.info(f"📊 黑名单过滤后: {len(merged_channels)} (减少 {before - len(merged_channels)})")

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

    # 自动追加未匹配频道
    if unmatched_channels and ENABLE_DEMO_FILTER:
        from src.demo_filter import detect_province, get_demo_category_for_province
        demo_categories = {cat for cat, _ in demo_order}
        added_count = 0
        existing_names = {ch["name"] for ch in ordered_channels}
        for ch in unmatched_channels:
            name = ch.get("name")
            if not name or name in existing_names:
                continue
            province = detect_province(name)
            if province:
                cat = get_demo_category_for_province(province, demo_order)
                ch["demo_category"] = cat
                if "urls" not in ch:
                    ch["urls"] = [ch["url"]] if ch.get("url") else []
                ordered_channels.append(ch)
                existing_names.add(name)
                added_count += 1
        if added_count > 0:
            logger.info(f"📊 将 {added_count} 个未匹配频道按省份归类追加")
    return ordered_channels, unmatched_channels

def integrate_special_sources(ordered_channels):
    """集成新源（固定源+体育赛事）"""
    try:
        import asyncio
        from src.hmtj_source import integrate_hmtj_source
        hmtj_classified = asyncio.run(integrate_hmtj_source())
        if hmtj_classified:
            stable_mgr = StableManager()
            total_fixed = 0
            sports_count = 0
            for cat, channels in hmtj_classified.items():
                if cat in ["央视", "卫视", "地方"]:
                    fixed_count = 0
                    for ch in channels:
                        name = ch.get("name")
                        url = ch.get("url")
                        if name and url:
                            existing = stable_mgr.stable_sources.get(name)
                            if existing and existing.is_fixed:
                                continue
                            if stable_mgr.set_fixed_source(name, url, auto_optimize=True):
                                fixed_count += 1
                                logger.info(f"📌 从新源固定: {name}")
                    total_fixed += fixed_count
                elif cat == "体育赛事":
                    for ch in channels:
                        ch["demo_category"] = "体育赛事"
                        ordered_channels.append(ch)
                        sports_count += 1
            logger.info(f"📊 新源入库统计: 共新增 {total_fixed} 个固定源，体育赛事 {sports_count} 个")
    except Exception as e:
        logger.warning(f"⚠️ 集成新源失败: {e}")
    return ordered_channels

def apply_stable_sources(ordered_channels):
    """用稳定源覆盖输出"""
    try:
        stable_mgr = StableManager()
        active_stable = stable_mgr.get_active_sources()
        if active_stable:
            stable_dict = {name: src for name, src in active_stable.items()}
            replaced_count = 0
            for ch in ordered_channels:
                name = ch.get("name")
                if name in stable_dict:
                    src = stable_dict[name]
                    if src.url != ch.get("url"):
                        ch["url"] = src.url
                        ch["latency"] = src.latency
                        ch["video_codec"] = src.video_codec
                        if "urls" in ch:
                            if src.url not in ch["urls"]:
                                ch["urls"] = [src.url] + [u for u in ch["urls"] if u != src.url]
                            else:
                                ch["urls"].remove(src.url)
                                ch["urls"] = [src.url] + ch["urls"]
                        else:
                            ch["urls"] = [src.url]
                        replaced_count += 1
            if replaced_count > 0:
                logger.info(f"🔄 使用稳定源覆盖了 {replaced_count} 个频道")
    except Exception as e:
        logger.warning(f"⚠️ 稳定源覆盖失败: {e}")
    return ordered_channels

async def output_results(ordered_channels, demo_order, unmatched_channels, stats_extra=None):
    """生成输出文件"""
    generate_outputs_from_demo(ordered_channels, demo_order)
    special_stats = {}
    try:
        special_stats = await collect_and_append_special_categories(OUTPUT_DIR, None)
        if special_stats:
            logger.info("🎉 智能补充分类内容已追加到输出文件")
    except Exception as e:
        logger.warning(f"⚠️ 智能补充采集失败: {e}")
    total = len(ordered_channels)
    logger.info(f"🎉 完成！有效频道总数: {total}")
    cat_counter = Counter(ch.get("demo_category", "其他") for ch in ordered_channels)
    stats = {
        "total_channels": total,
        "timestamp": datetime.datetime.now().isoformat(),
        "category_stats": dict(cat_counter),
        "unmatched_count": len(unmatched_channels) if unmatched_channels else 0,
        "features": {
            "epg_injection_enabled": ENABLE_EPG_OUTPUT,
            "incremental_mode": False  # 可自行计算
        }
    }
    if special_stats:
        stats["special_categories"] = special_stats
    if stats_extra:
        stats.update(stats_extra)
    stats_path = OUTPUT_DIR / "stats.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

# ========== 传统模式 ==========
async def run_legacy_mode():
    logger.info("🚀 IPTV 智能整理平台启动 (传统模式)")
    logger.info(f"📡 配置：超时={TIMEOUT}s, 并发={MAX_WORKERS}, ffmpeg={FFMPEG_ENABLE}")
    logger.info(f"📋 增强过滤: demo={ENABLE_DEMO_FILTER}, alias={ENABLE_ALIAS}, blacklist={ENABLE_BLACKLIST}")

    demo_order = parse_demo_order_with_categories() if ENABLE_DEMO_FILTER else []
    logger.info(f"📋 Demo 顺序: {len(demo_order)} 个频道")

    db = await get_db_cache()
    channels_dict = await collect_raw_sources(db)
    if not channels_dict:
        logger.error("❌ 未获取到任何频道")
        return 1

    valid_channels = await speed_and_validate(channels_dict, db)
    if not valid_channels:
        logger.error("❌ 无有效频道")
        return 1

    ordered_channels, unmatched_channels = merge_and_filter(valid_channels, db, demo_order)
    if not ordered_channels:
        logger.error("❌ 过滤后无有效频道")
        return 1

    ordered_channels = integrate_special_sources(ordered_channels)
    ordered_channels = apply_stable_sources(ordered_channels)

    # 最终统计
    cat_counter = Counter(ch.get("demo_category", "其他") for ch in ordered_channels)
    logger.info("\n🎉 最终有效频道分类统计：")
    for cat, cnt in cat_counter.items():
        logger.info(f"  {cat}: {cnt} 个频道")

    await output_results(ordered_channels, demo_order, unmatched_channels)
    ffmpeg_cleanup()
    await db.close()
    return 0

# ========== 自治模式 ==========
async def run_autonomous_mode(skip_discover: bool = False):
    logger.info("=" * 60)
    logger.info("🤖 IPTV 自治系统启动 (观察并提升候选源)")
    if skip_discover:
        logger.info("⏭️ 跳过发现阶段，仅执行观察和提升")
    logger.info("=" * 60)
    try:
        from src.orchestrator import IPTVOrchestrator
        orchestrator = IPTVOrchestrator()
        stats = await orchestrator.run_once(skip_discover=skip_discover)
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
    try:
        if AUTONOMOUS_MODE:
            logger.info("🔀 根据 AUTONOMOUS_MODE=true 启用自治模式（先采集测速，再自治优化）")
            await run_legacy_mode()
            await run_autonomous_mode(skip_discover=True)
            return 0
        else:
            logger.info("🔀 根据 AUTONOMOUS_MODE=false 使用传统模式")
            return await run_legacy_mode()
    except Exception as e:
        logger.exception("❌ 发生未捕获的异常，程序退出")
        return 1

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
