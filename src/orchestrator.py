import asyncio
from datetime import datetime
from src.logger import logger
from src.settings import settings
from src.database import db
from src.repositories import repo_factory
from src.services.fetcher import fetch_all_sources
from src.services.parser import parse_and_dedupe
from src.services.speed_tester import test_channels_concurrent
from src.services.ffmpeg_validator import validate_batch
from src.services.merger import merge_channels_by_name
from src.services.demo_filter import filter_and_order_by_demo, parse_demo_order_with_categories
from src.services.generator import generate_outputs_from_demo
from src.stable_manager import StableManager
from src.candidate_observer import CandidateObserver
from src.quality_monitor import QualityMonitor
from src.models import Source, StableSource

class Orchestrator:
    def __init__(self):
        self.stable_mgr = StableManager()
        self.candidate_obs = CandidateObserver()
        self.quality_mon = QualityMonitor()

    async def run(self, skip_discover=False):
        logger.info("🚀 自治模式启动")
        await db.init()
        if not skip_discover:
            await self.discover_phase()
        await self.observe_phase()
        # 不再需要独立的提升阶段，已合并到观察中
        await self.quality_phase()
        await self.generate_output()
        logger.info("✅ 自治模式完成")

    async def discover_phase(self):
        logger.info("📡 发现阶段：拉取订阅源...")
        sources = await self._get_sources()
        raw_contents = await fetch_all_sources(sources)
        channels_dict = parse_and_dedupe(raw_contents)
        for ch in channels_dict.values():
            src = Source(
                channel_name=ch['name'],
                url=ch['url'],
                source_url=ch.get('source_url', 'unknown'),
                status='pending'
            )
            await repo_factory.source_repo.add(src)
        logger.info(f"✅ 发现阶段完成，新增 {len(channels_dict)} 个频道")

    async def observe_phase(self):
        logger.info("🔍 观察阶段：从缓存测速候选源...")
        pending = await repo_factory.source_repo.get_pending(limit=5000)
        if not pending:
            logger.info("📭 无待测速源")
            return
        channels = [{"name": s.channel_name, "url": s.url} for s in pending]
        valid = await test_channels_concurrent(channels)
        # 更新 source_pool 状态
        for ch in valid:
            key = Source(channel_name=ch['name'], url=ch['url'], source_url='').get_key()
            await repo_factory.source_repo.update_status(key, 'verified', latency=ch.get('latency', 0), success=True)
        
        # 直接提升为稳定源（跳过候选池评估）
        promoted = 0
        for ch in valid:
            # 检查是否已存在稳定源，若存在且固定则跳过
            existing = await repo_factory.stable_repo.get(ch['name'])
            if existing and existing.is_fixed:
                continue
            stable = StableSource(
                channel_name=ch['name'],
                url=ch['url'],
                latency=ch.get('latency', 0),
                video_codec='',
                is_fixed=False,
                auto_optimize=False,
                promoted_at=datetime.now()
            )
            await repo_factory.stable_repo.upsert(stable)
            promoted += 1
        logger.info(f"✅ 观察阶段完成，{len(valid)} 个源通过测速，{promoted} 个被提升为稳定源")

    async def quality_phase(self):
        logger.info("📊 质量检查阶段...")
        stables = await repo_factory.stable_repo.get_all()
        for stable in stables:
            ok, latency = await self.quality_mon.check_channel(stable.channel_name, stable.url)
            if ok:
                if stable.fail_count > 0:
                    await repo_factory.stable_repo.update_fail_count(stable.channel_name, 0, 'active')
            else:
                new_fail = stable.fail_count + 1
                status = 'degraded' if new_fail < 3 else 'failed'
                await repo_factory.stable_repo.update_fail_count(stable.channel_name, new_fail, status)
                if status == 'failed' and settings.auto_replace_failed:
                    await self._replace_failed(stable.channel_name)
        logger.info("✅ 质量检查完成")

    async def _replace_failed(self, channel_name: str):
        # 简单替换：从所有稳定源中找同名的最佳（但这里只简单处理）
        stables = await repo_factory.stable_repo.get_all()
        best = None
        for s in stables:
            if s.channel_name == channel_name and s.status != 'failed':
                if best is None or s.latency < best.latency:
                    best = s
        if best:
            stable = StableSource(
                channel_name=channel_name,
                url=best.url,
                latency=best.latency,
                video_codec='',
                is_fixed=False,
                auto_optimize=False,
                promoted_at=datetime.now()
            )
            await repo_factory.stable_repo.upsert(stable)
            logger.info(f"🔄 已替换失败源 {channel_name}")

    async def generate_output(self):
        logger.info("📝 生成输出文件...")
        stables = await repo_factory.stable_repo.get_all()
        channels = [{"name": s.channel_name, "url": s.url, "latency": s.latency} for s in stables if s.status != 'failed']
        if not channels:
            logger.warning("无稳定源，跳过输出")
            return
        demo_order = parse_demo_order_with_categories() if settings.enable_demo_filter else []
        ordered, _ = filter_and_order_by_demo(channels)
        generate_outputs_from_demo(ordered, demo_order)
        logger.info("✅ 输出生成完成")

    async def _get_sources(self):
        from src.subscribe_manager import SubscribeManager
        mgr = SubscribeManager()
        urls = mgr.get_all_subscribe_urls()
        if urls:
            return urls
        return settings.raw_sources + settings.direct_sources
