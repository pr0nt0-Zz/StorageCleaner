import sys
import os

from PySide6.QtCore import QSettings
from pathlib import Path

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui.setup_wizard import SetupWizard


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    # Set app icon for taskbar and window title bar
    # PyInstaller stores data files in sys._MEIPASS when bundled
    base_dir = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
    icon_path = base_dir / "app_icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    settings = QSettings("StorageCleaner", "StorageCleaner")

    # First-run setup wizard
    if not settings.value("setup/completed", False, type=bool):
        wizard = SetupWizard(settings)
        if wizard.exec() != wizard.Accepted:
            sys.exit(0)

    # Read saved settings
    selected_drives_str = settings.value("setup/selected_drives", "", type=str)
    drive_list = [d.strip() for d in selected_drives_str.split(",") if d.strip()]
    user_name = settings.value("setup/user_name", "", type=str)

    # Fallback: if no drives configured, use system drive
    if not drive_list:
        sys_drive = os.environ.get("SystemDrive", "C:")[:1]
        drive_list = [sys_drive]

    win = MainWindow(selected_drives=drive_list, user_name=user_name)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
