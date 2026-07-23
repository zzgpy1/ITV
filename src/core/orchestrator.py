# src/core/orchestrator.py
from src.settings import settings
from src.repositories import repo_factory
from src.discoverers.source_discoverer import SourceDiscoverer
from src.observers.candidate_observer import CandidateObserver
from src.speed_tester import SpeedTester
from src.ffmpeg_validator import validate_batch
from src.stable.manager import StableManager
from src.quality.monitor import QualityMonitor
from src.merger import merge_channels_by_name
from src.blacklist_filter import get_blacklist_filter
from src.demo_filter import filter_and_order_by_demo, parse_demo_order_with_categories
from src.generator import OutputGenerator
from src.logger import logger


class Orchestrator:
    def __init__(self):
        self.discoverer = SourceDiscoverer()
        self.observer = CandidateObserver()
        self.speed_tester = SpeedTester()
        self.stable_manager = StableManager()
        self.quality_monitor = QualityMonitor()
        self.generator = OutputGenerator()
        self.stats = {}

    async def run(self, skip_discover: bool = False):
        logger.info("=" * 50)
        logger.info("🚀 IPTV 智能管理平台启动")
        logger.info("=" * 50)

        # 初始化数据库
        await repo_factory.init()
        await self.stable_manager.init()

        try:
            # ===== 阶段1: 采集 =====
            logger.info("📡 阶段1: 采集")
            if not skip_discover:
                sources = await self.discoverer.discover()
                if sources:
                    for src in sources:
                        await repo_factory.source.add(
                            src["key"], src["name"], src["url"], src["source_url"]
                        )
                        await repo_factory.candidate.add(src["key"], src["name"], src["url"])
                    logger.info(f"✅ 采集完成: {len(sources)} 个频道加入候选池")
                else:
                    logger.warning("⚠️ 未发现任何频道")
            else:
                logger.info("⏭️ 跳过发现阶段")

            # ===== 阶段2: 测速 =====
            logger.info("🚀 阶段2: 测速")
            pending = await repo_factory.source.get_pending(limit=3000)
            if pending:
                logger.info(f"🔍 测速 {len(pending)} 个待验证源")
                valid = await self.speed_tester.test_batch(pending, source_mode=True)
                if valid:
                    logger.info(f"✅ 测速通过: {len(valid)} 个频道")
                else:
                    logger.warning("⚠️ 测速未通过任何频道")
            else:
                logger.info("📭 没有待验证的源")

            # ===== 阶段3: ffmpeg 深度验证 =====
            if settings.ffmpeg_enable:
                logger.info("🎬 阶段3: ffmpeg 深度验证")
                rows = await repo_factory.source._fetchall(
                    "SELECT source_key, channel_name, url FROM source_pool WHERE status = 'verified' LIMIT 500"
                )
                if rows:
                    channels = [{"key": r[0], "name": r[1], "url": r[2]} for r in rows]
                    validated = await validate_batch(channels)
                    logger.info(f"✅ ffmpeg 验证通过: {len(validated)} 个频道")
                else:
                    logger.info("📭 没有需要深度验证的频道")

            # ===== 阶段4: 观察候选池 =====
            logger.info("🔍 阶段4: 观察候选池")
            await self.observer.observe()

            # ===== 阶段5: 提升稳定源 =====
            logger.info("⬆️ 阶段5: 提升稳定源")
            stable_candidates = await repo_factory.candidate.get_stable_candidates()
            promoted = 0
            if stable_candidates:
                for cand in stable_candidates:
                    existing = await repo_factory.stable.get(cand["name"])
                    if existing and existing.get("is_fixed", False):
                        continue
                    if existing and existing.get("latency", 9999) < cand.get("latency", 9999):
                        continue
                    if await self.stable_manager.promote_candidate(
                        cand["name"], cand["url"], cand.get("latency", 0), "h264"
                    ):
                        await repo_factory.candidate.promote(cand["key"])
                        promoted += 1
                logger.info(f"✅ 提升完成: {promoted} 个稳定源")
            else:
                logger.info("📭 没有稳定的候选源")

            # ===== 阶段6: 质量检查 =====
            if settings.auto_replace_failed:
                logger.info("🔎 阶段6: 质量检查")
                await self.quality_monitor.check_all_active_sources()

            # ===== 阶段7: 生成输出 =====
            logger.info("📁 阶段7: 生成输出")
            await self._generate_output()

        except Exception as e:
            logger.error(f"❌ 运行失败: {e}")
            import traceback
            traceback.print_exc()
            raise

        # ===== 统计 =====
        logger.info("=" * 50)
        logger.info("📊 运行统计")
        logger.info("=" * 50)
        try:
            source_stats = await repo_factory.source._fetchall(
                "SELECT status, COUNT(*) FROM source_pool GROUP BY status"
            )
            for row in source_stats:
                logger.info(f"  源池 {row[0]}: {row[1]}")
        except Exception:
            pass

        try:
            candidate_stats = await repo_factory.candidate._fetchall(
                "SELECT status, COUNT(*) FROM candidate_pool GROUP BY status"
            )
            for row in candidate_stats:
                logger.info(f"  候选池 {row[0]}: {row[1]}")
        except Exception:
            pass

        stable_all = await repo_factory.stable.get_all()
        fixed_count = sum(1 for s in stable_all.values() if s.get("is_fixed", False))
        logger.info(f"  稳定源总数: {len(stable_all)} (固定源: {fixed_count})")
        logger.info("=" * 50)
        logger.info("🎉 全部完成!")

        await repo_factory.close()

    async def _generate_output(self):
        """生成输出文件 - 从稳定源和候选池合并数据"""
        stable = await repo_factory.stable.get_all()
        channels = []

        # 1. 收集稳定源
        if stable:
            for name, info in stable.items():
                url = info.get("url")
                if url:
                    channels.append({
                        "name": name,
                        "url": url,
                        "latency": info.get("latency", 9999),
                        "video_codec": info.get("video_codec", ""),
                        "is_fixed": info.get("is_fixed", False)
                    })
            logger.info(f"📊 从稳定源获取: {len(channels)} 个频道")

        # 2. 如果稳定源太少，从候选池补充
        if len(channels) < 30:
            logger.info(f"📊 稳定源数量较少 ({len(channels)})，从候选池补充...")
            existing_names = {c["name"] for c in channels}

            # 获取候选池中稳定的或观察中的源
            rows = await repo_factory.candidate._fetchall(
                "SELECT source_key, channel_name, url, avg_latency FROM candidate_pool WHERE status IN ('stable', 'observing') LIMIT 500"
            )

            added = 0
            for row in rows:
                name = row[1]
                if name not in existing_names:
                    channels.append({
                        "name": name,
                        "url": row[2],
                        "latency": row[3] or 9999,
                        "video_codec": "h264",
                        "is_fixed": False
                    })
                    existing_names.add(name)
                    added += 1

            if added > 0:
                logger.info(f"✅ 从候选池补充: {added} 个频道")
                logger.info(f"📊 补充后总数: {len(channels)} 个频道")

        # 3. 如果还是太少，从源池获取
        if len(channels) < 30:
            logger.info(f"📊 频道数量仍然较少 ({len(channels)})，从源池获取已验证的源...")
            existing_names = {c["name"] for c in channels}

            rows = await repo_factory.source._fetchall(
                "SELECT source_key, channel_name, url FROM source_pool WHERE status = 'verified' LIMIT 200"
            )

            added = 0
            for row in rows:
                name = row[1]
                if name not in existing_names:
                    channels.append({
                        "name": name,
                        "url": row[2],
                        "latency": 9999,
                        "video_codec": "h264",
                        "is_fixed": False
                    })
                    existing_names.add(name)
                    added += 1

            if added > 0:
                logger.info(f"✅ 从源池补充: {added} 个频道")
                logger.info(f"📊 补充后总数: {len(channels)} 个频道")

        if not channels:
            logger.warning("⚠️ 没有频道数据，跳过输出")
            return

        # 4. 合并频道
        logger.info(f"📊 开始合并 {len(channels)} 个频道...")
        merged = merge_channels_by_name(channels)

        # 5. 黑名单过滤
        if settings.enable_blacklist:
            blacklist = get_blacklist_filter()
            merged = blacklist.filter_channels(merged)

        # 6. Demo 筛选
        demo_order = parse_demo_order_with_categories() if settings.enable_demo_filter else []
        if demo_order and merged:
            ordered, _ = filter_and_order_by_demo(merged)
        else:
            ordered = merged

        if not ordered:
            logger.warning("⚠️ 筛选后无频道")
            return

        logger.info(f"📊 最终输出 {len(ordered)} 个频道")
        self.generator.generate_all(ordered, demo_order)


async def run_autonomous_mode(skip_discover: bool = False):
    orch = Orchestrator()
    await orch.run(skip_discover=skip_discover)
