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
        QLabel { font-size: 14px; }
        QPushButton { padding: 6px 14px; font-size: 14px; font-weight: 500; }
        QComboBox { padding: 5px; font-size: 14px; }
        QLineEdit { padding: 6px; font-size: 14px; }
        QCheckBox { font-size: 14px; spacing: 8px; }
        QTableWidget { font-size: 13px; }
        QTableWidget::item { padding: 4px; }
        QHeaderView::section { font-size: 13px; font-weight: bold; padding: 6px; }
        QTabBar::tab { font-size: 14px; font-weight: bold; padding: 8px 16px; }
        QTextEdit { font-size: 14px; }
        QTextBrowser { font-size: 14px; }
        QGroupBox { font-size: 14px; font-weight: bold; }
        QGroupBox::title { color: #1976D2; }
        QProgressBar { font-size: 13px; min-height: 20px; }
        QMenuBar { font-size: 14px; }
        QMenu { font-size: 14px; }
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
