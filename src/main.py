# src/main.py
"""IPTV 智能管理 GUI 工具 - 程序入口"""

import sys
from pathlib import Path

# 将项目根目录添加到 sys.path，确保能导入 src 模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from src.gui.main_window import IPTVMainWindow
from src.utils.logger_handler import setup_gui_logging


def main():
    """程序入口"""
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setApplicationName("IPTV 智能管理工具")
    app.setOrganizationName("IPTVCollector")
    
    # 配置日志重定向到 GUI
    setup_gui_logging()
    
    # 创建主窗口
    window = IPTVMainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
