# src/run.py
import asyncio
from src.core.orchestrator import Orchestrator
from src.logger import logger

async def main():
    orch = Orchestrator()
    await orch.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("用户中断")
