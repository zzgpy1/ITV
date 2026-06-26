# gui/worker.py
import sys
import os
import subprocess
import threading
from PyQt5.QtCore import QThread, pyqtSignal

class CollectionWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)
    progress_signal = pyqtSignal(int, int)

    def __init__(self):
        super().__init__()

    def run(self):
        try:
            self.log_signal.emit("🚀 开始 IPTV 采集任务...")
            
            # 获取当前可执行文件所在目录
            base_dir = os.path.dirname(sys.executable)
            # 将项目根目录添加到 Python 路径
            sys.path.insert(0, base_dir)
            
            # 导入并运行主采集逻辑
            import asyncio
            from src.run import main as run_main
            
            # 重定向日志输出到信号
            import logging
            from src.logger import logger
            
            # 添加自定义日志处理器
            class GuiLogHandler(logging.Handler):
                def __init__(self, signal):
                    super().__init__()
                    self.signal = signal
                def emit(self, record):
                    msg = self.format(record)
                    self.signal.emit(msg)
            
            gui_handler = GuiLogHandler(self.log_signal)
            gui_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            logger.addHandler(gui_handler)
            
            # 运行异步主函数
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            exit_code = loop.run_until_complete(run_main())
            loop.close()
            
            if exit_code == 0:
                self.log_signal.emit("✅ 采集任务成功完成")
                self.finished_signal.emit(True)
            else:
                self.log_signal.emit(f"❌ 采集任务退出，错误码: {exit_code}")
                self.finished_signal.emit(False)
                
        except Exception as e:
            self.log_signal.emit(f"❌ 采集任务异常: {str(e)}")
            import traceback
            self.log_signal.emit(traceback.format_exc())
            self.finished_signal.emit(False)
        finally:
            # 清理日志处理器
            logger.removeHandler(gui_handler)
