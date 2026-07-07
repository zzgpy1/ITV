# src/candidate/observer.py
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from src.logger import logger
from src.database import get_db_cache, channel_key
from src.candidate.models import ObservationResult, CandidateStatus


class CandidateObserver:
    """
    候选版观察者 - 优化版，批量加载候选池数据到内存，避免大量数据库查询
    """
    
    MIN_SUCCESS_COUNT = 3
    MIN_SUCCESS_RATE = 0.5
    MAX_AVG_LATENCY = 3000
    MAX_OBSERVE_PER_RUN = 3000
    
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or Path("data/candidate_pool.json")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._observations: Dict[str, ObservationResult] = {}
        self._load()
    
    def _load(self):
        if self.db_path.exists():
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for k, v in data.items():
                        self._observations[k] = ObservationResult.from_dict(v)
                logger.info(f"📦 加载候选池: {len(self._observations)} 个候选源")
            except Exception as e:
                logger.warning(f"加载候选池失败: {e}")
    
    def _save(self):
        try:
            data = {k: v.to_dict() for k, v in self._observations.items()}
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存候选池失败: {e}")
    
    def add_candidate(self, source_key: str, channel_name: str, url: str):
        if source_key not in self._observations:
            self._observations[source_key] = ObservationResult(
                source_key=source_key,
                channel_name=channel_name,
                url=url
            )
            self._save()
    
    def add_candidates_batch(self, sources: List[tuple]):
        added = 0
        for source_key, channel_name, url in sources:
            if source_key not in self._observations:
                self._observations[source_key] = ObservationResult(
                    source_key=source_key,
                    channel_name=channel_name,
                    url=url
                )
                added += 1
        if added > 0:
            self._save()
            logger.info(f"📝 批量添加 {added} 个候选源")
    
    async def _load_candidate_stats(self, db) -> Dict[str, Dict]:
        """批量加载所有候选池统计数据"""
        stats = {}
        if db is None or db._conn is None:
            return stats
        try:
            cursor = await db._conn.execute(
                "SELECT channel_key, success_count, fail_count, avg_latency FROM candidate_pool"
            )
            rows = await cursor.fetchall()
            await cursor.close()
            for row in rows:
                key, sc, fc, avg = row
                stats[key] = {"success": sc, "fail": fc, "avg": avg}
            logger.debug(f"批量加载候选池统计: {len(stats)} 条记录")
        except Exception as e:
            logger.warning(f"批量加载候选池统计失败: {e}")
        return stats
    
async def observe_batch_from_cache(self, batch_size: int = 3000) -> List[ObservationResult]:
    """分批观察候选源，从数据库读取统计，若无记录则从内存初始化"""
    observing = [
        (k, v) for k, v in self._observations.items() 
        if v.status == CandidateStatus.OBSERVING
    ]
    if not observing:
        return []

    observing.sort(key=lambda x: x[1].discovered_at)
    batch = observing[:batch_size]

    logger.info(f"🔍 本次观察 {len(batch)} 个候选源（共 {len(observing)} 个待观察）...")

    db = await get_db_cache()
    if db is None or db._conn is None:
        logger.error("❌ 数据库连接无效，无法观察候选源")
        return []

    # 批量加载候选池统计数据
    stats_map = await self._load_candidate_stats(db)

    stable_results = []
    processed = 0
    last_log = 0

    for key, obs in batch:
        stat = stats_map.get(key)
        if stat:
            # 更新内存中的统计
            obs.success_count = stat["success"]
            obs.fail_count = stat["fail"]
            obs.avg_latency = stat["avg"]
            obs.check_count = stat["success"] + stat["fail"]
            obs.last_check = datetime.now()
        else:
            # 数据库无记录，尝试从内存插入初始记录
            # 但此时 stat 为空，说明从未测速过，我们保留内存中的原始数据，但不改变状态
            # 也可以选择插入一条初始记录
            await db._conn.execute(
                '''INSERT OR IGNORE INTO candidate_pool 
                   (channel_key, success_count, fail_count, avg_latency, last_check, status)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (obs.source_key, 0, 0, 0, datetime.now().isoformat(), 'observing')
            )
            await db._conn.commit()
            # 仍然使用内存中的统计（可能为0）
            # 但无法判断稳定，跳过

        # 判断是否达到稳定标准（仅当有统计时）
        if stat:
            if obs.check_count >= self.MIN_SUCCESS_COUNT and \
               obs.success_rate >= self.MIN_SUCCESS_RATE and \
               obs.avg_latency <= self.MAX_AVG_LATENCY:
                obs.status = CandidateStatus.STABLE
                self._save()
                # 同步更新数据库状态
                try:
                    await db._conn.execute(
                        "UPDATE candidate_pool SET status = ? WHERE channel_key = ?",
                        ('stable', obs.source_key)
                    )
                    await db._conn.commit()
                except Exception as e:
                    logger.warning(f"更新数据库状态失败: {e}")
                stable_results.append(obs)
                logger.info(f"✅ 候选源稳定: {obs.channel_name} (成功率 {obs.success_rate:.2%}, 延迟 {obs.avg_latency}ms, 检查 {obs.check_count} 次)")

        processed += 1
        if processed - last_log >= 100:
            logger.info(f"  📊 观察进度: {processed}/{len(batch)}，稳定 {len(stable_results)} 个")
            last_log = processed

    if stable_results:
        logger.info(f"✅ 本批次 {len(stable_results)} 个源达到稳定标准")
    else:
        logger.info(f"📊 本批次无新稳定源")

    return stable_results
    
    def get_candidates(self) -> List[ObservationResult]:
        return list(self._observations.values())
    
    def get_stable_candidates(self) -> List[ObservationResult]:
        return [v for v in self._observations.values() if v.status == CandidateStatus.STABLE]
    
    def get_observing_count(self) -> int:
        return sum(1 for v in self._observations.values() if v.status == CandidateStatus.OBSERVING)
    
    def mark_promoted(self, source_key: str):
        if source_key in self._observations:
            self._observations[source_key].status = CandidateStatus.PROMOTED
            self._observations[source_key].promoted_at = datetime.now()
            self._save()
    
    def get_statistics(self) -> dict:
        stats = {
            "total": len(self._observations),
            "observing": self.get_observing_count(),
            "stable": sum(1 for v in self._observations.values() if v.status == CandidateStatus.STABLE),
            "promoted": sum(1 for v in self._observations.values() if v.status == CandidateStatus.PROMOTED),
            "rejected": sum(1 for v in self._observations.values() if v.status == CandidateStatus.REJECTED),
        }
        return stats
