# gui/worker.py
import sys
import os
import asyncio
import logging
from PyQt5.QtCore import QThread, pyqtSignal

class CollectionWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(self):
        super().__init__()

    def run(self):
        try:
            self.log_signal.emit("🚀 开始 IPTV 采集任务...")
            
            # 获取 exe 所在目录
            exe_dir = os.path.dirname(sys.executable)
            os.chdir(exe_dir)
            sys.path.insert(0, exe_dir)
            
            # ===== 关键：在导入 src 之前设置环境变量 =====
            os.environ["AUTONOMOUS_MODE"] = "true"
            os.environ["FFMPEG_ENABLE"] = "true"
            os.environ["ENABLE_DEMO_FILTER"] = "true"
            os.environ["ENABLE_ALIAS"] = "true"
            os.environ["ENABLE_BLACKLIST"] = "true"
            # 打印确认
            self.log_signal.emit(f"🔧 环境变量已设置: AUTONOMOUS_MODE={os.environ.get('AUTONOMOUS_MODE')}")

            from src.run import main as run_main
            from src.logger import logger

            # 自定义日志处理器
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
            logger.removeHandler(gui_handler)
