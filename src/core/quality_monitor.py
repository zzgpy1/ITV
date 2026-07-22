# src/core/quality_monitor.py
from src.repository import repo_factory
from src.settings import settings
from src.logger import logger

class QualityMonitor:
    def __init__(self, stable_manager):
        self.stable_manager = stable_manager

    async def check_all(self):
        active = await repo_factory.stable.get_active()
        for src in active:
            # 简单健康检查：这里可以调用实际测速，但简化
            pass
