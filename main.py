import sys
import os

from PySide6.QtCore import QSettings
from pathlib import Path

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from core.platform_utils import get_default_font, detect_all_storage, IS_WINDOWS
from ui.main_window import MainWindow
from ui.setup_wizard import SetupWizard


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont(get_default_font(), 12))
    app.setStyleSheet("""
        * { color: #FFFFFF; }
        QWidget { background-color: #1E1E1E; }
        QMainWindow { background-color: #1E1E1E; }
        QLabel { font-size: 14px; }
        QPushButton {
            padding: 6px 14px; font-size: 14px; font-weight: 500;
            background-color: #333333; color: #FFFFFF; border: 1px solid #555555;
            border-radius: 4px;
        }
        QPushButton:hover { background-color: #444444; }
        QPushButton:pressed { background-color: #555555; }
        QComboBox {
            padding: 5px; font-size: 14px;
            background-color: #2A2A2A; color: #FFFFFF; border: 1px solid #555555;
        }
        QComboBox QAbstractItemView {
            background-color: #2A2A2A; color: #FFFFFF;
            selection-background-color: #444444;
        }
        QLineEdit {
            padding: 6px; font-size: 14px;
            background-color: #2A2A2A; color: #FFFFFF; border: 1px solid #555555;
        }
        QCheckBox { font-size: 14px; spacing: 8px; }
        QCheckBox::indicator { width: 16px; height: 16px; }
        QTableWidget {
            font-size: 13px; background-color: #2A2A2A; color: #FFFFFF;
            gridline-color: #444444; alternate-background-color: #333333;
        }
        QTableWidget::item { padding: 4px; }
        QTableWidget::item:selected { background-color: #444444; }
        QHeaderView::section {
            font-size: 13px; font-weight: bold; padding: 6px;
            background-color: #333333; color: #FFFFFF; border: 1px solid #444444;
        }
        QTabWidget::pane { border: 1px solid #444444; background-color: #1E1E1E; }
        QTabBar::tab {
            font-size: 14px; font-weight: bold; padding: 8px 16px;
            background-color: #2A2A2A; color: #AAAAAA; border: 1px solid #444444;
        }
        QTabBar::tab:selected { background-color: #1E1E1E; color: #FFFFFF; border-bottom: none; }
        QTabBar::tab:hover { color: #FFFFFF; }
        QTextEdit { font-size: 14px; background-color: #2A2A2A; color: #FFFFFF; }
        QTextBrowser { font-size: 14px; background-color: #2A2A2A; color: #FFFFFF; }
        QGroupBox { font-size: 14px; font-weight: bold; border: 1px solid #444444; margin-top: 8px; padding-top: 14px; }
        QGroupBox::title { color: #5B9BD5; }
        QProgressBar {
            font-size: 13px; min-height: 20px;
            background-color: #2A2A2A; color: #FFFFFF; border: 1px solid #444444;
        }
        QProgressBar::chunk { background-color: #5B9BD5; }
        QMenuBar { font-size: 14px; background-color: #2A2A2A; color: #FFFFFF; }
        QMenuBar::item:selected { background-color: #444444; }
        QMenu { font-size: 14px; background-color: #2A2A2A; color: #FFFFFF; }
        QMenu::item:selected { background-color: #444444; }
        QScrollArea { background-color: #1E1E1E; }
        QScrollBar:vertical {
            background-color: #2A2A2A; width: 12px;
        }
        QScrollBar::handle:vertical { background-color: #555555; border-radius: 4px; min-height: 20px; }
        QScrollBar:horizontal {
            background-color: #2A2A2A; height: 12px;
        }
        QScrollBar::handle:horizontal { background-color: #555555; border-radius: 4px; min-width: 20px; }
        QDialog { background-color: #1E1E1E; }
        QMessageBox { background-color: #1E1E1E; }
        QToolTip { background-color: #333333; color: #FFFFFF; border: 1px solid #555555; }
    """)

    # Set app icon for taskbar and window title bar
    # PyInstaller stores data files in sys._MEIPASS when bundled
    base_dir = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))

    # Try .ico first (Windows), then .png (Linux)
    icon_path = base_dir / "app_icon.ico"
    if not icon_path.exists():
        icon_path = base_dir / "app_icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    settings = QSettings("StorageCleaner", "StorageCleaner")

    # First-run setup wizard
    if not settings.value("setup/completed", False, type=bool):
        wizard = SetupWizard(settings)
        if wizard.exec() != wizard.Accepted:
            sys.exit(0)

    # Read saved settings - try new key first, fall back to old key
    storage_str = settings.value("setup/selected_storage", "", type=str)
    if not storage_str:
        storage_str = settings.value("setup/selected_drives", "", type=str)
    storage_list = [s.strip() for s in storage_str.split(",") if s.strip()]
    user_name = settings.value("setup/user_name", "", type=str)

    # Fallback: if no storage configured, use first detected
    if not storage_list:
        all_storage = detect_all_storage()
        if all_storage:
            storage_list = [all_storage[0]["id"]]
        elif IS_WINDOWS:
            storage_list = [os.environ.get("SystemDrive", "C:")[:1]]
        else:
            storage_list = ["root"]

    win = MainWindow(selected_storage=storage_list, user_name=user_name)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
