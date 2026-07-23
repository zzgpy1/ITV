# src/core/orchestrator.py
import asyncio
from src.settings import settings
from src.repositories import repo_factory
from src.discoverers.source_discoverer import SourceDiscoverer
from src.core.speed_tester import SpeedTester
from src.stable.manager import StableManager
from src.quality.monitor import QualityMonitor
from src.generator import OutputGenerator
from src.demo_filter import parse_demo_order, filter_and_order_by_demo
from src.merger import merge_channels_by_name
from src.blacklist_filter import get_blacklist_filter
from src.logger import logger

class Orchestrator:
    def __init__(self):
        self.discoverer = SourceDiscoverer()
        self.speed_tester = SpeedTester()
        self.stable_manager = StableManager()
        self.quality_monitor = QualityMonitor(self.stable_manager)
        self.generator = OutputGenerator()

    async def run(self, skip_discover=False):
        await repo_factory.init()
        await self.stable_manager.init()

        if not skip_discover:
            await self.discover_phase()
        await self.observe_phase()
        await self.promote_phase()
        await self.quality_check_phase()
        await self.generate_output_phase()

    async def discover_phase(self):
        sources = await self.discoverer.discover()
        for src in sources:
            await repo_factory.source.add(src["key"], src["name"], src["url"], src["source_url"])
            await repo_factory.candidate.add(src["key"], src["name"], src["url"])

    async def observe_phase(self):
        logger.info("📊 观察候选源...")
        # 获取已有稳定源
        stable = await repo_factory.stable.get_all()
        stable_names = set(stable.keys())

        # 只取那些还没有稳定源的频道
        pending = await repo_factory.candidate.get_observing(limit=5000)
        pending_by_channel = {}
        for p in pending:
            name = p["name"]
            if name not in stable_names:
                pending_by_channel.setdefault(name, []).append(p)

        # 限制总数：最多 1000 个候选，每个频道最多取 3 个
        max_batch = 1000
        to_test = []
        for name, sources in pending_by_channel.items():
            to_test.extend(sources[:3])
            if len(to_test) >= max_batch:
                break

        if not to_test:
            logger.info("没有需要观察的候选源（或已有稳定源）")
            return

        logger.info(f"本次观察 {len(to_test)} 个候选源（覆盖 {len(pending_by_channel)} 个频道）")
        await self.speed_tester.test_batch(to_test)

    async def promote_phase(self):
        logger.info("⬆️ 提升稳定源...")
        stable_candidates = await repo_factory.candidate.get_stable_candidates()
        for cand in stable_candidates:
            existing = await repo_factory.stable.get(cand["name"])
            if existing and existing["is_fixed"]:
                continue
            if existing and existing["latency"] < cand["latency"]:
                continue
            await repo_factory.stable.upsert(cand["name"], cand["url"], cand["latency"])
            await repo_factory.candidate.promote(cand["key"])
            logger.info(f"✅ 提升: {cand['name']}")

    async def quality_check_phase(self):
        logger.info("🔎 质量检查...")
        await self.quality_monitor.check_all_active_sources()
        if settings.auto_replace_failed:
            critical = self.quality_monitor.get_critical_sources()
            for name in critical:
                candidates = await repo_factory.candidate.get_stable_candidates()
                better = [c for c in candidates if c["name"] == name]
                if better:
                    await repo_factory.stable.upsert(name, better[0]["url"], better[0]["latency"])
                    logger.info(f"🔄 替换失效源: {name}")

    async def generate_output_phase(self):
        stable = await repo_factory.stable.get_all()
        if not stable:
            logger.warning("无稳定源，跳过输出")
            return
        channels = [{"name": k, "url": v["url"], "latency": v["latency"]} for k, v in stable.items()]
        merged = merge_channels_by_name(channels)
        if settings.enable_blacklist:
            bl = get_blacklist_filter()
            merged = bl.filter_channels(merged)
        demo_order = parse_demo_order() if settings.enable_demo_filter else []
        if demo_order:
            ordered, _ = filter_and_order_by_demo(merged)
        else:
            ordered = merged
        self.generator.generate_all(ordered, demo_order)
