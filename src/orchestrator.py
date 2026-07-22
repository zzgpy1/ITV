import asyncio
from datetime import datetime
from src.logger import logger
from src.settings import settings
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
from src.models import Source, Candidate

class Orchestrator:
    def __init__(self):
        self.stable_mgr = StableManager()
        self.candidate_obs = CandidateObserver()
        self.quality_mon = QualityMonitor()

    async def run(self, skip_discover=False):
        logger.info("🚀 自治模式启动")
        await db.init()  # 确保数据库初始化
        if not skip_discover:
            await self.discover_phase()
        await self.observe_phase()
        await self.promote_phase()
        await self.quality_phase()
        await self.generate_output()
        logger.info("✅ 自治模式完成")

    async def discover_phase(self):
        logger.info("📡 发现阶段：拉取订阅源...")
        sources = await self._get_sources()
        raw_contents = await fetch_all_sources(sources)
        channels_dict = parse_and_dedupe(raw_contents)
        # 将新频道加入 source_pool
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
        # 转换为测速格式
        channels = [{"name": s.channel_name, "url": s.url} for s in pending]
        # 执行测速（结果写入 candidate_pool）
        valid = await test_channels_concurrent(channels)
        # 更新 source_pool 状态
        for ch in valid:
            key = Source(channel_name=ch['name'], url=ch['url'], source_url='').get_key()
            await repo_factory.source_repo.update_status(key, 'verified', latency=ch.get('latency', 0), success=True)
        logger.info(f"✅ 观察阶段完成，{len(valid)} 个源通过测速")

    async def promote_phase(self):
        logger.info("📌 提升阶段：将稳定候选提升为稳定源...")
        stable_candidates = await repo_factory.candidate_repo.get_stable_candidates()
        promoted = 0
        for cand in stable_candidates:
            # 检查是否存在固定源
            existing = await repo_factory.stable_repo.get(cand.channel_name)
            if existing and existing.is_fixed:
                continue
            if existing and existing.latency < cand.avg_latency:
                continue
            # 提升
            stable = StableSource(
                channel_name=cand.channel_name,
                url=cand.url,
                latency=cand.avg_latency,
                video_codec='',
                is_fixed=False,
                auto_optimize=False,
                promoted_at=datetime.now()
            )
            await repo_factory.stable_repo.upsert(stable)
            # 更新候选状态
            await repo_factory.candidate_repo.update_status(cand.source_key, 'promoted', datetime.now())
            promoted += 1
        logger.info(f"✅ 提升阶段完成，{promoted} 个源成为稳定源")

    async def quality_phase(self):
        logger.info("📊 质量检查阶段...")
        # 检查所有稳定源
        stables = await repo_factory.stable_repo.get_all()
        for stable in stables:
            # 简化的检查：使用快速探测
            ok, latency = await self.quality_mon.check_channel(stable.channel_name, stable.url)
            if ok:
                # 重置失败计数
                if stable.fail_count > 0:
                    await repo_factory.stable_repo.update_fail_count(stable.channel_name, 0, 'active')
            else:
                new_fail = stable.fail_count + 1
                status = 'degraded' if new_fail < 3 else 'failed'
                await repo_factory.stable_repo.update_fail_count(stable.channel_name, new_fail, status)
                if status == 'failed' and settings.auto_replace_failed:
                    # 从候选池寻找替代
                    await self._replace_failed(stable.channel_name)
        logger.info("✅ 质量检查完成")

    async def _replace_failed(self, channel_name: str):
        # 查找候选池中该频道的最佳替代
        candidates = await repo_factory.candidate_repo.get_stable_candidates()
        best = None
        for c in candidates:
            if c.channel_name == channel_name and c.status == 'stable':
                if best is None or c.avg_latency < best.avg_latency:
                    best = c
        if best:
            stable = StableSource(
                channel_name=channel_name,
                url=best.url,
                latency=best.avg_latency,
                video_codec='',
                is_fixed=False,
                auto_optimize=False,
                promoted_at=datetime.now()
            )
            await repo_factory.stable_repo.upsert(stable)
            logger.info(f"🔄 已替换失败源 {channel_name} -> {best.url[:50]}...")
        else:
            logger.warning(f"⚠️ 未找到 {channel_name} 的替代源")

    async def generate_output(self):
        logger.info("📝 生成输出文件...")
        stables = await repo_factory.stable_repo.get_all()
        channels = [{"name": s.channel_name, "url": s.url, "latency": s.latency} for s in stables if s.status != 'failed']
        demo_order = parse_demo_order_with_categories() if settings.enable_demo_filter else []
        ordered, _ = filter_and_order_by_demo(channels)
        generate_outputs_from_demo(ordered, demo_order)
        logger.info("✅ 输出生成完成")

    async def _get_sources(self):
        # 从 subscribe.txt 读取
        from src.subscribe_manager import SubscribeManager
        mgr = SubscribeManager()
        urls = mgr.get_all_subscribe_urls()
        if urls:
            return urls
        return settings.raw_sources + settings.direct_sources
