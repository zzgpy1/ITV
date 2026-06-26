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
        # 全局异常捕获，确保任何错误都能反馈到界面
        try:
            self.log_signal.emit("🚀 开始 IPTV 采集任务...")
            
            # 获取可执行文件所在目录（打包后为 exe 所在路径）
            base_dir = os.path.dirname(sys.executable)
            self.log_signal.emit(f"📂 工作目录: {base_dir}")
            self.log_signal.emit(f"📂 sys.path: {sys.path}")

            # 确保 internal 目录在路径中（PyInstaller onedir 模式）
            internal_dir = os.path.join(base_dir, '_internal')
            if os.path.exists(internal_dir) and internal_dir not in sys.path:
                sys.path.insert(0, internal_dir)
                self.log_signal.emit(f"📂 已添加 _internal 路径: {internal_dir}")

            # 验证 src 模块能否导入
            try:
                import src
                self.log_signal.emit("✅ src 模块导入成功")
            except ImportError as e:
                self.log_signal.emit(f"❌ src 模块导入失败: {e}")
                self.finished_signal.emit(False)
                return

            # 导入主采集函数
            try:
                from src.run import main as run_main
                self.log_signal.emit("✅ src.run 导入成功")
            except ImportError as e:
                self.log_signal.emit(f"❌ src.run 导入失败: {e}")
                self.finished_signal.emit(False)
                return

            # 设置日志捕获
            from src.logger import logger
            self.log_signal.emit("✅ 日志模块加载成功")

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

            # 运行异步采集
            self.log_signal.emit("⏳ 正在运行采集任务，请稍候...")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                exit_code = loop.run_until_complete(run_main())
            finally:
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
            try:
                logger.removeHandler(gui_handler)
            except:
                pass
