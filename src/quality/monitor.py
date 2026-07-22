# src/quality/monitor.py
from src.repositories import repo_factory
from src.logger import logger

class QualityMonitor:
    def __init__(self, stable_manager):
        self.stable_manager = stable_manager

    async def check_all_active_sources(self):
        stable = await repo_factory.stable.get_all()
        for name, info in stable.items():
            # 模拟检查，实际可进行测速
            pass

    def get_critical_sources(self):
        # 返回连续失败>3的稳定源
        # 简化实现
        return []
