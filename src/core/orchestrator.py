# src/core/orchestrator.py
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
        # 先不创建 SpeedTester，等 init 后
        self.speed_tester = None
        self.stable_manager = StableManager()
        self.quality_monitor = QualityMonitor(self.stable_manager)
        self.generator = OutputGenerator()

    async def run(self, skip_discover=False):
        await repo_factory.init()
        # 现在 repo_factory 已初始化，可以创建 SpeedTester
        self.speed_tester = SpeedTester()
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
        pending = await repo_factory.candidate.get_observing()
        if pending:
            await self.speed_tester.test_batch(pending)

    async def promote_phase(self):
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
