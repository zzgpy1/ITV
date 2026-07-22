# src/core/orchestrator.py
import asyncio
from src.repository import repo_factory
from src.services.fetcher import fetch_all_sources
from src.services.parser import parse_and_dedupe
from src.services.speed_tester import probe_channel
from src.services.validator import validate_with_ffprobe
from src.core.stable_manager import StableManager
from src.core.quality_monitor import QualityMonitor
from src.settings import settings
from src.logger import logger
from src.deduplicator import channel_key
import aiohttp

class Orchestrator:
    def __init__(self):
        self.stable_manager = StableManager()
        self.quality_monitor = QualityMonitor(self.stable_manager)

    async def run(self):
        logger.info("🚀 启动自治模式")
        await repo_factory.init()
        await self.discover()
        await self.observe()
        await self.promote()
        await self.quality_check()

    async def discover(self):
        logger.info("阶段1: 发现新源")
        sources = settings.iptv_sources
        raw = await fetch_all_sources(sources, force_refresh=True)
        channels_dict = parse_and_dedupe(raw)
        count = 0
        for ch in channels_dict.values():
            key = channel_key(ch["name"], ch["url"])
            await repo_factory.source.add(key, ch["name"], ch["url"], ch.get("source_url", ""))
            # 同时加入候选池
            await repo_factory.candidate.add(key, ch["name"], ch["url"])
            count += 1
        logger.info(f"发现 {count} 个新源加入候选池")

    async def observe(self):
        logger.info("阶段2: 观察候选源")
        pending = await repo_factory.candidate.get_observing(limit=2000)
        if not pending:
            logger.info("无待观察候选源")
            return
        sem = asyncio.Semaphore(settings.max_workers)
        async with aiohttp.ClientSession() as session:
            async def observe_one(item):
                async with sem:
                    ch = {"name": item["channel_name"], "url": item["url"]}
                    _, latency, ok = await probe_channel(
                        session, ch,
                        repo_factory.candidate,
                        repo_factory.history,
                        repo_factory.cache
                    )
                    if ok and latency < settings.candidate_max_latency:
                        # 检查是否达到稳定标准
                        # 简单实现：查询该候选的统计
                        # 更严谨：我们在此处只做测速，判断由后续promote决定
                        # 但我们可以在测速后直接更新状态？为了分离，我们只在promote阶段判断
                        pass
            tasks = [observe_one(item) for item in pending]
            await asyncio.gather(*tasks)
        logger.info(f"观察完成，共 {len(pending)} 个候选")

    async def promote(self):
        logger.info("阶段3: 提升稳定源")
        # 从候选池获取 stable 状态的源（由之前观察后标记）
        stable_candidates = await repo_factory.candidate.get_stable_candidates()
        promoted = 0
        for cand in stable_candidates:
            # 检查是否满足条件（在观察阶段已更新统计）
            if cand["success_count"] >= settings.candidate_min_success and \
               cand["avg_latency"] <= settings.candidate_max_latency and \
               cand["success_count"] / (cand["success_count"] + cand["fail_count"]) >= settings.candidate_min_success_rate:
                # 检查是否已存在稳定源且质量更好
                existing = await repo_factory.stable.get(cand["channel_name"])
                if existing and existing["latency"] < cand["avg_latency"]:
                    continue
                # 提升
                await repo_factory.stable.upsert(
                    cand["channel_name"], cand["url"], cand["avg_latency"],
                    "", is_fixed=False, auto_optimize=True
                )
                await repo_factory.candidate.promote(cand["source_key"])
                promoted += 1
                logger.info(f"提升稳定源: {cand['channel_name']}")
        logger.info(f"提升 {promoted} 个稳定源")

    async def quality_check(self):
        logger.info("阶段4: 质量检查")
        active = await repo_factory.stable.get_active()
        for src in active:
            # 简单检查：若最近失败次数超过3，则尝试替换
            if src["fail_count"] >= 3 and not src["is_fixed"]:
                # 寻找候选池中同名的稳定候选
                candidates = await repo_factory.candidate.get_stable_candidates()
                best = None
                for cand in candidates:
                    if cand["channel_name"] == src["channel_name"] and cand["avg_latency"] < src["latency"]:
                        if best is None or cand["avg_latency"] < best["avg_latency"]:
                            best = cand
                if best:
                    await repo_factory.stable.replace_source(
                        src["channel_name"], best["url"], best["avg_latency"], ""
                    )
                    await repo_factory.candidate.promote(best["source_key"])
                    logger.info(f"替换劣质源: {src['channel_name']}")
