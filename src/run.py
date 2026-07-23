# src/run.py
#!/usr/bin/env python3
import asyncio
import sys
from src.core.orchestrator import run_autonomous_mode
from src.logger import logger


async def main():
    try:
        await run_autonomous_mode(skip_discover=False)
    except KeyboardInterrupt:
        logger.warning("⚠️ 用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 运行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
