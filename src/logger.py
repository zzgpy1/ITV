# src/logger.py
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from src.settings import settings

def setup_logger(name: str = "IPTV"):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)
    # 文件日志
    try:
        log_dir = settings.output_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(log_dir / "run.log", maxBytes=10*1024*1024, backupCount=3, encoding='utf-8')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception:
        pass
    return logger

logger = setup_logger()
