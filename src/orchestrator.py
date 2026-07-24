# src/orchestrator.py
"""IPTV 编排器 - 协调所有服务"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from src.core.config import get_config
from src.core.exceptions import IPTVError
from src.infrastructure.database import get_db, channel_key
from src.infrastructure.logger import get_logger
from src.managers.source_manager import SourceManager
from src.managers.candidate_manager import CandidateManager
from src.managers.stable_manager import StableManager
from src.managers.quality_manager import QualityManager
from src.services.speed_tester import SpeedTester
from src.services.validator import Validator
from src.services.merger import Merger
from src.services.generator import Generator
from src.services.subscribe_manager import get_subscribe_urls
from src.services.demo_service import load_demo_order

logger = get_logger(__name__)


class IPTVOrchestrator:
    """IPTV 编排器"""
    
    def __init__(self, data_dir: Optional[Path] = None):
        self.config = get_config()
        self.data_dir = data_dir or self.config.data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化管理器
        self.source_manager = SourceManager(self.data_dir)
        self.candidate_manager = CandidateManager(self.data_dir)
        self.stable_manager = StableManager(self.data_dir)
        self.quality_manager = QualityManager(self.stable_manager)
        
        # 初始化服务
        self.speed_tester = SpeedTester()
        self.validator = Validator()
        self.merger = Merger()
        self.generator = Generator()
        
        # 统计
        self.stats = {
            "started_at": None,
            "finished_at": None,
            "discovered": 0,
            "observed": 0,
            "promoted": 0,
            "replaced": 0,
            "total_channels": 0,
        }
    
    async def run(self, skip_discover: bool = False) -> Dict[str, Any]:
        """运行完整流程"""
        self.stats["started_at"] = datetime.now()
        
        try:
            logger.info("🚀 IPTV 自治系统启动")
            logger.info(f"📊 配置: 并发={self.config.max_workers}, 超时={self.config.timeout}s")
            
            # 1. 发现新源
            if not skip_discover:
                new_sources = await self._discover_phase()
                self.stats["discovered"] = sum(len(v) for v in new_sources.values())
            else:
                logger.info("⏭️ 跳过发现阶段")
            
            # 2. 观察候选源
            stable_candidates = await self._observe_phase()
            self.stats["observed"] = len(stable_candidates)
            
            # 3. 提升稳定源
            promoted = await self._promote_phase(stable_candidates)
            self.stats["promoted"] = promoted
            
            # 4. 质量检查
            replaced = await self._quality_phase()
            self.stats["replaced"] = replaced
            
            # 5. 生成输出
            await self._generate_phase()
            
        except Exception as e:
            logger.exception(f"❌ 运行失败: {e}")
            raise
        
        finally:
            self.stats["finished_at"] = datetime.now()
            await self._cleanup()
        
        self._print_stats()
        return self.stats
    
    async def _discover_phase(self) -> Dict[str, List[Dict]]:
        """发现阶段"""
        logger.info("=" * 50)
        logger.info("阶段1: 发现新源")
        logger.info("=" * 50)
        
        # 获取订阅源
        sources = get_subscribe_urls()
        if not sources:
            sources = self.config.iptv_sources
            logger.info(f"📋 使用默认源: {len(sources)} 个")
        else:
            logger.info(f"📋 使用订阅源: {len(sources)} 个")
        
        # 分批处理
        batch_size = 5
        all_new = {}
        
        for i in range(0, len(sources), batch_size):
            batch = sources[i:i+batch_size]
            new = await self.source_manager.discover_sources(
                batch,
                filter_domestic=True,
                force_refresh=True
            )
            for name, channels in new.items():
                if name not in all_new:
                    all_new[name] = []
                all_new[name].extend(channels)
            
            logger.info(f"📊 进度: {min(i+batch_size, len(sources))}/{len(sources)}")
        
        # 添加到候选池
        for name, channels in all_new.items():
            for ch in channels[:100]:
                self.candidate_manager.add_candidate(
                    channel_key(name, ch["url"]),
                    name,
                    ch["url"]
                )
        
        return all_new
    
    async def _observe_phase(self) -> List[Dict]:
        """观察阶段"""
        logger.info("=" * 50)
        logger.info("阶段2: 观察候选源")
        logger.info("=" * 50)
        
        observing_count = self.candidate_manager.get_observing_count()
        if observing_count == 0:
            logger.info("📭 没有候选源需要观察")
            return []
        
        logger.info(f"📊 候选池状态: {observing_count} 个正在观察")
        
        # 从数据库获取测速结果
        db = await get_db()
        stable = []
        
        for obs in self.candidate_manager.get_observing_sources(limit=3000):
            # 查询测速历史
            rows = await db.fetch_all(
                """SELECT latency, success FROM speed_history 
                   WHERE channel_key = ? ORDER BY timestamp DESC LIMIT 10""",
                (obs["key"],)
            )
            
            if len(rows) < self.config.candidate_min_success:
                continue
            
            success_count = sum(1 for h in rows if h["success"])
            fail_count = len(rows) - success_count
            success_latencies = [h["latency"] for h in rows if h["success"] and h["latency"] > 0]
            avg_latency = sum(success_latencies) // max(len(success_latencies), 1) if success_latencies else 9999
            
            success_rate = success_count / len(rows)
            
            if (success_rate >= self.config.candidate_min_success_rate and 
                avg_latency <= self.config.candidate_max_latency):
                
                obs["success_count"] = success_count
                obs["fail_count"] = fail_count
                obs["avg_latency"] = avg_latency
                obs["status"] = "stable"
                stable.append(obs)
                
                logger.info(f"✅ 候选源稳定: {obs['name']} (成功率 {success_rate:.2%}, 延迟 {avg_latency}ms)")
        
        self.candidate_manager.batch_update(stable)
        logger.info(f"✅ 观察完成: {len(stable)} 个源达到稳定标准")
        return stable
    
    async def _promote_phase(self, stable_candidates: List[Dict]) -> int:
        """提升阶段"""
        logger.info("=" * 50)
        logger.info("阶段3: 提升稳定源")
        logger.info("=" * 50)
        
        if not stable_candidates:
            logger.info("📭 没有稳定的候选源需要提升")
            return 0
        
        promoted = 0
        for obs in stable_candidates[:50]:
            # 检查是否已存在
            existing = await self.stable_manager.get_source(obs["name"])
            if existing and existing.get("is_fixed"):
                continue
            if existing and existing.get("latency", 9999) < obs.get("avg_latency", 9999):
                continue
            
            if await self.stable_manager.promote(
                obs["name"],
                obs["url"],
                obs.get("avg_latency", 0),
                ""
            ):
                promoted += 1
                self.candidate_manager.mark_promoted(obs["key"])
                logger.info(f"📌 已提升: {obs['name']}")
        
        logger.info(f"✅ 提升完成: {promoted} 个源被提升")
        return promoted
    
    async def _quality_phase(self) -> int:
        """质量检查阶段"""
        logger.info("=" * 50)
        logger.info("阶段4: 质量检查")
        logger.info("=" * 50)
        
        if not self.config.autonomous_mode:
            logger.info("⏭️ 自治模式已禁用，跳过质量检查")
            return 0
        
        # 检查所有稳定源
        reports = await self.quality_manager.check_all()
        
        # 处理需要替换的源
        replaced = 0
        for report in reports:
            if report.get("status") == "critical":
                # 寻找候选替代
                candidates = self.candidate_manager.get_stable_sources()
                for cand in candidates:
                    if cand["name"] == report["channel_name"]:
                        if await self.stable_manager.replace(
                            report["channel_name"],
                            cand["url"],
                            cand.get("avg_latency", 0),
                            ""
                        ):
                            replaced += 1
                            self.candidate_manager.mark_promoted(cand["key"])
                            logger.info(f"🔄 已替换: {report['channel_name']}")
                            break
        
        logger.info(f"✅ 质量检查完成: 替换了 {replaced} 个失效源")
        return replaced
    
    async def _generate_phase(self):
        """生成输出"""
        logger.info("=" * 50)
        logger.info("阶段5: 生成输出")
        logger.info("=" * 50)
        
        # 获取稳定源
        sources = await self.stable_manager.get_active_sources()
        channels = []
        
        for name, src in sources.items():
            channels.append({
                "name": name,
                "url": src["url"],
                "urls": [src["url"]],
                "latency": src.get("latency", 0),
                "video_codec": src.get("video_codec", ""),
                "is_fixed": src.get("is_fixed", False),
            })
        
        if not channels:
            logger.warning("⚠️ 没有可用的稳定源")
            return
        
        # 合并
        merged = self.merger.merge(channels)
        self.stats["total_channels"] = len(merged)
        
        # 加载 demo 顺序
        demo_order = load_demo_order()
        
        # 生成输出
        self.generator.generate_all(merged, demo_order)
        
        # 智能补充
        from src.services.special_categories import collect_and_append_special_categories
        await collect_and_append_special_categories(self.config.output_dir)
        
        logger.info(f"✅ 输出生成完成: {len(merged)} 个频道")
    
    async def _cleanup(self):
        """清理资源"""
        from src.infrastructure.database import get_db
        from src.infrastructure.http_client import close_http_client
        
        db = await get_db()
        await db.close()
        await close_http_client()
        logger.info("🧹 资源已清理")
    
    def _print_stats(self):
        """打印统计"""
        duration = (self.stats["finished_at"] - self.stats["started_at"]).total_seconds()
        
        logger.info("=" * 50)
        logger.info("📊 运行统计")
        logger.info("=" * 50)
        logger.info(f"  耗时: {duration:.2f}s")
        logger.info(f"  发现新源: {self.stats['discovered']}")
        logger.info(f"  观察候选: {self.stats['observed']}")
        logger.info(f"  提升稳定: {self.stats['promoted']}")
        logger.info(f"  替换失效: {self.stats['replaced']}")
        logger.info(f"  输出频道: {self.stats['total_channels']}")
        logger.info("=" * 50)


# 全局编排器
_orchestrator = None


def get_orchestrator() -> IPTVOrchestrator:
    """获取编排器实例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = IPTVOrchestrator()
    return _orchestrator


async def run_autonomous_mode(skip_discover: bool = False) -> Dict[str, Any]:
    """运行自治模式"""
    orchestrator = get_orchestrator()
    return await orchestrator.run(skip_discover=skip_discover)
