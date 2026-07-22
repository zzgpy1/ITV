import asyncio
import sys
from src.settings import settings
from src.logger import logger
from src.database import db
from src.orchestrator import Orchestrator

async def main():
    logger.info("🚀 IPTV 智能管理平台启动")
    await db.init()
    orch = Orchestrator()
    await orch.run(skip_discover=False)
    await db.close()
    logger.info("🎉 全部完成")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("⚠️ 用户中断")
        sys.exit(1)
