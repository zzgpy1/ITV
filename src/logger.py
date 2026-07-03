# src/logger.py
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

from src.config import settings

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
        log_file = settings.OUTPUT_DIR / "run.log"
    try:
        settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        # 使用 RotatingFileHandler，最大 10MB，保留 3 个备份
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=3, encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception:
        pass
    return logger

logger = setup_logger()
