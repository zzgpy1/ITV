# src/orchestrator.py
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from src.logger import logger
from src.database import get_db_cache, channel_key
from src.source_pool.discoverer import SourceDiscoverer
from src.candidate.observer import CandidateObserver
from src.stable.manager import StableManager
from src.quality.monitor import QualityMonitor
from src.config_loader import config
from src.demo_filter import parse_demo_order_with_categories
from src.generator import generate_outputs_from_demo


class IPTVOrchestrator:
    """IPTV 自治系统编排器"""
    
    MAX_NEW_SOURCES_PER_RUN = 5000
    MAX_OBSERVE_PER_RUN = 3000

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path("data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db = None

        self.discoverer = SourceDiscoverer(self.data_dir / "source_pool.json")
        self.candidate_observer = CandidateObserver(self.data_dir / "candidate_pool.json")
        self.stable_manager = StableManager()
        self.quality_monitor = QualityMonitor(self.stable_manager)

        self.stats = {
            "last_discover": None,
            "last_observe": None,
            "total_promoted": 0,
            "new_sources_count": 0,
            "observed_count": 0,
            "stable_count_after": 0,
            "new_stable_count": 0
        }

        # 从配置读取候选阈值
        CandidateObserver.MIN_SUCCESS_COUNT = max(config.candidate_min_success, 3)
        CandidateObserver.MIN_SUCCESS_RATE = config.candidate_min_success_rate
        CandidateObserver.MAX_AVG_LATENCY = config.candidate_max_latency

    async def _ensure_db(self):
        if self.db is None:
            self.db = await get_db_cache()
            # 检查 candidate_pool 表是否存在数据，若空则从 JSON 导入
            cursor = await self.db._conn.execute('SELECT COUNT(*) FROM candidate_pool')
            count = (await cursor.fetchone())[0]
            await cursor.close()
            if count == 0:
                json_path = self.data_dir / "candidate_pool.json"
                if json_path.exists():
                    await self.db.import_candidate_pool_from_json(json_path)
                    logger.info("📥 已将 JSON 候选池导入数据库")
                else:
                    logger.warning("⚠️ 没有候选池数据，自治模式无法工作")

    async def discover_phase(self) -> Dict:
        """阶段1: 发现新源（仅国内频道）"""
        logger.info("=" * 50)
        logger.info("阶段1: 发现新源（国内频道）")
        logger.info("=" * 50)
        await self._ensure_db()
        try:
            new_sources = await asyncio.wait_for(
                self.discoverer.discover(self.db, filter_domestic=True, force_refresh=True),
                timeout=120
            )
            total_new = sum(len(s) for s in new_sources.values())
            self.stats["new_sources_count"] = total_new
            self.stats["last_discover"] = datetime.now()
            if total_new == 0:
                logger.info("✅ 没有发现新源")
                return {}
            # 限制数量并加入候选池
            added_sources = []
            count = 0
            for channel_name, sources in new_sources.items():
                for src in sources:
                    if count >= self.MAX_NEW_SOURCES_PER_RUN:
                        break
                    added_sources.append((src.get_key(), channel_name, src.url))
                    count += 1
                if count >= self.MAX_NEW_SOURCES_PER_RUN:
                    break
            self.candidate_observer.add_candidates_batch(added_sources)
            logger.info(f"✅ 发现阶段完成: {len(added_sources)} 个新源进入候选池")
            return new_sources
        except Exception as e:
            logger.error(f"❌ 发现新源阶段失败: {e}")
            return {}

    async def observe_phase(self) -> List:
        """阶段2: 从缓存观察候选源"""
        logger.info("=" * 50)
        logger.info("阶段2: 从缓存观察候选源")
        logger.info("=" * 50)
        try:
            observing_count = self.candidate_observer.get_observing_count()
            if observing_count == 0:
                logger.info("📭 没有候选源需要观察")
                return []
            stable_count = len(self.candidate_observer.get_stable_candidates())
            logger.info(f"📊 候选池状态: {observing_count} 个正在观察，{stable_count} 个已稳定")
            stable_candidates = await asyncio.wait_for(
                self.candidate_observer.observe_batch_from_cache(
                    batch_size=self.MAX_OBSERVE_PER_RUN
                ),
                timeout=150
            )
            self.stats["last_observe"] = datetime.now()
            self.stats["observed_count"] = len(stable_candidates)
            logger.info(f"✅ 观察阶段完成: {len(stable_candidates)} 个源达到稳定标准")
            return stable_candidates
        except asyncio.TimeoutError:
            logger.warning("⚠️ 观察候选源阶段整体超时")
            return []
        except Exception as e:
            logger.error(f"❌ 观察候选源阶段失败: {e}")
            return []

    async def promote_phase(self, stable_candidates: List = None) -> int:
        """阶段3: 提升稳定源"""
        logger.info("=" * 50)
        logger.info("阶段3: 提升稳定源")
        logger.info("=" * 50)
        try:
            if stable_candidates is None:
                stable_candidates = self.candidate_observer.get_stable_candidates()
                logger.info(f"📦 从内存获取稳定候选: {len(stable_candidates)} 个")
            if not stable_candidates:
                logger.info("📭 没有稳定的候选源需要提升")
                return 0

            before_count = len(await self.stable_manager.get_stable_sources())
            promoted_count = 0
            for obs in stable_candidates[:50]:  # 最多提升50个
                # 如果 obs 是字典（从数据库来的），构造对象
                if isinstance(obs, dict):
                    from src.candidate.models import ObservationResult
                    obs_obj = ObservationResult(
                        source_key=obs.get('key', ''),
                        channel_name=obs.get('name', ''),
                        url=obs.get('url', ''),
                        avg_latency=obs.get('latency', 0),
                        success_count=obs.get('success', 0),
                        fail_count=obs.get('fail', 0)
                    )
                else:
                    obs_obj = obs

                existing = await self.stable_manager.get_stable_source(obs_obj.channel_name)
                if existing and existing.get('is_fixed'):
                    continue
                if existing and existing.get('latency', 9999) < obs_obj.avg_latency:
                    continue
                if await self.stable_manager.promote_candidate(
                    obs_obj.channel_name, obs_obj.url, obs_obj.avg_latency, ""
                ):
                    promoted_count += 1
                    self.candidate_observer.mark_promoted(obs_obj.source_key)
                    logger.info(f"📌 已提升: {obs_obj.channel_name}")

            self.stats["total_promoted"] += promoted_count
            self.stats["new_stable_count"] = promoted_count
            after_count = len(await self.stable_manager.get_stable_sources())
            self.stats["stable_count_after"] = after_count
            logger.info(f"✅ 提升阶段完成: {promoted_count} 个源被提升到稳定版")
            logger.info(f"📊 稳定源变化: {before_count} -> {after_count}")
            return promoted_count
        except Exception as e:
            logger.error(f"❌ 提升稳定源阶段失败: {e}")
            return 0

    async def run_once(self, skip_discover: bool = False) -> Dict:
        """执行一次完整的自治流程"""
        logger.info("🚀 IPTV 自治系统启动")
        logger.info(f"📊 配置: 每批发现 {self.MAX_NEW_SOURCES_PER_RUN} 个，每批观察 {self.MAX_OBSERVE_PER_RUN} 个")
        logger.info("📌 只处理国内频道，国外频道自动过滤")
        if skip_discover:
            logger.info("⏭️ 跳过发现阶段（使用已有源池）")
        else:
            logger.info("⚡ 强制刷新模式：重新拉取所有源")

        await self._ensure_db()

        # 阶段1: 发现
        if not skip_discover:
            await self.discover_phase()
        else:
            logger.info("⏭️ 跳过发现阶段")

        # 阶段2: 观察
        stable_candidates = await self.observe_phase()

        # 阶段3: 提升
        await self.promote_phase(stable_candidates)

        # 统计输出
        logger.info("=" * 50)
        logger.info("📊 自治模式统计")
        logger.info("=" * 50)
        logger.info(f"  源池总数: {self.discoverer.get_statistics()['total']}")
        stats = self.candidate_observer.get_statistics()
        logger.info(f"  候选池总数: {stats['total']}")
        logger.info(f"  候选池观察中: {stats['observing']}")
        logger.info(f"  本次新提升: {self.stats.get('new_stable_count', 0)}")
        logger.info(f"  累计提升: {self.stats['total_promoted']}")

        return self.stats


# ========== 全局函数 ==========
_orchestrator = None

def get_orchestrator() -> IPTVOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = IPTVOrchestrator()
    return _orchestrator

async def run_autonomous_mode(skip_discover: bool = False):
    """供 run.py 调用的自治模式入口"""
    orchestrator = get_orchestrator()
    return await orchestrator.run_once(skip_discover=skip_discover)
