# gui/main_window.py
import sys
import os
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QTextEdit, QStatusBar, QLabel, QProgressBar, QMessageBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from gui.worker import CollectionWorker
from gui.config_dialog import ConfigDialog

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IPTV 智能管理平台")
        self.setMinimumSize(900, 600)
        self.worker = None
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 顶部按钮
        btn_layout = QHBoxLayout()
        self.run_btn = QPushButton("▶ 运行采集")
        self.run_btn.clicked.connect(self.start_collection)
        self.run_btn.setFixedHeight(40)
        self.config_btn = QPushButton("⚙️ 配置")
        self.config_btn.clicked.connect(self.open_config)
        self.config_btn.setFixedHeight(40)
        self.open_output_btn = QPushButton("📁 打开输出目录")
        self.open_output_btn.clicked.connect(self.open_output_folder)
        self.open_output_btn.setFixedHeight(40)

        btn_layout.addWidget(self.run_btn)
        btn_layout.addWidget(self.config_btn)
        btn_layout.addWidget(self.open_output_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 日志区域
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        layout.addWidget(self.log_text)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.status_label = QLabel("就绪")
        self.statusBar.addWidget(self.status_label)

        self.apply_style()

    def apply_style(self):
        style_path = os.path.join(os.path.dirname(__file__), "styles", "dark_theme.qss")
        if os.path.exists(style_path):
            with open(style_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

    def start_collection(self):
        """启动采集任务"""
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "提示", "采集任务正在运行中")
            return

        self.log_text.clear()
        self.run_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.status_label.setText("采集中...")

        # 设置环境变量，启用自治模式和 ffmpeg
        os.environ["AUTONOMOUS_MODE"] = "true"
        os.environ["FFMPEG_ENABLE"] = "true"
        os.environ["ENABLE_DEMO_FILTER"] = "true"
        os.environ["ENABLE_ALIAS"] = "true"
        os.environ["ENABLE_BLACKLIST"] = "true"

        self.worker = CollectionWorker()
        self.worker.log_signal.connect(self.append_log)
        self.worker.finished_signal.connect(self.on_collection_finished)
        self.worker.start()

    def append_log(self, text):
        self.log_text.append(text)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def on_collection_finished(self, success):
        self.run_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        if success:
            self.status_label.setText("采集完成")
            QMessageBox.information(self, "完成", "IPTV 采集任务成功完成！")
        else:
            self.status_label.setText("采集失败")
            QMessageBox.critical(self, "错误", "采集任务失败，请查看日志。")

    def open_config(self):
        dialog = ConfigDialog(self)
        if dialog.exec_():
            self.append_log("✅ 配置已更新，下次采集将生效")

    def open_output_folder(self):
        output_dir = os.path.join(os.path.dirname(sys.executable), "output")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        os.startfile(output_dir)
