from src.discoverer import Discoverer
from src.observer import Observer
from src.stable_manager import StableManager
from src.quality_monitor import QualityMonitor
from src.generator import generate_outputs
from src.demo_filter import filter_and_order_by_demo, parse_demo_order
from src.settings import settings
from src.logger import logger

class Orchestrator:
    def __init__(self):
        self.discoverer = Discoverer()
        self.observer = Observer()
        self.stable_mgr = StableManager()
        self.quality_monitor = QualityMonitor()

    async def run(self, skip_discover=False):
        logger.info("开始自治流程")
        if not skip_discover:
            await self.discoverer.discover(force_refresh=True)
        # 观察候选
        await self.observer.observe()
        # 同步固定源
        await self.stable_mgr.sync_fixed_sources()
        # 质量检查并替换
        await self.quality_monitor.check_all()
        # 生成最终输出（从稳定源构建频道列表）
        stables = await self.stable_mgr.stable_repo.get_all()
        channels = []
        for name, s in stables.items():
            # 构造完整的频道字典
            ch = {
                "name": name,
                "url": s.url,
                "urls": [s.url],
                "latency": s.latency,
                "video_codec": s.video_codec,
                "is_fixed": s.is_fixed
            }
            channels.append(ch)
        # demo 筛选
        demo_order = parse_demo_order()
        ordered = filter_and_order_by_demo(channels)
        await generate_outputs(ordered, demo_order)
        logger.info("自治流程完成")
