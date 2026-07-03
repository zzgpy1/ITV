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
from src.config import (
    ENABLE_DEMO_FILTER, OUTPUT_DIR,
    CANDIDATE_OBSERVATION_HOURS, CANDIDATE_MIN_SUCCESS,
    CANDIDATE_MIN_SUCCESS_RATE, CANDIDATE_MAX_LATENCY,
    HEALTH_HISTORY_DAYS, PREDICT_THRESHOLD,
    AUTO_PROMOTE_THRESHOLD, SLOW_SPEED_THRESHOLD
)
from src.demo_filter import parse_demo_order_with_categories
from src.generator import generate_outputs_from_demo


class IPTVOrchestrator:
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

        CandidateObserver.MIN_SUCCESS_COUNT = min(CANDIDATE_MIN_SUCCESS, 3)
        CandidateObserver.MIN_SUCCESS_RATE = CANDIDATE_MIN_SUCCESS_RATE
        CandidateObserver.MAX_AVG_LATENCY = CANDIDATE_MAX_LATENCY

    async def predict_failure_probability(self, channel_key: str) -> float:
        """基于历史速度数据预测未来7天失效概率"""
        if not self.db:
            self.db = await get_db_cache()
        history = await self.db.get_speed_history(channel_key, days=HEALTH_HISTORY_DAYS)
        if len(history) < 5:
            return 0.0
        recent = history[-10:]
        success_rate = sum(1 for h in recent if h['success']) / len(recent)
        latencies = [h['latency'] for h in recent if h['success']]
        if latencies:
            avg_lat = sum(latencies) / len(latencies)
            trend = (latencies[-1] - latencies[0]) / (latencies[0] + 1) if latencies else 0
            prob = (1 - success_rate) * 0.6 + min(1, max(0, trend)) * 0.4
            return min(1, prob)
        return 0.0

    async def auto_replace_if_risky(self):
        """检查所有稳定源，如果预测失效概率高于阈值，则从候选池提拔替补"""
        if not self.db:
            self.db = await get_db_cache()
        stable = self.stable_manager.get_active_sources()
        candidates = await self.db.get_candidates_for_promotion()
        replaced = 0
        for name, src in stable.items():
            if src.is_fixed and not src.auto_optimize:
                continue
            key = channel_key(name, src.url)
            prob = await self.predict_failure_probability(key)
            if prob > PREDICT_THRESHOLD:
                logger.warning(f"⚠️ {name} 预测失效概率 {prob:.2%}，尝试从候选池替换")
                for cand in candidates:
                    if cand['name'] == name and cand['url'] != src.url:
                        self.stable_manager.replace_source(name, cand['url'], cand['latency'], "")
                        logger.info(f"✅ {name} 已预替换为 {cand['url']}")
                        replaced += 1
                        break
        return replaced

    async def discover_phase(self) -> Dict:
        logger.info("=" * 50)
        logger.info("阶段1: 发现新源（国内频道）")
        logger.info("=" * 50)
        try:
            if not self.db:
                self.db = await get_db_cache()
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
            if total_new > self.MAX_NEW_SOURCES_PER_RUN:
                logger.warning(f"⚠️ 新源数量 {total_new} 超过限制 {self.MAX_NEW_SOURCES_PER_RUN}，只取前 {self.MAX_NEW_SOURCES_PER_RUN} 个")
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
        logger.info("=" * 50)
        logger.info("阶段3: 提升稳定源")
        logger.info("=" * 50)
        try:
            if stable_candidates is None:
                stable_candidates = self.candidate_observer.get_stable_candidates()
            if not stable_candidates:
                logger.info("📭 没有稳定的候选源需要提升")
                return 0
            before_count = len(self.stable_manager.get_active_sources())
            promoted_count = 0
            for obs in stable_candidates[:50]:
                existing = self.stable_manager.stable_sources.get(obs.channel_name)
                if existing and existing.is_fixed:
                    continue
                if existing and existing.latency < obs.avg_latency:
                    continue
                if self.stable_manager.promote_candidate(
                    obs.channel_name, obs.url, obs.avg_latency, ""
                ):
                    promoted_count += 1
                    self.candidate_observer.mark_promoted(obs.source_key)
                    logger.info(f"📌 已提升: {obs.channel_name}")
            self.stats["total_promoted"] += promoted_count
            self.stats["new_stable_count"] = promoted_count
            after_count = len(self.stable_manager.get_active_sources())
            self.stats["stable_count_after"] = after_count
            logger.info(f"✅ 提升阶段完成: {promoted_count} 个源被提升到稳定版")
            logger.info(f"📊 稳定源变化: {before_count} -> {after_count}")
            return promoted_count
        except Exception as e:
            logger.error(f"❌ 提升稳定源阶段失败: {e}")
            return 0

    async def run_once(self, skip_discover: bool = False) -> Dict:
        logger.info("🚀 IPTV 自治系统启动")
        logger.info(f"📊 配置: 每批发现 {self.MAX_NEW_SOURCES_PER_RUN} 个，每批观察 {self.MAX_OBSERVE_PER_RUN} 个")
        logger.info("📌 只处理国内频道，国外频道自动过滤")
        if skip_discover:
            logger.info("⏭️ 跳过发现阶段（使用已有源池）")
        else:
            logger.info("⚡ 强制刷新模式：重新拉取所有源")
        try:
            self.db = await get_db_cache()
            if not skip_discover:
                await self.discover_phase()
            else:
                logger.info("⏭️ 跳过发现阶段")
            stable_candidates = await self.observe_phase()
            await self.promote_phase(stable_candidates)
            replaced = await self.auto_replace_if_risky()
            if replaced:
                logger.info(f"🔄 已预替换 {replaced} 个高风险源")
            logger.info("=" * 50)
            logger.info("📊 自治模式统计")
            logger.info("=" * 50)
            logger.info(f"  源池总数: {self.discoverer.get_statistics()['total']}")
            logger.info(f"  候选池总数: {self.candidate_observer.get_statistics()['total']}")
            logger.info(f"  候选池观察中: {self.candidate_observer.get_statistics()['observing']}")
            logger.info(f"  本次新提升: {self.stats.get('new_stable_count', 0)}")
            logger.info(f"  累计提升: {self.stats['total_promoted']}")
        except Exception as e:
            logger.exception(f"❌ 自治流程执行失败: {e}")
        finally:
            if self.db:
                await self.db.close()
        return self.stats


# 全局实例
_orchestrator = None

def get_orchestrator() -> IPTVOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = IPTVOrchestrator()
    return _orchestrator

async def run_autonomous_mode():
    orchestrator = get_orchestrator()
    return await orchestrator.run_once()
