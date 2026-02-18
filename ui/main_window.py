import platform
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QThread, Signal, QSettings
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QWidget, QMainWindow, QTabWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit, QCheckBox,
    QMessageBox, QLineEdit, QGroupBox, QComboBox, QMenuBar, QTextBrowser
)

from core.utils import human_bytes, is_admin, drive_exists, drive_usage, open_in_explorer, size_class, score_label, confidence_label, recommendation_color, get_logger, LOG_FILE
from core.targets import CleanTarget, get_clean_targets
from core.cleaner import folder_size_bytes, delete_contents, empty_recycle_bin
from core.apps import list_installed_apps
from core.drive_scan import top_largest_folders, top_largest_files
from core.ml_advisor import ml_scan, ScanResult
from core.file_categories import CATEGORIES
from core.chatbot import get_response as chatbot_response, get_welcome_message
from core.platform_utils import (
    IS_WINDOWS, IS_LINUX,
    get_elevation_hint, get_trash_label,
    detect_all_storage, storage_exists, get_storage_path, storage_usage,
    open_in_file_manager, open_text_file, open_system_apps_settings,
)

logger = get_logger("StorageCleaner.ui")

# -------------------------
# Workers
# -------------------------
class ScanWorker(QThread):
    progress = Signal(int)
    log = Signal(str)
    result = Signal(dict)

    def __init__(self, targets: List[CleanTarget]):
        super().__init__()
        self.targets = targets

    def run(self):
        sizes = {}
        n = len(self.targets)
        for i, t in enumerate(self.targets):
            if t.kind == "folder" and t.path:
                self.log.emit(f"Scanning: {t.title} -> {t.path}")
                sizes[t.key] = folder_size_bytes(t.path)
            else:
                sizes[t.key] = 0
            self.progress.emit(int(((i + 1) / max(n, 1)) * 100))
        self.result.emit(sizes)

class CleanWorker(QThread):
    progress = Signal(int)
    log = Signal(str)
    done = Signal(dict)

    def __init__(self, targets: List[CleanTarget], selected_keys: List[str]):
        super().__init__()
        self.targets = targets
        self.selected = set(selected_keys)

    def run(self):
        results = {}
        chosen = [t for t in self.targets if t.key in self.selected]
        n = len(chosen)

        for i, t in enumerate(chosen):
            if t.kind == "folder" and t.path:
                self.log.emit(f"Cleaning: {t.title} -> {t.path}")
                df, dd, err = delete_contents(t.path)
                results[t.key] = {"ok": True, "deleted_files": df, "deleted_dirs": dd, "errors": err}
            elif t.kind == "action" and t.action:
                self.log.emit(f"Running action: {t.title}")
                ok, msg = t.action()
                results[t.key] = {"ok": ok, "message": msg}
            else:
                results[t.key] = {"ok": False, "message": "No handler."}

            self.progress.emit(int(((i + 1) / max(n, 1)) * 100))

        self.done.emit(results)

class AppsWorker(QThread):
    done = Signal(list)
    fail = Signal(str)

    def run(self):
        try:
            apps = list_installed_apps()
            self.done.emit(apps)
        except Exception as e:
            self.fail.emit(str(e))

class DriveScanWorker(QThread):
    progress = Signal(int)
    log = Signal(str)
    done = Signal(list)

    def __init__(self, root: str, mode: str, top_n: int, depth: int):
        super().__init__()
        self.root = root
        self.mode = mode  # "folders" or "files"
        self.top_n = top_n
        self.depth = depth

    def run(self):
        self.log.emit(f"Drive scan started: {self.root} mode={self.mode} top={self.top_n} depth={self.depth}")

        # No fine-grained progress here; depth-limited scan. We'll set 20% start, 100% end.
        self.progress.emit(20)
        root_path = Path(self.root)

        if self.mode == "folders":
            rows = top_largest_folders(root_path, top_n=self.top_n, max_depth=self.depth)
        else:
            rows = top_largest_files(root_path, top_n=self.top_n, max_depth=max(self.depth, 3))

        self.progress.emit(100)
        self.done.emit(rows)

class DriveDeleteWorker(QThread):
    progress = Signal(int)
    log = Signal(str)
    done = Signal(list)  # list of {"path": str, "ok": bool, "message": str}

    def __init__(self, paths: List[str], mode: str):
        super().__init__()
        self.paths = paths
        self.mode = mode  # "files" or "folders"

    def run(self):
        results = []
        n = len(self.paths)
        for i, p in enumerate(self.paths):
            target = Path(p)
            try:
                if self.mode == "files":
                    self.log.emit(f"Deleting file: {p}")
                    logger.info(f"DELETE_FILE: {p}")
                    target.unlink(missing_ok=True)
                    results.append({"path": p, "ok": True, "message": "Deleted"})
                else:
                    self.log.emit(f"Deleting folder: {p}")
                    logger.info(f"DELETE_FOLDER: {p}")
                    shutil.rmtree(target, ignore_errors=True)
                    results.append({"path": p, "ok": True, "message": "Deleted"})
            except Exception as e:
                self.log.emit(f"Failed to delete {p}: {e}")
                logger.warning(f"DELETE_FAILED: {p} - {e}")
                results.append({"path": p, "ok": False, "message": str(e)})
            self.progress.emit(int(((i + 1) / max(n, 1)) * 100))
        self.done.emit(results)

class MLAdvisorWorker(QThread):
    progress = Signal(int)
    log = Signal(str)
    done = Signal(object)   # ScanResult

    def __init__(self, root: str, min_size_mb: int):
        super().__init__()
        self.root = root
        self.min_size_mb = min_size_mb

    def run(self):
        self.log.emit(f"AI Advisor scan: {self.root} (min {self.min_size_mb} MB)")
        result = ml_scan(
            self.root,
            min_size_mb=self.min_size_mb,
            progress_cb=lambda pct: self.progress.emit(pct),
        )
        self.log.emit(f"Found {len(result.files)} file(s), {result.duplicates_found} duplicate group(s)")
        self.done.emit(result)

