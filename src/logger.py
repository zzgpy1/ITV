# src/logger.py
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

# 从 config_loader 导入 config，避免循环依赖
from src.config_loader import config

def setup_logger(name: str = "IPTVCollector", level: int = logging.INFO, log_file: Path = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    if log_file is None:
        log_file = config.output_dir / "run.log"   # 使用 config.output_dir
    try:
        config.output_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=3, encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception:
        pass
    return logger

logger = setup_logger()
