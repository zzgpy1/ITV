# src/utils/logger_handler.py
import logging
from typing import Optional, Callable

class GUILogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.callback: Optional[Callable] = None
    
    def set_callback(self, callback: Callable):
        self.callback = callback
    
    def emit(self, record):
        if self.callback:
            msg = self.format(record)
            self.callback(msg)

gui_log_handler = GUILogHandler()

def setup_gui_logging():
    import logging
    from src.logger import logger
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    gui_log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(gui_log_handler)
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(console)
    logger.info("📡 GUI 日志已配置")
