# src/quality/monitor.py
from src.repositories import repo_factory
from src.logger import logger
from src.speed_tester import SpeedTester, channel_key


class QualityMonitor:
    def __init__(self):
        self.stable_repo = repo_factory.stable
        self.candidate_repo = repo_factory.candidate
        self.speed_tester = SpeedTester()

    async def check_all_active_sources(self):
        active = await self.stable_repo.get_all()
        if not active:
            return

        logger.info(f"🔍 检查 {len(active)} 个稳定源的质量")
        critical = []

        for name, info in active.items():
            # 仅检查非固定源
            if info["is_fixed"]:
                continue
            # 获取最近历史
            key = channel_key(name, info["url"])
            history = await repo_factory.history.get_history(key, days=7)
            if len(history) < 5:
                continue

            # 计算成功率
            total = len(history)
            success_count = sum(1 for h in history if h["success"])
            success_rate = success_count / total if total > 0 else 0
            avg_latency = sum(h["latency"] for h in history if h["success"]) // max(success_count, 1)

            # 判断是否需要替换
            if success_rate < 0.5 or avg_latency > 5000:
                critical.append(name)
                logger.warning(f"⚠️ {name} 质量下降: 成功率 {success_rate:.1%}, 延迟 {avg_latency}ms")

        if critical:
            logger.info(f"⚠️ 发现 {len(critical)} 个需要替换的源")
            return critical
        return []

    async def get_critical_sources(self):
        return await self.check_all_active_sources()
