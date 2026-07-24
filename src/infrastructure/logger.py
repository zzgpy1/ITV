# src/infrastructure/logger.py
"""统一日志系统"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

from src.core.config import get_config


class LoggerManager:
    """日志管理器"""
    
    _instance: Optional["LoggerManager"] = None
    _loggers: Dict[str, logging.Logger] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """初始化日志系统"""
        config = get_config()
        log_dir = config.output_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 根日志配置
        self._root_logger = logging.getLogger()
        self._root_logger.setLevel(logging.INFO)
        
        # 清除已有的处理器
        for handler in self._root_logger.handlers[:]:
            self._root_logger.removeHandler(handler)
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        self._root_logger.addHandler(console_handler)
        
        # 文件处理器
        try:
            file_handler = RotatingFileHandler(
                log_dir / "iptv.log",
                maxBytes=10*1024*1024,
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
            )
            file_handler.setFormatter(file_format)
            self._root_logger.addHandler(file_handler)
        except Exception:
            pass
    
    def get_logger(self, name: str = None) -> logging.Logger:
        """获取日志器"""
        if name is None:
            return self._root_logger
        
        if name not in self._loggers:
            self._loggers[name] = logging.getLogger(name)
        
        return self._loggers[name]


_logger_manager: Optional[LoggerManager] = None


def get_logger(name: str = None) -> logging.Logger:
    """获取日志器（便捷函数）"""
    global _logger_manager
    if _logger_manager is None:
        _logger_manager = LoggerManager()
    return _logger_manager.get_logger(name)


def set_log_level(level: str) -> None:
    """设置日志级别"""
    levels = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
    }
    logger = get_logger()
    logger.setLevel(levels.get(level.upper(), logging.INFO))
