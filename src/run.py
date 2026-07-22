#!/usr/bin/env python3
import asyncio
import sys
from src.orchestrator import Orchestrator
from src.logger import logger
from src.database import get_db

async def main():
    logger.info("IPTV 自治系统启动")
    orchestrator = Orchestrator()
    await orchestrator.run(skip_discover=False)
    # 关闭数据库
    db = await get_db()
    await db.close()
    logger.info("运行结束")

if __name__ == "__main__":
    asyncio.run(main())
