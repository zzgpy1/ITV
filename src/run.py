#!/usr/bin/env python3
# src/run.py
"""主入口"""

import asyncio
import sys
import signal
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import get_config
from src.core.exceptions import IPTVError
from src.infrastructure.logger import get_logger, set_log_level
from src.orchestrator import run_autonomous_mode

logger = get_logger(__name__)


def setup_signal_handlers():
    """设置信号处理器"""
    def signal_handler(sig, frame):
        logger.warning(f"⚠️ 收到信号 {sig}，正在退出...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """主函数"""
    # 加载配置
    config = get_config()
    
    # 设置日志级别
    log_level = "DEBUG" if "--debug" in sys.argv else "INFO"
    set_log_level(log_level)
    
    logger.info("🚀 IPTV 智能整理平台启动")
    logger.info(f"📡 配置: 超时={config.timeout}s, 并发={config.max_workers}")
    logger.info(f"📋 模式: {'自治' if config.autonomous_mode else '传统'}")
    
    # 设置信号处理器
    setup_signal_handlers()
    
    try:
        # 运行自治模式
        stats = await run_autonomous_mode(
            skip_discover="--skip-discover" in sys.argv
        )
        
        logger.info("🎉 运行完成!")
        return 0
        
    except IPTVError as e:
        logger.error(f"❌ IPTV 错误: {e}")
        return 1
    except KeyboardInterrupt:
        logger.warning("⚠️ 用户中断")
        return 130
    except Exception as e:
        logger.exception(f"❌ 未知错误: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
