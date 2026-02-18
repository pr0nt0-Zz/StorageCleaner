from typing import Dict, List

from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QWidget, QLineEdit, QScrollArea,
    QCheckBox, QFrame
)

from core.utils import detect_all_drives, human_bytes


class SetupWizard(QDialog):
    """
    First-run setup wizard. Shown before MainWindow when
    QSettings 'setup/completed' is not True.
    """

    def __init__(self, settings: QSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.selected_drives: List[str] = []
        self.user_name: str = ""
        self._drive_checkboxes: Dict[str, QCheckBox] = {}

        self.setWindowTitle("StorageCleaner - Setup")
        self.setMinimumSize(620, 500)
        self.setModal(True)

        main_layout = QVBoxLayout(self)

        # Step indicator
        self.step_label = QLabel("Step 1 of 4")
        self.step_label.setAlignment(Qt.AlignCenter)
        self.step_label.setStyleSheet("font-size: 12px; color: #888; margin-bottom: 4px;")
        main_layout.addWidget(self.step_label)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #ccc;")
        main_layout.addWidget(sep)

        # Stacked pages
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_welcome_page())
        self.stack.addWidget(self._build_profile_page())
        self.stack.addWidget(self._build_drives_page())
        self.stack.addWidget(self._build_done_page())
        main_layout.addWidget(self.stack)

        # Navigation buttons
        nav = QHBoxLayout()
        self.btn_back = QPushButton("Back")
        self.btn_next = QPushButton("Get Started")
        self.btn_back.clicked.connect(self._go_back)
        self.btn_next.clicked.connect(self._go_next)
        self.btn_next.setStyleSheet("font-weight: bold; padding: 6px 20px;")
        nav.addStretch()
        nav.addWidget(self.btn_back)
        nav.addWidget(self.btn_next)
        main_layout.addLayout(nav)

        self._update_nav()

    # ---- Page Builders ----

    def _build_welcome_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addStretch()

        title = QLabel("StorageCleaner")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: bold; color: #1e73d2;")
        layout.addWidget(title)

        subtitle = QLabel("Your all-in-one Windows storage management utility")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-size: 14px; color: #555; margin-bottom: 16px;")
        layout.addWidget(subtitle)

        features = QLabel(
            "<ul style='font-size: 13px; line-height: 1.8;'>"
            "<li><b>Cleaner</b> - Remove temp files, browser caches, and Recycle Bin</li>"
            "<li><b>Installed Apps</b> - View and uninstall Windows applications</li>"
            "<li><b>Drive Analyzer</b> - Find the largest files and folders on your drives</li>"
            "<li><b>Smart Advisor</b> - Detect stale, unused large files with risk scoring</li>"
            "</ul>"
        )
        features.setWordWrap(True)
        layout.addWidget(features)

        hint = QLabel("Let's set up StorageCleaner for your system.")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("font-size: 12px; color: #888; margin-top: 12px;")
        layout.addWidget(hint)

        layout.addStretch()
        return w

    def _build_profile_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addStretch()

        header = QLabel("What should we call you?")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        desc = QLabel("This is used for personalization only. You can leave it blank.")
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("color: #666; margin-bottom: 12px;")
        layout.addWidget(desc)

        input_row = QHBoxLayout()
        input_row.addStretch()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Your name")
        self.name_input.setMaximumWidth(300)
        self.name_input.setStyleSheet("font-size: 14px; padding: 6px;")
        input_row.addWidget(self.name_input)
        input_row.addStretch()
        layout.addLayout(input_row)

        layout.addStretch()
        return w

    def _build_drives_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        header = QLabel("Select drives to manage")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        desc = QLabel("StorageCleaner detected the following drives on your system.\n"
                       "Select which ones you want to scan and manage.")
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("color: #666; margin-bottom: 8px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Scrollable drive list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #ccc; }")
        scroll_content = QWidget()
        self.drives_layout = QVBoxLayout(scroll_content)

        detected = detect_all_drives()

        if not detected:
            no_drives = QLabel("No drives detected on this system.")
            no_drives.setStyleSheet("color: red; font-weight: bold; padding: 20px;")
            no_drives.setAlignment(Qt.AlignCenter)
            self.drives_layout.addWidget(no_drives)
        else:
            for drive in detected:
                letter = drive["letter"]
                total = human_bytes(drive["total"])
                used = human_bytes(drive["used"])
                free = human_bytes(drive["free"])

                pct = int((drive["used"] / max(drive["total"], 1)) * 100)

                cb = QCheckBox(
                    f"  {letter}:     Total: {total}  |  Used: {used} ({pct}%)  |  Free: {free}"
                )
                cb.setChecked(True)
                cb.setStyleSheet("font-size: 12px; padding: 6px 4px;")
                self._drive_checkboxes[letter] = cb
                self.drives_layout.addWidget(cb)

        self.drives_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Warning label (hidden by default)
        self.drive_warning = QLabel("Please select at least one drive.")
        self.drive_warning.setStyleSheet("color: red; font-weight: bold;")
        self.drive_warning.setAlignment(Qt.AlignCenter)
        self.drive_warning.setVisible(False)
        layout.addWidget(self.drive_warning)

        return w

    def _build_done_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addStretch()

        header = QLabel("You're all set!")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("font-size: 22px; font-weight: bold; color: #1e73d2;")
        layout.addWidget(header)

        self.summary_label = QLabel("")
        self.summary_label.setAlignment(Qt.AlignCenter)
        self.summary_label.setStyleSheet("font-size: 13px; margin: 16px; line-height: 1.6;")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        hint = QLabel("You can change these settings later from Help > Run Setup Wizard.")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(hint)

        layout.addStretch()
        return w

    # ---- Navigation ----

    def _update_nav(self):
        idx = self.stack.currentIndex()
        self.step_label.setText(f"Step {idx + 1} of 4")
        self.btn_back.setVisible(idx > 0)
        if idx == 3:
            self.btn_next.setText("Finish")
        elif idx == 0:
            self.btn_next.setText("Get Started")
        else:
            self.btn_next.setText("Next")

    def _go_back(self):
        idx = self.stack.currentIndex()
        if idx > 0:
            self.stack.setCurrentIndex(idx - 1)
            self._update_nav()

    def _go_next(self):
        idx = self.stack.currentIndex()

        if idx == 1:
            self.user_name = self.name_input.text().strip()

        if idx == 2:
            self.selected_drives = [
                letter for letter, cb in self._drive_checkboxes.items()
                if cb.isChecked()
            ]
            if not self.selected_drives:
                self.drive_warning.setVisible(True)
                return
            self.drive_warning.setVisible(False)
            self._populate_summary()

        if idx == 3:
            self._save_and_finish()
            return

        self.stack.setCurrentIndex(idx + 1)
        self._update_nav()

    def _populate_summary(self):
        name_display = self.user_name or "(not set)"
        drives_display = ", ".join(f"{d}:" for d in sorted(self.selected_drives))
        self.summary_label.setText(
            f"<b>Name:</b> {name_display}<br><br>"
            f"<b>Managed drives:</b> {drives_display}<br><br>"
            "Click <b>Finish</b> to launch StorageCleaner."
        )

    def _save_and_finish(self):
        self.settings.setValue("setup/completed", True)
        self.settings.setValue("setup/user_name", self.user_name)
        self.settings.setValue("setup/selected_drives",
                               ",".join(sorted(self.selected_drives)))
        self.accept()

    # ---- Public accessors ----

    def get_selected_drives(self) -> List[str]:
        return sorted(self.selected_drives)

    def get_user_name(self) -> str:
        return self.user_name