# -------------------------
# Main Window
# -------------------------
class MainWindow(QMainWindow):
    def __init__(self, selected_storage: List[str] = None, user_name: str = ""):
        super().__init__()
        self.setWindowTitle("StorageCleaner - Storage Management")
        self.resize(1100, 720)

        self.settings = QSettings("StorageCleaner", "StorageCleaner")
        self.selected_storage = selected_storage or (["C"] if IS_WINDOWS else ["root"])
        self.user_name = user_name

        # Build a label map from detected storage
        self._storage_label_map: Dict[str, str] = {}
        self._storage_path_map: Dict[str, str] = {}
        self._refresh_storage_maps()

        self.targets: List[CleanTarget] = get_clean_targets(empty_recycle_bin)
        self.sizes: Dict[str, int] = {}
        self._apps_cache: List[Dict[str, str]] = []
        self._drive_scan_mode: str = "files"

        tabs = QTabWidget()
        tabs.addTab(self._build_cleaner_tab(), "Cleaner")
        tabs.addTab(self._build_apps_tab(), "Installed Apps")
        tabs.addTab(self._build_drives_tab(), "Storage")
        tabs.addTab(self._build_advisor_tab(), "AI Advisor")
        tabs.addTab(self._build_chatbot_tab(), "Chatbot")

        self.setCentralWidget(tabs)
        self._build_menu_bar()
        self._build_status_bar()
        self._update_admin_banner()
        self._load_settings()

    def _refresh_storage_maps(self):
        all_storage = detect_all_storage()
        self._storage_label_map = {s["id"]: s["label"] for s in all_storage}
        self._storage_path_map = {s["id"]: s["path"] for s in all_storage}

    def _get_storage_label(self, sid: str) -> str:
        return self._storage_label_map.get(sid, sid)

    def _get_storage_path(self, sid: str) -> str:
        return self._storage_path_map.get(sid, get_storage_path(sid))

    # -------------------------
    # Cleaner Tab
    # -------------------------
    def _build_cleaner_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        self.admin_label = QLabel("")
        layout.addWidget(self.admin_label)

        dash = QGroupBox("Dashboard")
        dash_l = QHBoxLayout(dash)
        self.lbl_total = QLabel("Total reclaimable: —")
        self.lbl_selected = QLabel("Selected reclaimable: —")
        self.lbl_last = QLabel("Last run: —")
        for x in (self.lbl_total, self.lbl_selected, self.lbl_last):
            x.setStyleSheet("font-weight: 600;")
        dash_l.addWidget(self.lbl_total)
        dash_l.addWidget(self.lbl_selected)
        dash_l.addWidget(self.lbl_last)
        layout.addWidget(dash)

        self.targets_table = QTableWidget(0, 6)
        self.targets_table.setHorizontalHeaderLabels(["Select", "Category", "Path / Action", "Size", "Admin?", "Status"])
        self.targets_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.targets_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.targets_table.setAlternatingRowColors(True)
        layout.addWidget(self.targets_table)

        btn_row = QHBoxLayout()
        self.scan_btn = QPushButton("Scan")
        self.clean_btn = QPushButton("Clean Selected")
        self.clean_btn.setEnabled(False)
        btn_row.addWidget(self.scan_btn)
        btn_row.addWidget(self.clean_btn)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        btn_row.addWidget(self.progress)
        layout.addLayout(btn_row)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        layout.addWidget(self.log_box)

        self.scan_btn.clicked.connect(self._handle_scan)
        self.clean_btn.clicked.connect(self._handle_clean)

        self._populate_targets_table()
        return w

    def _update_admin_banner(self):
        greeting = f"Welcome, {self.user_name}!  |  " if self.user_name else ""
        hint = get_elevation_hint()
        if is_admin():
            self.admin_label.setText(
                f"{greeting}Running as Admin: YES (system cleaning enabled)"
            )
        else:
            self.admin_label.setText(
                f"{greeting}Running as Admin: NO (some system folders may fail; {hint})"
            )
        self.admin_label.setStyleSheet("font-weight: 600;")

    def _load_settings(self):
        safe_mode = self.settings.value("apps/safe_mode", True, type=bool)
        self.cb_safe_mode.setChecked(safe_mode)

        adv_size_index = self.settings.value("advisor/min_size_index", 2, type=int)
        if 0 <= adv_size_index < self.adv_size_combo.count():
            self.adv_size_combo.setCurrentIndex(adv_size_index)

        width = self.settings.value("window/width", 1100, type=int)
        height = self.settings.value("window/height", 720, type=int)
        self.resize(width, height)

    def _save_settings(self):
        self.settings.setValue("apps/safe_mode", self.cb_safe_mode.isChecked())
        self.settings.setValue("advisor/min_size_index", self.adv_size_combo.currentIndex())
        self.settings.setValue("window/width", self.width())
        self.settings.setValue("window/height", self.height())

    def closeEvent(self, event):
        self._save_settings()
        super().closeEvent(event)

    def _build_menu_bar(self):
        menu_bar = self.menuBar()

        help_menu = menu_bar.addMenu("Help")

        guide_action = help_menu.addAction("User Guide")
        guide_action.triggered.connect(self._show_user_guide)

        help_menu.addSeparator()

        setup_action = help_menu.addAction("Run Setup Wizard...")
        setup_action.triggered.connect(self._rerun_setup_wizard)

        help_menu.addSeparator()

        about_action = help_menu.addAction("About StorageCleaner")
        about_action.triggered.connect(self._show_about)

        log_action = help_menu.addAction("Open Log File")
        log_action.triggered.connect(self._open_log_file)

        log_folder_action = help_menu.addAction("Open Log Folder")
        log_folder_action.triggered.connect(self._open_log_folder)

    def _show_user_guide(self):
        from ui.user_guide import UserGuideDialog
        dlg = UserGuideDialog(parent=self)
        dlg.exec()

    def _show_about(self):
        trash = get_trash_label()
        os_info = f"{platform.system()} {platform.release()}"
        QMessageBox.about(
            self, "About StorageCleaner",
            "<h3>StorageCleaner v1.2</h3>"
            f"<p>A cross-platform storage management and disk cleaning utility.</p>"
            f"<p>Running on: {os_info}</p>"
            "<p><b>Features:</b></p>"
            "<ul>"
            f"<li><b>Cleaner</b> - Remove temp files, browser caches, and {trash} contents</li>"
            "<li><b>Installed Apps</b> - View and manage installed applications</li>"
            "<li><b>Storage</b> - Scan and identify the largest files and folders</li>"
            "<li><b>AI Advisor</b> - ML-powered file analysis with duplicate detection and safety scoring</li>"
            "<li><b>Chatbot</b> - In-app assistant to help you use StorageCleaner</li>"
            "</ul>"
            "<p><b>Tips:</b></p>"
            "<ul>"
            f"<li>Run with elevated privileges for full system cleaning ({get_elevation_hint()})</li>"
            "<li>Close browsers before cleaning their caches for best results</li>"
            "<li>All deletions are permanent - review carefully before confirming</li>"
            "<li>Check the log file (Help > Open Log File) for a full audit trail</li>"
            "</ul>"
            f"<p><small>Log file: {LOG_FILE}</small></p>"
        )

    def _open_log_file(self):
        try:
            if LOG_FILE.exists():
                open_text_file(str(LOG_FILE))
            else:
                QMessageBox.information(self, "No log yet", f"Log file does not exist yet:\n{LOG_FILE}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open log file: {e}")

    def _open_log_folder(self):
        open_in_file_manager(str(LOG_FILE.parent))

    def _populate_targets_table(self):
        self.targets_table.setRowCount(0)
        for t in self.targets:
            r = self.targets_table.rowCount()
            self.targets_table.insertRow(r)

            cb = QCheckBox()
            cb.stateChanged.connect(self._update_selected_total)
            self.targets_table.setCellWidget(r, 0, cb)

            it = QTableWidgetItem(t.title)
            it.setData(Qt.UserRole, t.key)
            self.targets_table.setItem(r, 1, it)

            if t.kind == "folder":
                self.targets_table.setItem(r, 2, QTableWidgetItem(str(t.path)))
            else:
                self.targets_table.setItem(r, 2, QTableWidgetItem("Action"))

            self.targets_table.setItem(r, 3, QTableWidgetItem("—"))
            self.targets_table.setItem(r, 4, QTableWidgetItem("YES" if t.requires_admin else "NO"))
            self.targets_table.setItem(r, 5, QTableWidgetItem("Idle"))

    def _log(self, msg: str):
        self.log_box.append(msg)

    def _key_kind(self, key: str) -> str:
        for t in self.targets:
            if t.key == key:
                return t.kind
        return "folder"

    def _selected_keys(self) -> List[str]:
        keys = []
        for r in range(self.targets_table.rowCount()):
            cb = self.targets_table.cellWidget(r, 0)
            if cb and cb.isChecked():
                key = self.targets_table.item(r, 1).data(Qt.UserRole)
                keys.append(key)
        return keys

    def _set_row_status(self, key: str, status: str):
        for r in range(self.targets_table.rowCount()):
            if self.targets_table.item(r, 1).data(Qt.UserRole) == key:
                self.targets_table.setItem(r, 5, QTableWidgetItem(status))
                return

    def _update_selected_total(self):
        if not self.sizes:
            self.lbl_selected.setText("Selected reclaimable: —")
            return
        total = 0
        for r in range(self.targets_table.rowCount()):
            cb = self.targets_table.cellWidget(r, 0)
            if cb and cb.isChecked():
                key = self.targets_table.item(r, 1).data(Qt.UserRole)
                total += int(self.sizes.get(key, 0))
        self.lbl_selected.setText(f"Selected reclaimable: {human_bytes(total)}")

    def _handle_scan(self):
        self.scan_btn.setEnabled(False)
        self.clean_btn.setEnabled(False)
        self.progress.setValue(0)
        self._log("=== Scan started ===")

        self.scan_worker = ScanWorker(self.targets)
        self.scan_worker.log.connect(self._log)
        self.scan_worker.progress.connect(self.progress.setValue)
        self.scan_worker.result.connect(self._on_scan_done)
        self.scan_worker.finished.connect(lambda: self.scan_btn.setEnabled(True))
        self.scan_worker.start()

    def _on_scan_done(self, sizes: dict):
        self.sizes = sizes
        total = 0
        for r in range(self.targets_table.rowCount()):
            key = self.targets_table.item(r, 1).data(Qt.UserRole)
            sz = int(self.sizes.get(key, 0))
            total += sz
            if self._key_kind(key) == "action":
                self.targets_table.setItem(r, 3, QTableWidgetItem("—"))
            else:
                self.targets_table.setItem(r, 3, QTableWidgetItem(human_bytes(sz)))
            self.targets_table.setItem(r, 5, QTableWidgetItem("Scanned"))

        self.lbl_total.setText(f"Total reclaimable: {human_bytes(total)}")
        self._update_selected_total()
        self.lbl_last.setText("Last run: Scan completed")
        self._log(f"=== Scan done. Estimated reclaimable: {human_bytes(total)} ===")
        self.clean_btn.setEnabled(True)

    def _handle_clean(self):
        keys = self._selected_keys()
        if not keys:
            QMessageBox.information(self, "Nothing selected", "Select at least one category to clean.")
            return

        # warn about admin-required targets
        needs_admin = [t.title for t in self.targets if t.key in keys and t.requires_admin]
        if needs_admin and not is_admin():
            hint = get_elevation_hint()
            QMessageBox.warning(
                self, "Admin recommended",
                "Some selected items may fail without admin:\n- " + "\n- ".join(needs_admin) +
                f"\n\nTip: Close app and re-run with elevated privileges ({hint})."
            )

        resp = QMessageBox.question(
            self, "Confirm clean",
            "This will delete temp/cache contents for selected categories.\n\n"
            "Tip: Close browsers (Chrome/Edge/Firefox) for best cache cleanup.\n\nProceed?",
            QMessageBox.Yes | QMessageBox.No
        )
        if resp != QMessageBox.Yes:
            return

        self.scan_btn.setEnabled(False)
        self.clean_btn.setEnabled(False)
        self.progress.setValue(0)
        self._log("=== Clean started ===")

        for k in keys:
            self._set_row_status(k, "Cleaning...")

        self.clean_worker = CleanWorker(self.targets, keys)
        self.clean_worker.log.connect(self._log)
        self.clean_worker.progress.connect(self.progress.setValue)
        self.clean_worker.done.connect(self._on_clean_done)
        self.clean_worker.finished.connect(lambda: self.scan_btn.setEnabled(True))
        self.clean_worker.start()

    def _on_clean_done(self, results: dict):
        ok_count = 0
        fail_count = 0

        for key, info in results.items():
            if info.get("ok"):
                ok_count += 1
                self._set_row_status(key, "Cleaned")
                if "deleted_files" in info:
                    self._log(f"[OK] {key}: deleted_files={info['deleted_files']} errors={info['errors']}")
                else:
                    self._log(f"[OK] {key}: {info.get('message','')}")
            else:
                fail_count += 1
                self._set_row_status(key, "Failed")
                self._log(f"[FAIL] {key}: {info.get('message','')}")

        self.lbl_last.setText(f"Last run: Clean completed (OK={ok_count}, FAIL={fail_count})")
        self._log(f"=== Clean done. OK={ok_count}, FAIL={fail_count} ===")
        self.clean_btn.setEnabled(True)

        # re-scan to refresh sizes
        self._handle_scan()

    # -------------------------
    # Installed Apps Tab
    # -------------------------
    def _build_apps_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        top = QHBoxLayout()
        self.app_search = QLineEdit()
        self.app_search.setPlaceholderText("Search app name / publisher...")
        self.app_refresh = QPushButton("Refresh List")
        top.addWidget(self.app_search)
        top.addWidget(self.app_refresh)
        layout.addLayout(top)

        btns = QHBoxLayout()
        self.btn_open_settings = QPushButton("Open System Apps Settings")
        self.btn_uninstall = QPushButton("Uninstall Selected")
        self.cb_safe_mode = QCheckBox("Safe mode (view-only)")
        self.cb_safe_mode.setChecked(True)
        btns.addWidget(self.btn_open_settings)
        btns.addWidget(self.btn_uninstall)
        btns.addWidget(self.cb_safe_mode)
        layout.addLayout(btns)

        self.apps_table = QTableWidget(0, 6)
        self.apps_table.setHorizontalHeaderLabels(["Name", "Version", "Publisher", "InstallDate", "Size (est.)", "Uninstall"])
        self.apps_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.apps_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.apps_table.setAlternatingRowColors(True)
        layout.addWidget(self.apps_table)

        if IS_WINDOWS:
            hint_text = "Uninstall safely via Settings > Apps > Installed apps. (Safe mode ON blocks uninstall execution.)"
        else:
            hint_text = "Uninstall column shows the terminal command. Copy and run it in your terminal. (Safe mode ON blocks execution.)"
        hint = QLabel(hint_text)
        hint.setStyleSheet("color: #666;")
        layout.addWidget(hint)

        self.app_refresh.clicked.connect(self._load_apps)
        self.app_search.textChanged.connect(self._filter_apps)
        self.btn_open_settings.clicked.connect(self._open_installed_apps_settings)
        self.btn_uninstall.clicked.connect(self._uninstall_selected_app)

        self._load_apps()
        return w

    def _open_installed_apps_settings(self):
        try:
            open_system_apps_settings()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _load_apps(self):
        self.apps_table.setRowCount(0)
        self.app_refresh.setEnabled(False)
        self.app_refresh.setText("Loading...")

        self.apps_worker = AppsWorker()
        self.apps_worker.done.connect(self._on_apps_loaded)
        self.apps_worker.fail.connect(self._on_apps_failed)
        self.apps_worker.finished.connect(lambda: self._apps_load_finished())
        self.apps_worker.start()

    def _apps_load_finished(self):
        self.app_refresh.setEnabled(True)
        self.app_refresh.setText("Refresh List")

    def _on_apps_failed(self, err: str):
        QMessageBox.critical(self, "Error", f"Failed to read installed apps:\n{err}")
        self._apps_cache = []

    def _on_apps_loaded(self, apps: list):
        self._apps_cache = apps
        self._render_apps(apps)

    def _render_apps(self, apps: List[Dict[str, str]]):
        self.apps_table.setRowCount(0)
        for a in apps:
            r = self.apps_table.rowCount()
            self.apps_table.insertRow(r)

            name = a.get("DisplayName", "")
            ver = a.get("DisplayVersion", "")
            pub = a.get("Publisher", "")
            date = a.get("InstallDate", "")
            size = a.get("EstimatedSize", "")
            uninst = a.get("UninstallString", "")

            size_str = ""
            if size.isdigit():
                try:
                    kb = int(size)
                    size_str = human_bytes(kb * 1024)
                except Exception:
                    size_str = size
            else:
                size_str = size or ""

            values = [name, ver, pub, date, size_str, uninst]
            for c, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                self.apps_table.setItem(r, c, item)

    def _filter_apps(self, text: str):
        q = text.strip().lower()
        if not q:
            self._render_apps(self._apps_cache)
            return
        filtered = []
        for a in self._apps_cache:
            blob = (a.get("DisplayName", "") + " " + a.get("Publisher", "")).lower()
            if q in blob:
                filtered.append(a)
        self._render_apps(filtered)

    def _uninstall_selected_app(self):
        if self.cb_safe_mode.isChecked():
            QMessageBox.information(self, "Safe mode", "Safe mode is ON (view-only). Turn it OFF to enable uninstall.")
            return

        row = self.apps_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select an app", "Click an app row first.")
            return

        name = self.apps_table.item(row, 0).text()
        uninstall_str = (self.apps_table.item(row, 5).text() or "").strip()

        if not uninstall_str:
            QMessageBox.warning(self, "No uninstall command", "This app has no uninstall command available.")
            return

        if IS_LINUX:
            # On Linux, show the command for the user to run in terminal
            QMessageBox.information(
                self, "Uninstall Command",
                f"To uninstall <b>{name}</b>, run this command in your terminal:\n\n"
                f"<code>{uninstall_str}</code>\n\n"
                "Copy the command above and paste it into a terminal window."
            )
            return

        # Windows: validate and execute
        cmd = uninstall_str
        low = cmd.lower()

        dangerous_patterns = ["format ", "del /", "rd /s", "rmdir /s", "powershell", "curl ", "wget ",
                              "invoke-", "iex ", "downloadstring", "net user", "reg delete", "shutdown"]
        for pattern in dangerous_patterns:
            if pattern in low:
                logger.warning(f"BLOCKED uninstall command for '{name}': contains '{pattern}' -> {cmd}")
                QMessageBox.warning(
                    self, "Suspicious command blocked",
                    f"The uninstall command for '{name}' contains a suspicious pattern ('{pattern}') "
                    f"and was blocked for safety.\n\nCommand:\n{cmd}\n\n"
                    "You can uninstall this app manually via system settings."
                )
                return

        # MSI best practice: convert install to uninstall if needed
        if "msiexec" in low and " /i" in low:
            cmd = cmd.replace(" /I", " /X").replace(" /i", " /x")

        msg = (
            f"App: {name}\n\n"
            f"Uninstall command:\n{cmd}\n\n"
            "This will launch the vendor uninstaller (may prompt UAC).\nProceed?"
        )
        resp = QMessageBox.question(self, "Confirm uninstall", msg, QMessageBox.Yes | QMessageBox.No)
        if resp != QMessageBox.Yes:
            return

        try:
            logger.info(f"UNINSTALL_START: '{name}' -> {cmd}")
            subprocess.Popen(["cmd", "/c", cmd], shell=False)
            QMessageBox.information(self, "Started", "Uninstaller launched. Follow the prompts.")
        except Exception as e:
            logger.error(f"UNINSTALL_FAILED: '{name}' -> {e}")
            QMessageBox.critical(self, "Failed to launch", str(e))

    # -------------------------
    # Storage Tab
    # -------------------------
    def _build_drives_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        self.drive_info = QLabel("")
        layout.addWidget(self.drive_info)

        # usage refresh
        usage_row = QHBoxLayout()
        self.btn_usage = QPushButton("Refresh Storage Usage")
        usage_row.addWidget(self.btn_usage)
        self.drive_progress = QProgressBar()
        self.drive_progress.setValue(0)
        usage_row.addWidget(self.drive_progress)
        layout.addLayout(usage_row)

        # scan controls
        scan_box = QGroupBox("Storage Analyzer")
        scan_l = QHBoxLayout(scan_box)

        scan_l.addWidget(QLabel("Location:"))
        self.drive_combo = QComboBox()
        self._populate_storage_combo(self.drive_combo)
        scan_l.addWidget(self.drive_combo)

        self.btn_scan_folders = QPushButton("Scan Top Folders")
        self.btn_scan_files = QPushButton("Scan Top Files")
        scan_l.addWidget(self.btn_scan_folders)
        scan_l.addWidget(self.btn_scan_files)
        layout.addWidget(scan_box)

        # delete controls
        delete_row = QHBoxLayout()
        self.cb_drive_select_all = QCheckBox("Select All")
        self.cb_drive_select_all.stateChanged.connect(self._toggle_drive_select_all)
        self.btn_drive_delete = QPushButton("Delete Selected")
        self.btn_drive_delete.setStyleSheet("color: red; font-weight: bold;")
        delete_row.addWidget(self.cb_drive_select_all)
        delete_row.addWidget(self.btn_drive_delete)
        delete_row.addStretch()
        layout.addLayout(delete_row)

        # results table
        self.drive_table = QTableWidget(0, 5)
        self.drive_table.setHorizontalHeaderLabels(["Select", "Class", "Size", "Path", "Action"])
        self.drive_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.drive_table.setAlternatingRowColors(True)
        layout.addWidget(self.drive_table)

        self.drive_log = QTextEdit()
        self.drive_log.setReadOnly(True)
        layout.addWidget(self.drive_log)

        self.btn_usage.clicked.connect(self._refresh_drive_usage)
        self.btn_scan_folders.clicked.connect(lambda: self._start_drive_scan_from_combo("folders"))
        self.btn_scan_files.clicked.connect(lambda: self._start_drive_scan_from_combo("files"))
        self.btn_drive_delete.clicked.connect(self._delete_drive_selected)

        self._refresh_drive_usage()
        return w

    def _populate_storage_combo(self, combo: QComboBox):
        combo.clear()
        for sid in self.selected_storage:
            label = self._get_storage_label(sid)
            combo.addItem(label, sid)

    def _start_drive_scan_from_combo(self, mode: str):
        sid = self.drive_combo.currentData()
        if not sid:
            QMessageBox.information(self, "No location", "No storage location selected.")
            return
        path = self._get_storage_path(sid)
        self._start_drive_scan(path, mode)

    def _drive_log(self, msg: str):
        self.drive_log.append(msg)

    def _refresh_drive_usage(self):
        parts = []
        for sid in self.selected_storage:
            if storage_exists(sid):
                path = self._get_storage_path(sid)
                total, used, free = storage_usage(path)
                label = self._get_storage_label(sid)
                parts.append(f"{label}  Total {human_bytes(total)} | Used {human_bytes(used)} | Free {human_bytes(free)}")
            else:
                label = self._get_storage_label(sid)
                parts.append(f"{label}  Not detected")
        self.drive_info.setText("  |  ".join(parts))

    def _start_drive_scan(self, root: str, mode: str):
        # guard: path must exist
        if not Path(root).exists():
            QMessageBox.information(self, "Location not found", f"Storage location not found: {root}")
            return

        # Typical safe defaults
        top_n = 30
        depth = 3 if mode == "folders" else 4

        self._drive_scan_mode = mode
        self.cb_drive_select_all.setChecked(False)
        self.drive_table.setRowCount(0)
        self.drive_progress.setValue(0)

        self.drive_scan_worker = DriveScanWorker(root, mode, top_n=top_n, depth=depth)
        self.drive_scan_worker.log.connect(self._drive_log)
        self.drive_scan_worker.progress.connect(self.drive_progress.setValue)
        self.drive_scan_worker.done.connect(self._on_drive_scan_done)

        self._drive_log(f"=== Running scan on {root} ({mode}) ===")
        self.drive_scan_worker.start()

    def _on_drive_scan_done(self, rows: list):
        self.drive_table.setRowCount(0)
        for size, path in rows:
            r = self.drive_table.rowCount()
            self.drive_table.insertRow(r)

            cb = QCheckBox()
            self.drive_table.setCellWidget(r, 0, cb)

            cls = size_class(int(size))

            self.drive_table.setItem(r, 1, QTableWidgetItem(cls))
            size_item = QTableWidgetItem(human_bytes(int(size)))
            size_item.setData(Qt.UserRole, int(size))
            self.drive_table.setItem(r, 2, size_item)
            self.drive_table.setItem(r, 3, QTableWidgetItem(path))

            btn = QPushButton("Open")
            btn.clicked.connect(lambda checked=False, p=path: open_in_file_manager(p))
            self.drive_table.setCellWidget(r, 4, btn)

        self._drive_log("=== Scan done ===")

    def _toggle_drive_select_all(self, state):
        checked = state == Qt.Checked.value
        for r in range(self.drive_table.rowCount()):
            cb = self.drive_table.cellWidget(r, 0)
            if cb:
                cb.setChecked(checked)

    def _delete_drive_selected(self):
        paths = []
        total_size = 0
        for r in range(self.drive_table.rowCount()):
            cb = self.drive_table.cellWidget(r, 0)
            if cb and cb.isChecked():
                path = self.drive_table.item(r, 3).text()
                paths.append(path)
                raw_size = self.drive_table.item(r, 2).data(Qt.UserRole)
                if raw_size:
                    total_size += int(raw_size)

        if not paths:
            QMessageBox.information(self, "Nothing selected", "Select at least one item to delete.")
            return

        mode_label = "files" if self._drive_scan_mode == "files" else "folders"
        preview = "\n".join(paths[:10])
        if len(paths) > 10:
            preview += f"\n... and {len(paths) - 10} more"

        resp = QMessageBox.warning(
            self, "Confirm deletion",
            f"You are about to permanently delete {len(paths)} {mode_label} "
            f"(~{human_bytes(total_size)}):\n\n"
            f"{preview}\n\n"
            "This action cannot be undone. Proceed?",
            QMessageBox.Yes | QMessageBox.No
        )
        if resp != QMessageBox.Yes:
            return

        self.btn_drive_delete.setEnabled(False)
        self.drive_progress.setValue(0)
        self._drive_log(f"=== Deleting {len(paths)} {mode_label} ===")

        self.drive_delete_worker = DriveDeleteWorker(paths, self._drive_scan_mode)
        self.drive_delete_worker.log.connect(self._drive_log)
        self.drive_delete_worker.progress.connect(self.drive_progress.setValue)
        self.drive_delete_worker.done.connect(self._on_drive_delete_done)
        self.drive_delete_worker.start()

    def _on_drive_delete_done(self, results: list):
        ok_count = 0
        fail_count = 0
        deleted_paths = set()

        for item in results:
            if item["ok"]:
                ok_count += 1
                deleted_paths.add(item["path"])
                self._drive_log(f"[OK] Deleted: {item['path']}")
            else:
                fail_count += 1
                self._drive_log(f"[FAIL] {item['path']}: {item['message']}")

        # Remove deleted rows from table (iterate in reverse to preserve indices)
        for r in range(self.drive_table.rowCount() - 1, -1, -1):
            path = self.drive_table.item(r, 3).text()
            if path in deleted_paths:
                self.drive_table.removeRow(r)

        self.cb_drive_select_all.setChecked(False)
        self.btn_drive_delete.setEnabled(True)
        self._drive_log(f"=== Delete done. OK={ok_count}, FAIL={fail_count} ===")
        self._refresh_drive_usage()

    # -------------------------
    # AI Advisor Tab
    # -------------------------
    def _build_advisor_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # Controls row
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Min file size:"))
        self.adv_size_combo = QComboBox()
        self.adv_size_combo.addItems(["10 MB", "25 MB", "50 MB", "100 MB", "250 MB", "500 MB"])
        self.adv_size_combo.setCurrentIndex(2)  # default 50 MB
        ctrl.addWidget(self.adv_size_combo)

        ctrl.addWidget(QLabel("Location:"))
        self.adv_drive_combo = QComboBox()
        self._populate_storage_combo(self.adv_drive_combo)
        ctrl.addWidget(self.adv_drive_combo)

        self.btn_adv_scan = QPushButton("AI Scan")
        self.btn_adv_scan.setStyleSheet("font-weight: bold;")
        ctrl.addWidget(self.btn_adv_scan)
        layout.addLayout(ctrl)

        # Category filter row
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter by category:"))
        self.adv_cat_filter = QComboBox()
        self._populate_category_filter()
        filter_row.addWidget(self.adv_cat_filter)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # Dashboard
        self.adv_dashboard = QLabel("Scan a storage location to find files safe to delete.")
        self.adv_dashboard.setStyleSheet("font-weight: 600;")
        self.adv_dashboard.setWordWrap(True)
        layout.addWidget(self.adv_dashboard)

        # Progress
        self.adv_progress = QProgressBar()
        self.adv_progress.setValue(0)
        layout.addWidget(self.adv_progress)

        # Select all + select safe + delete row
        action_row = QHBoxLayout()
        self.cb_adv_select_all = QCheckBox("Select All")
        self.cb_adv_select_all.stateChanged.connect(self._toggle_advisor_select_all)
        self.btn_adv_select_safe = QPushButton("Select All Safe")
        self.btn_adv_select_safe.setStyleSheet("color: green; font-weight: bold;")
        self.btn_adv_delete = QPushButton("Delete Selected")
        self.btn_adv_delete.setStyleSheet("color: red; font-weight: bold;")
        action_row.addWidget(self.cb_adv_select_all)
        action_row.addWidget(self.btn_adv_select_safe)
        action_row.addWidget(self.btn_adv_delete)
        action_row.addStretch()
        layout.addLayout(action_row)

        # Results table - 10 columns
        self.adv_table = QTableWidget(0, 10)
        self.adv_table.setHorizontalHeaderLabels([
            "Select", "Score", "AI Recommendation", "Confidence", "Category",
            "Size", "Last Accessed", "Last Modified", "Path", "Reasons"
        ])
        self.adv_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.adv_table.horizontalHeader().setSectionResizeMode(8, QHeaderView.Stretch)
        self.adv_table.horizontalHeader().setSectionResizeMode(9, QHeaderView.Stretch)
        self.adv_table.setAlternatingRowColors(True)
        layout.addWidget(self.adv_table)

        # Log
        self.adv_log_box = QTextEdit()
        self.adv_log_box.setReadOnly(True)
        self.adv_log_box.setMaximumHeight(120)
        layout.addWidget(self.adv_log_box)

        # Store scan result for filtering
        self._adv_scan_result: Optional[ScanResult] = None

        # Connections
        self.btn_adv_scan.clicked.connect(self._start_advisor_scan_from_combo)
        self.btn_adv_delete.clicked.connect(self._delete_advisor_selected)
        self.btn_adv_select_safe.clicked.connect(self._select_all_safe)
        self.adv_cat_filter.currentIndexChanged.connect(self._apply_advisor_filter)

        return w

    def _populate_category_filter(self):
        self.adv_cat_filter.clear()
        self.adv_cat_filter.addItem("All Categories", "all")
        for key, cat in CATEGORIES.items():
            self.adv_cat_filter.addItem(cat.label, key)
        self.adv_cat_filter.addItem("Duplicates Only", "duplicate")

    def _advisor_log(self, msg: str):
        self.adv_log_box.append(msg)

    def _get_adv_min_size_mb(self) -> int:
        text = self.adv_size_combo.currentText()
        if "GB" in text:
            return int(text.replace("GB", "").strip()) * 1024
        return int(text.replace("MB", "").strip())

    def _start_advisor_scan_from_combo(self):
        sid = self.adv_drive_combo.currentData()
        if not sid:
            QMessageBox.information(self, "No location", "No storage location selected.")
            return
        path = self._get_storage_path(sid)
        self._start_advisor_scan(path)

    def _start_advisor_scan(self, root: str):
        if not Path(root).exists():
            QMessageBox.information(self, "Location not found", f"Storage location not found: {root}")
            return

        min_size_mb = self._get_adv_min_size_mb()
        self.adv_table.setRowCount(0)
        self.adv_progress.setValue(0)
        self.cb_adv_select_all.setChecked(False)
        self.adv_dashboard.setText("AI scanning... this may take a while.")
        self.btn_adv_scan.setEnabled(False)

        self.advisor_worker = MLAdvisorWorker(root, min_size_mb)
        self.advisor_worker.log.connect(self._advisor_log)
        self.advisor_worker.progress.connect(self.adv_progress.setValue)
        self.advisor_worker.done.connect(self._on_advisor_scan_done)
        self.advisor_worker.finished.connect(self._advisor_scan_finished)

        self._advisor_log(f"=== AI Advisor scan: {root} (min {min_size_mb} MB) ===")
        self.advisor_worker.start()

    def _advisor_scan_finished(self):
        self.btn_adv_scan.setEnabled(True)

    def _on_advisor_scan_done(self, result: ScanResult):
        self._adv_scan_result = result
        self._render_advisor_table(result.files)

        # Build dashboard summary
        parts = [f"Found {len(result.files)} file(s)"]
        parts.append(f"Total reclaimable: {human_bytes(result.total_reclaimable)}")
        if result.duplicates_found > 0:
            parts.append(f"Duplicates: {result.duplicates_found} group(s) ({human_bytes(result.duplicate_space_reclaimable)})")

        # Category breakdown
        cat_parts = []
        for cat_key, info in result.category_summary.items():
            cat_label = CATEGORIES.get(cat_key, CATEGORIES.get("large_unused")).label
            cat_parts.append(f"{cat_label}: {info['count']} ({human_bytes(info['size'])})")
        if cat_parts:
            parts.append("  |  ".join(cat_parts))

        self.adv_dashboard.setText("  |  ".join(parts[:3]) + ("\n" + parts[3] if len(parts) > 3 else ""))
        self._advisor_log(f"=== AI scan done. {len(result.files)} files, {human_bytes(result.total_reclaimable)} total ===")

    def _render_advisor_table(self, files):
        self.adv_table.setRowCount(0)

        for item in files:
            r = self.adv_table.rowCount()
            self.adv_table.insertRow(r)

            cb = QCheckBox()
            self.adv_table.setCellWidget(r, 0, cb)

            score_item = QTableWidgetItem(str(item.score))
            rec_item = QTableWidgetItem(item.recommendation)
            conf_item = QTableWidgetItem(confidence_label(item.confidence))
            cat_label = CATEGORIES.get(item.category, CATEGORIES.get("large_unused")).label
            cat_item = QTableWidgetItem(cat_label)
            size_item = QTableWidgetItem(human_bytes(item.size))
            size_item.setData(Qt.UserRole, item.size)
            accessed_item = QTableWidgetItem(item.accessed)
            modified_item = QTableWidgetItem(item.modified)
            path_item = QTableWidgetItem(item.path)
            reasons_item = QTableWidgetItem(item.reasons)

            # Store safety and category as user data for filtering/selecting
            rec_item.setData(Qt.UserRole, item.safety)
            cat_item.setData(Qt.UserRole, item.category)

            self.adv_table.setItem(r, 1, score_item)
            self.adv_table.setItem(r, 2, rec_item)
            self.adv_table.setItem(r, 3, conf_item)
            self.adv_table.setItem(r, 4, cat_item)
            self.adv_table.setItem(r, 5, size_item)
            self.adv_table.setItem(r, 6, accessed_item)
            self.adv_table.setItem(r, 7, modified_item)
            self.adv_table.setItem(r, 8, path_item)
            self.adv_table.setItem(r, 9, reasons_item)

            # Color-code row based on safety
            bg_hex, fg_hex = recommendation_color(item.safety)
            bg = QBrush(QColor(bg_hex))
            fg = QBrush(QColor(fg_hex))
            for c in range(1, 10):
                cell = self.adv_table.item(r, c)
                if cell:
                    cell.setBackground(bg)
                    cell.setForeground(fg)

    def _apply_advisor_filter(self):
        if not self._adv_scan_result:
            return
        cat_key = self.adv_cat_filter.currentData()
        if cat_key == "all":
            self._render_advisor_table(self._adv_scan_result.files)
        else:
            filtered = [f for f in self._adv_scan_result.files if f.category == cat_key]
            self._render_advisor_table(filtered)

    def _select_all_safe(self):
        """Select only rows marked as SAFE (green)."""
        for r in range(self.adv_table.rowCount()):
            cb = self.adv_table.cellWidget(r, 0)
            rec_item = self.adv_table.item(r, 2)
            if cb and rec_item:
                safety = rec_item.data(Qt.UserRole)
                cb.setChecked(safety == "safe")

    def _toggle_advisor_select_all(self, state):
        checked = state == Qt.Checked.value
        for r in range(self.adv_table.rowCount()):
            cb = self.adv_table.cellWidget(r, 0)
            if cb:
                cb.setChecked(checked)

    def _delete_advisor_selected(self):
        paths = []
        total_size = 0
        for r in range(self.adv_table.rowCount()):
            cb = self.adv_table.cellWidget(r, 0)
            if cb and cb.isChecked():
                path = self.adv_table.item(r, 8).text()
                paths.append(path)
                raw_size = self.adv_table.item(r, 5).data(Qt.UserRole)
                if raw_size:
                    total_size += int(raw_size)

        if not paths:
            QMessageBox.information(self, "Nothing selected", "Select at least one file to delete.")
            return

        preview = "\n".join(paths[:10])
        if len(paths) > 10:
            preview += f"\n... and {len(paths) - 10} more"

        resp = QMessageBox.warning(
            self, "Confirm deletion",
            f"You are about to permanently delete {len(paths)} file(s) "
            f"(~{human_bytes(total_size)}):\n\n"
            f"{preview}\n\n"
            "This action cannot be undone. Proceed?",
            QMessageBox.Yes | QMessageBox.No
        )
        if resp != QMessageBox.Yes:
            return

        self.btn_adv_delete.setEnabled(False)
        self.adv_progress.setValue(0)
        self._advisor_log(f"=== Deleting {len(paths)} file(s) ===")

        self.adv_delete_worker = DriveDeleteWorker(paths, "files")
        self.adv_delete_worker.log.connect(self._advisor_log)
        self.adv_delete_worker.progress.connect(self.adv_progress.setValue)
        self.adv_delete_worker.done.connect(self._on_advisor_delete_done)
        self.adv_delete_worker.start()

    def _on_advisor_delete_done(self, results: list):
        ok_count = 0
        fail_count = 0
        deleted_paths = set()

        for item in results:
            if item["ok"]:
                ok_count += 1
                deleted_paths.add(item["path"])
                self._advisor_log(f"[OK] Deleted: {item['path']}")
            else:
                fail_count += 1
                self._advisor_log(f"[FAIL] {item['path']}: {item['message']}")

        for r in range(self.adv_table.rowCount() - 1, -1, -1):
            path = self.adv_table.item(r, 8).text()
            if path in deleted_paths:
                self.adv_table.removeRow(r)

        self.cb_adv_select_all.setChecked(False)
        self.btn_adv_delete.setEnabled(True)

        # Update dashboard with remaining items
        remaining_count = self.adv_table.rowCount()
        self.adv_dashboard.setText(
            f"{remaining_count} file(s) remaining in review list  |  Deleted: {ok_count}  |  Failed: {fail_count}"
        )
        self._advisor_log(f"=== Delete done. OK={ok_count}, FAIL={fail_count} ===")

    # -------------------------
    # Chatbot Tab
    # -------------------------
    def _build_chatbot_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # Chat display
        self.chat_display = QTextBrowser()
        self.chat_display.setOpenExternalLinks(False)
        self.chat_display.setStyleSheet(
            "QTextBrowser { background-color: #f5f5f5; font-size: 14px; padding: 8px; }"
        )
        layout.addWidget(self.chat_display)

        # Input row
        input_row = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Type your question here...")
        self.chat_input.setStyleSheet("font-size: 14px; padding: 6px;")
        self.chat_input.returnPressed.connect(self._send_chat_message)
        input_row.addWidget(self.chat_input)

        self.btn_chat_send = QPushButton("Send")
        self.btn_chat_send.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        self.btn_chat_send.clicked.connect(self._send_chat_message)
        input_row.addWidget(self.btn_chat_send)
        layout.addLayout(input_row)

        # Quick action buttons
        quick_row = QHBoxLayout()
        quick_row.addWidget(QLabel("Quick:"))
        for label in ["How to clean?", "AI Advisor help", "Storage tips", "What can you do?"]:
            btn = QPushButton(label)
            btn.setStyleSheet("font-size: 12px;")
            btn.clicked.connect(lambda checked, q=label: self._send_quick_question(q))
            quick_row.addWidget(btn)
        quick_row.addStretch()
        layout.addLayout(quick_row)

        # Show welcome message
        self._append_bot_message(get_welcome_message())

        return w

    def _append_bot_message(self, html_content: str):
        self.chat_display.append(
            '<div style="background-color: #d6eaf8; border-radius: 8px; '
            'padding: 10px; margin: 6px 40px 6px 0px;">'
            '<b style="color: #1a5276;">Bot:</b><br>'
            f'{html_content}</div>'
        )
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )

    def _append_user_message(self, text: str):
        from html import escape
        self.chat_display.append(
            '<div style="background-color: #d5f5e3; border-radius: 8px; '
            'padding: 10px; margin: 6px 0px 6px 40px; text-align: right;">'
            '<b style="color: #1e8449;">You:</b><br>'
            f'{escape(text)}</div>'
        )
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )

    def _send_chat_message(self):
        text = self.chat_input.text().strip()
        if not text:
            return
        self.chat_input.clear()
        self._append_user_message(text)
        response = chatbot_response(text)
        self._append_bot_message(response)

    def _send_quick_question(self, question: str):
        self._append_user_message(question)
        response = chatbot_response(question)
        self._append_bot_message(response)

    # -------------------------
    # Status Bar
    # -------------------------
    def _build_status_bar(self):
        self._update_status_bar()

    def _update_status_bar(self):
        labels = [self._get_storage_label(sid) for sid in sorted(self.selected_storage)]
        locations_str = ", ".join(labels)
        total_storage = 0
        for sid in self.selected_storage:
            if storage_exists(sid):
                path = self._get_storage_path(sid)
                total, _, _ = storage_usage(path)
                total_storage += total

        os_info = f"{platform.system()} {platform.release()}"
        msg = (
            f"Managed locations: {locations_str}  |  "
            f"Total storage: {human_bytes(total_storage)}  |  "
            f"OS: {os_info}"
        )
        self.statusBar().showMessage(msg)

    # -------------------------
    # Re-run Setup Wizard
    # -------------------------
    def _rerun_setup_wizard(self):
        from ui.setup_wizard import SetupWizard

        wizard = SetupWizard(self.settings, parent=self)
        # Pre-populate with current settings
        wizard.name_input.setText(self.user_name)
        for sid, cb in wizard._storage_checkboxes.items():
            cb.setChecked(sid in self.selected_storage)

        if wizard.exec() == wizard.Accepted:
            self.selected_storage = wizard.get_selected_storage()
            self.user_name = wizard.get_user_name()

            # Refresh storage maps
            self._refresh_storage_maps()

            # Rebuild combo boxes
            self._populate_storage_combo(self.drive_combo)
            self._populate_storage_combo(self.adv_drive_combo)

            # Refresh UI
            self._update_admin_banner()
            self._refresh_drive_usage()
            self._update_status_bar()
