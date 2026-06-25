# src/gui/styles.py
"""暗色主题样式表"""

DARK_STYLE = """
QMainWindow {
    background-color: #1a1d20;
/* 暗色主题样式 */
QMainWindow { background-color: #1a1d20; }
}

QWidget {
    background-color: #1a1d20;
    color: #e9ecef;
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 12px;
}

QListWidget {
    background-color: #212529;
    border: none;
    outline: none;
}

QListWidget::item {
    padding: 10px 15px;
    border-left: 3px solid transparent;
}

QListWidget::item:selected {
    background-color: #2b3035;
    border-left-color: #0d6efd;
}

QListWidget::item:hover {
    background-color: #2b3035;
}

QPushButton {
    background-color: #0d6efd;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #0b5ed7;
}

QPushButton:pressed {
    background-color: #0a58ca;
}

QPushButton:disabled {
    background-color: #3d444b;
    color: #6c757d;
}

QLineEdit, QSpinBox, QComboBox, QTextEdit {
    background-color: #2b3035;
    color: #e9ecef;
    border: 1px solid #3d444b;
    border-radius: 4px;
    padding: 6px 10px;
}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #0d6efd;
}

QTableWidget {
    background-color: #1a1d20;
    alternate-background-color: #212529;
    gridline-color: #2b3035;
    border: none;
}

QTableWidget::item {
    padding: 8px;
}

QTableWidget::item:selected {
    background-color: #0d6efd;
}

QHeaderView::section {
    background-color: #212529;
    color: #adb5bd;
    padding: 8px;
    border: none;
    border-bottom: 1px solid #3d444b;
}

QGroupBox {
    border: 1px solid #3d444b;
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 10px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #adb5bd;
}

QScrollBar:vertical {
    background-color: #1a1d20;
    width: 10px;
}

QScrollBar::handle:vertical {
    background-color: #3d444b;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #495057;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QMenuBar {
    background-color: #212529;
    color: #e9ecef;
}

QMenuBar::item:selected {
    background-color: #2b3035;
}

QMenu {
    background-color: #212529;
    color: #e9ecef;
    border: 1px solid #3d444b;
}

QMenu::item:selected {
    background-color: #0d6efd;
}

QMessageBox {
    background-color: #1a1d20;
}

QMessageBox QPushButton {
    min-width: 80px;
}
"""

LIGHT_STYLE = """
/* 可选的亮色主题，暂不实现 */
"""
