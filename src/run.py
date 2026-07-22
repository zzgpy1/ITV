# src/run.py
import asyncio
import sys
from src.db import db
from src.repository import repo_factory
from src.core.orchestrator import Orchestrator
from src.core.stable_manager import StableManager
from src.services.fetcher import fetch_all_sources
from src.services.parser import parse_and_dedupe
from src.services.speed_tester import probe_channel
from src.services.validator import validate_with_ffprobe
from src.services.merger import merge_channels_by_name  # 原有 merger
from src.services.generator import generate_outputs
from src.settings import settings
from src.logger import logger
from src.demo_filter import filter_and_order_by_demo, parse_demo_order_with_categories
from src.blacklist_filter import get_blacklist_filter
from src.alias_matcher import get_alias_matcher
import aiohttp

async def main():
    logger.info("🚀 IPTV 智能管理平台启动 (重构版)")
    await db.init()
    await repo_factory.init()

    # 同步固定源
    stable_mgr = StableManager()
    await stable_mgr.sync_fixed_sources()

    # 1. 拉取
    sources = settings.iptv_sources
    raw = await fetch_all_sources(sources, force_refresh=False)
    channels_dict = parse_and_dedupe(raw)
    if not channels_dict:
        logger.error("无频道数据")
        return

    # 2. 测速
    valid_channels = []
    sem = asyncio.Semaphore(settings.max_workers)
    async with aiohttp.ClientSession() as session:
        tasks = []
        for ch in channels_dict.values():
            tasks.append(probe_channel(session, ch, repo_factory.candidate, repo_factory.history, repo_factory.cache))
        results = await asyncio.gather(*tasks)
        for ch, latency, ok in results:
            if ok:
                ch["latency"] = latency
                valid_channels.append(ch)

    # 3. ffmpeg 验证（若启用）
    if settings.ffmpeg_enable and valid_channels:
        valid_channels = await validate_with_ffprobe(valid_channels, repo_factory.cache)

    # 4. 合并
    merged = merge_channels_by_name(valid_channels)

    # 5. 黑名单过滤
    if settings.enable_blacklist:
        blacklist = get_blacklist_filter()
        merged = blacklist.filter_channels(merged)

    # 6. demo 筛选
    demo_order = parse_demo_order_with_categories() if settings.enable_demo_filter else []
    if settings.enable_demo_filter and demo_order:
        ordered, _ = filter_and_order_by_demo(merged)
    else:
        ordered = merged

    # 7. 生成输出
    await generate_outputs(ordered)

    # 8. 运行自治模式（后台）
    if settings.autonomous_mode:
        orch = Orchestrator()
        await orch.run()

    logger.info("🎉 完成")
    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
