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
    <h3 style="color:#1976D2;">4. AI Advisor Tab</h3>
    <p>The AI Advisor uses machine learning techniques to intelligently analyse your files
    and recommend which ones are safe to delete.</p>
    <ul>
      <li><b>How it works</b> &ndash; The advisor scans your storage location and scores
          each file from 0&ndash;100 using three components:
        <ul>
          <li><b>Rule-based scoring</b> &ndash; Junk extensions (.tmp, .log, .bak),
              Downloads/Temp folder locations, known junk directories.</li>
          <li><b>Statistical analysis (ML)</b> &ndash; Computes z-scores for file size
              and age across your system. Files that are unusually large AND
              unusually old score higher. This adapts to each system automatically.</li>
          <li><b>Duplicate detection</b> &ndash; Groups files by size and partial hash
              to find identical copies. Keeps the newest copy, marks others as safe
              to delete.</li>
        </ul>
      </li>
      <li><b>Safety levels</b>:
        <ul>
          <li><span style="color:green;"><b>SAFE TO DELETE</b></span> (green rows, score 60+) &ndash;
              High confidence these can be removed safely.</li>
          <li><span style="color:#FF8C00;"><b>REVIEW</b></span> (yellow rows, score 30-59) &ndash;
              Probably unused. Check before deleting.</li>
          <li><b>Protected files</b> &ndash; System files are automatically excluded
              and never shown in results.</li>
        </ul>
      </li>
      <li><b>Categories</b> &ndash; Files are categorised (Cache, Duplicate, Log, Archive,
          Old Download, etc.). Use the category filter to focus on specific types.</li>
      <li><b>Select All Safe</b> &ndash; One-click button to select only green
          (safe to delete) rows.</li>
      <li><b>Delete</b> &ndash; Select files and click Delete to remove them permanently.
          A confirmation dialog will appear first.</li>
    </ul>

    <hr>
    <h3 style="color:#1976D2;">5. StorageAdvisor Tab</h3>
    <p>StorageAdvisor is your in-app storage assistant. It uses a strict
    decision framework to help you free disk space safely:</p>
    <ul>
      <li><span style="color:green;"><b>SAFE_DELETE</b></span> &ndash; Low-risk
          temp/cache items, queue for deletion.</li>
      <li><span style="color:#FF8C00;"><b>REVIEW</b></span> &ndash; User data or
          unknown items; recommend manual inspection.</li>
      <li><span style="color:red;"><b>DO_NOT_DELETE</b></span> &ndash; OS/system
          paths; hard warning, never delete.</li>
    </ul>
    <ul>
      <li><b>How to use</b> &ndash; Type a question in the text box and press
          Enter or click Send.</li>
      <li><b>Quick action buttons</b> &ndash; Click Quick Wins, Hard Stops,
          Is this safe?, Storage Tips, or How to free space?</li>
      <li><b>Topics it covers</b> &ndash; Safe cleanup, folder classification,
          AI Advisor scoring, duplicate detection, browser caches, admin/sudo,
          setup wizard, and storage hygiene recommendations.</li>
      <li><b>Scope</b> &ndash; StorageAdvisor only answers questions about this app
          and safe disk cleanup. It does not connect to the internet or use
          external AI services.</li>
    </ul>
    <p><b>Example questions:</b> <i>&ldquo;What can I safely delete?&rdquo;</i>,
    <i>&ldquo;Is this folder safe?&rdquo;</i>,
    <i>&ldquo;How does AI Advisor work?&rdquo;</i>,
    <i>&ldquo;Give me storage tips&rdquo;</i></p>

    <hr>
    <h3 style="color:#1976D2;">6. Tips &amp; Best Practices</h3>
    <ul>
      <li>Run a clean scan periodically (e.g. monthly) to keep your system lean.</li>
      <li>Always review items before deleting &ndash; especially in the Advisor tab.</li>
      <li>Check the log file (Help &gt; Open Log File) if a deletion fails.</li>
      <li>Run as {admin_word} for full access to system temp files and caches.</li>
      <li>The Setup Wizard (Help &gt; Re-run Setup Wizard) lets you change which
          storage locations are managed.</li>
    </ul>

    <hr>
    <h3 style="color:#1976D2;">7. Troubleshooting</h3>
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
