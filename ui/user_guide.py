"""
In-app User Guide dialog for StorageCleaner.
Shows an HTML-formatted manual with platform-aware content.
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt

from core.platform_utils import IS_WINDOWS, IS_LINUX, get_trash_label, get_elevation_hint


def _build_guide_html() -> str:
    trash = get_trash_label()
    elevate = get_elevation_hint()

    if IS_WINDOWS:
        os_name = "Windows"
        temp_loc = "%TEMP%"
        admin_word = "administrator"
        apps_source = "the Windows Registry"
        uninstall_info = "Click <b>Uninstall</b> to run the app's built-in uninstaller."
        system_apps_info = "Click <b>Open System Apps Settings</b> to open Windows Settings &gt; Apps."
        storage_term = "drives (C:, D:, etc.)"
        file_manager = "File Explorer"
    else:
        os_name = "Linux"
        temp_loc = "/tmp"
        admin_word = "root (sudo)"
        apps_source = "your package manager (dpkg, rpm, Flatpak, Snap)"
        uninstall_info = (
            "The <b>Uninstall</b> column shows the terminal command to remove the package "
            "(e.g. <code>sudo apt remove &lt;pkg&gt;</code>). Copy and run it in your terminal."
        )
        system_apps_info = "Click <b>Open System Apps Settings</b> to launch your software center."
        storage_term = "mount points (/, /home, /mnt/data, etc.)"
        file_manager = "your file manager"

    html = f"""
    <h2 style="color:#1976D2;">StorageCleaner User Guide</h2>
    <p>Welcome to StorageCleaner! This guide covers every tab and feature to help you
    get started quickly.</p>

    <hr>
    <h3 style="color:#1976D2;">1. Cleaner Tab</h3>
    <p>The Cleaner tab lets you scan and delete common junk files to free up space.</p>
    <ul>
      <li><b>Scan</b> &ndash; Click to calculate the size of each clean target
          (temp files, browser caches, {trash}, etc.).</li>
      <li><b>Clean Selected</b> &ndash; Deletes the contents of every checked target.</li>
      <li><b>Targets</b> &ndash; Each row shows a category of cleanable files.
          Check the ones you want to clean.</li>
    </ul>
    <p><b>Tip:</b> Close your browser before cleaning browser caches for best results.</p>
    <p><b>Note:</b> Some targets (like system temp at <code>{temp_loc}</code>) require
    {admin_word} privileges. Items marked with <i>(requires admin)</i> may be skipped
    if you are not elevated. To elevate, {elevate}.</p>

    <hr>
    <h3 style="color:#1976D2;">2. Installed Apps Tab</h3>
    <p>View all applications installed on your system, sourced from {apps_source}.</p>
    <ul>
      <li><b>Search</b> &ndash; Type in the search box to filter apps by name.</li>
      <li><b>Safe Mode</b> &ndash; When enabled, hides system-critical packages to
          prevent accidental removal.</li>
      <li><b>Columns</b> &ndash; Name, Version, Publisher, Size.</li>
    </ul>
    <p>{uninstall_info}</p>
    <p>{system_apps_info}</p>

    <hr>
    <h3 style="color:#1976D2;">3. Storage Tab</h3>
    <p>Explore your {storage_term} to find what's using space.</p>
    <ul>
      <li><b>Location selector</b> &ndash; Choose which storage location to scan
          from the drop-down.</li>
      <li><b>Scan Folders</b> &ndash; Lists the largest top-level folders.</li>
      <li><b>Scan Files</b> &ndash; Lists the largest individual files.</li>
      <li><b>Size categories</b> &ndash; GIGANTIC (&gt;10 GB), HUGE (&gt;1 GB),
          LARGE (&gt;200 MB), MEDIUM (&gt;50 MB), SMALL.</li>
      <li><b>Open in {file_manager}</b> &ndash; Double-click any row to open
          the folder/file location.</li>
      <li><b>Delete</b> &ndash; Select rows and click Delete to remove them.
          A confirmation dialog will appear first.</li>
    </ul>

    <hr>
    <h3 style="color:#1976D2;">4. Smart Advisor Tab</h3>
    <p>The advisor scans a storage location for large, old files and gives each a
    &ldquo;junk score&rdquo; from 0&ndash;100.</p>
    <ul>
      <li><b>How scoring works</b> &ndash; Files get points for: junk extensions
          (.tmp, .log, .bak), being in Downloads/Temp folders, not accessed
          or modified in over a year, and large size (&gt;1 GB).</li>
      <li><b>Risk levels</b>:
        <ul>
          <li><span style="color:red;"><b>HIGH RISK</b></span> (score 70+) &ndash;
              Very likely junk. Safe to review and delete.</li>
          <li><span style="color:#FF8C00;"><b>MEDIUM RISK</b></span> (score 40-69) &ndash;
              Probably unused. Review before deleting.</li>
          <li><span style="color:green;"><b>LOW RISK</b></span> (score &lt;40) &ndash;
              Likely still useful. Keep unless you're sure.</li>
        </ul>
      </li>
      <li><b>Delete</b> &ndash; Select flagged files and delete them after review.</li>
    </ul>

    <hr>
    <h3 style="color:#1976D2;">5. Tips &amp; Best Practices</h3>
    <ul>
      <li>Run a clean scan periodically (e.g. monthly) to keep your system lean.</li>
      <li>Always review items before deleting &ndash; especially in the Advisor tab.</li>
      <li>Check the log file (Help &gt; Open Log File) if a deletion fails.</li>
      <li>Run as {admin_word} for full access to system temp files and caches.</li>
      <li>The Setup Wizard (Help &gt; Re-run Setup Wizard) lets you change which
          storage locations are managed.</li>
    </ul>

    <hr>
    <h3 style="color:#1976D2;">6. Troubleshooting</h3>
    <table border="0" cellpadding="4" cellspacing="0">
      <tr>
        <td><b>Problem</b></td>
        <td><b>Solution</b></td>
      </tr>
      <tr>
        <td>Some files failed to delete</td>
        <td>They may be in use by another program. Close the program and retry,
            or run as {admin_word}.</td>
      </tr>
      <tr>
        <td>Scan is slow</td>
        <td>Large storage locations take longer. The status bar shows progress.</td>
      </tr>
      <tr>
        <td>Storage location not listed</td>
        <td>Re-run the Setup Wizard from Help menu to detect and select locations.</td>
      </tr>
      <tr>
        <td>App not found in Installed Apps</td>
        <td>Some portable apps or manually installed software may not appear in
            {apps_source}.</td>
      </tr>
    </table>

    <hr>
    <p style="color:gray; font-size:small;">StorageCleaner &mdash; Cross-platform storage management tool.
    Works on {os_name}.</p>
    """
    return html


class UserGuideDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("User Guide - StorageCleaner")
        self.setMinimumSize(650, 520)
        self.resize(720, 580)

        layout = QVBoxLayout(self)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setHtml(_build_guide_html())
        layout.addWidget(browser)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)
