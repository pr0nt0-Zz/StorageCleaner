"""
Local chatbot engine for StorageCleaner.

Keyword-matching chatbot that answers questions about the app's features,
gives storage cleaning tips, and guides users. No internet required.
Works on Windows and Linux.
"""

import re
from dataclasses import dataclass, field
from typing import List, Set

from core.platform_utils import IS_WINDOWS, IS_LINUX, get_trash_label, get_elevation_hint


# ---------------------------------------------------------------------------
# Knowledge entry
# ---------------------------------------------------------------------------

@dataclass
class _KBEntry:
    keywords: Set[str]
    patterns: List[str]
    answer: str


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------

def _build_kb() -> List[_KBEntry]:
    trash = get_trash_label()
    elevate = get_elevation_hint()
    os_name = "Windows" if IS_WINDOWS else "Linux"

    return [
        # --- Greetings ---
        _KBEntry(
            keywords={"hi", "hello", "hey", "greetings", "yo", "sup"},
            patterns=["hi", "hello", "hey there", "good morning", "good afternoon"],
            answer=(
                "Hello! I'm the <b>StorageCleaner Bot</b>. I can help you learn how to use this app.<br><br>"
                "Ask me about any of these topics:<br>"
                "<ul>"
                "<li><b>Cleaner</b> - Scan and delete junk files</li>"
                "<li><b>Installed Apps</b> - View and manage apps</li>"
                "<li><b>Storage</b> - Find large files and folders</li>"
                "<li><b>AI Advisor</b> - Smart file deletion recommendations</li>"
                "<li><b>Setup</b> - Configuration and first-run wizard</li>"
                "<li><b>Tips</b> - Best practices for storage management</li>"
                "</ul>"
            ),
        ),

        # --- Thanks ---
        _KBEntry(
            keywords={"thanks", "thank", "thx", "appreciate"},
            patterns=["thank you", "thanks a lot", "thx"],
            answer="You're welcome! Let me know if you have any other questions about StorageCleaner.",
        ),

        # --- Help / What can you do ---
        _KBEntry(
            keywords={"help", "can", "do", "support", "feature", "features"},
            patterns=["what can you do", "help me", "what do you support", "list features"],
            answer=(
                "I can answer questions about <b>StorageCleaner</b>. Here are some things you can ask:<br><br>"
                "<ul>"
                "<li><i>How do I clean junk files?</i></li>"
                "<li><i>What is the AI Advisor?</i></li>"
                "<li><i>How do I find large files?</i></li>"
                "<li><i>How to uninstall an app?</i></li>"
                "<li><i>How do I run as admin?</i></li>"
                "<li><i>What are duplicates?</i></li>"
                "<li><i>Give me storage tips</i></li>"
                "</ul>"
                "<br>Just type your question and I'll do my best to help!"
            ),
        ),

        # --- What is StorageCleaner ---
        _KBEntry(
            keywords={"what", "storagecleaner", "about", "app", "application"},
            patterns=["what is storagecleaner", "what is this app", "about this app", "tell me about"],
            answer=(
                "<b>StorageCleaner</b> is a cross-platform storage management and disk cleaning tool.<br><br>"
                "It helps you:<br>"
                "<ul>"
                "<li>Clean temp files, browser caches, and system junk</li>"
                "<li>View and manage installed applications</li>"
                "<li>Scan storage to find the largest files and folders</li>"
                "<li>Use AI-powered analysis to identify files safe to delete</li>"
                "</ul>"
                f"Currently running on <b>{os_name}</b>."
            ),
        ),

        # --- Cleaner: How to scan ---
        _KBEntry(
            keywords={"clean", "scan", "junk", "temp", "delete", "remove"},
            patterns=["how to clean", "how to scan", "clean junk", "delete temp", "remove junk"],
            answer=(
                "To clean junk files:<br><br>"
                "<ol>"
                "<li>Go to the <b>Cleaner</b> tab</li>"
                "<li>Click <b>Scan</b> to calculate sizes of each clean target</li>"
                "<li>Check the targets you want to clean (temp files, browser caches, etc.)</li>"
                "<li>Click <b>Clean Selected</b> to delete them</li>"
                "</ol>"
                "<br><b>Tip:</b> Close your browser before cleaning browser caches for best results."
            ),
        ),

        # --- Cleaner: Targets ---
        _KBEntry(
            keywords={"target", "targets", "categories", "what", "clean"},
            patterns=["what are targets", "what can i clean", "clean targets", "cleaning categories"],
            answer=(
                "Clean targets are categories of files you can delete:<br><br>"
                "<ul>"
                "<li><b>System temp files</b> - Temporary files created by the OS</li>"
                "<li><b>User temp files</b> - Temporary files in your profile</li>"
                "<li><b>Browser caches</b> - Chrome, Firefox, Edge cached data</li>"
                f"<li><b>{trash}</b> - Deleted files waiting to be permanently removed</li>"
                "<li><b>Thumbnail cache</b> - Cached image previews</li>"
                "</ul>"
                "Each target shows its size after scanning so you can decide what to clean."
            ),
        ),

        # --- Cleaner: Browser cache ---
        _KBEntry(
            keywords={"browser", "cache", "chrome", "firefox", "edge"},
            patterns=["browser cache", "chrome cache", "firefox cache", "clear browser"],
            answer=(
                "StorageCleaner can clean caches for:<br>"
                "<ul>"
                "<li><b>Google Chrome</b></li>"
                "<li><b>Mozilla Firefox</b></li>"
                "<li><b>Microsoft Edge</b></li>"
                "</ul>"
                "<br><b>Important:</b> Close the browser before cleaning its cache, "
                "otherwise some files may be locked and cannot be deleted."
            ),
        ),

        # --- Cleaner: Recycle Bin / Trash ---
        _KBEntry(
            keywords={"recycle", "bin", "trash", "empty"},
            patterns=["empty recycle bin", "empty trash", "clear recycle", "clear trash"],
            answer=(
                f"The <b>{trash}</b> holds files you've deleted but haven't permanently removed.<br><br>"
                f"To empty it, check the <b>{trash}</b> target in the Cleaner tab and click <b>Clean Selected</b>.<br><br>"
                "This permanently deletes all files in the trash and frees up the space they occupy."
            ),
        ),

        # --- Installed Apps ---
        _KBEntry(
            keywords={"installed", "apps", "applications", "programs", "software"},
            patterns=["installed apps", "list apps", "view applications", "my programs"],
            answer=(
                "The <b>Installed Apps</b> tab shows all applications on your system.<br><br>"
                "<ul>"
                "<li>Use the <b>search box</b> to filter by name</li>"
                "<li>Toggle <b>Safe Mode</b> to hide system-critical packages</li>"
                "<li>Columns show: Name, Version, Publisher, and Size</li>"
                "</ul>"
            ),
        ),

        # --- Uninstall ---
        _KBEntry(
            keywords={"uninstall", "remove", "app", "program"},
            patterns=["how to uninstall", "remove app", "uninstall program", "delete app"],
            answer=(
                "To uninstall an application:<br><br>"
                "<ol>"
                "<li>Go to the <b>Installed Apps</b> tab</li>"
                "<li>Find the app using the search box</li>"
                "<li>Select it and click <b>Uninstall</b></li>"
                "</ol>"
                + (
                    "On Windows, this runs the app's built-in uninstaller.<br>"
                    if IS_WINDOWS else
                    "On Linux, the uninstall command is shown for you to run in terminal "
                    "(e.g. <code>sudo apt remove &lt;package&gt;</code>).<br>"
                )
                + "<br>Enable <b>Safe Mode</b> to prevent accidental removal of system packages."
            ),
        ),

        # --- Safe Mode ---
        _KBEntry(
            keywords={"safe", "mode", "system", "critical", "hide"},
            patterns=["safe mode", "what is safe mode", "hide system"],
            answer=(
                "<b>Safe Mode</b> in the Installed Apps tab hides system-critical packages "
                "that should not be removed.<br><br>"
                "When enabled, packages essential to your operating system are hidden "
                "so you don't accidentally uninstall them. It's recommended to keep Safe Mode "
                "enabled unless you know what you're doing."
            ),
        ),

        # --- Storage scanning ---
        _KBEntry(
            keywords={"storage", "large", "files", "folders", "biggest", "space"},
            patterns=["find large files", "scan storage", "biggest files", "what uses space", "disk space"],
            answer=(
                "The <b>Storage</b> tab helps you find what's using the most space:<br><br>"
                "<ol>"
                "<li>Select a storage location from the dropdown</li>"
                "<li>Click <b>Scan Folders</b> to see the largest directories</li>"
                "<li>Click <b>Scan Files</b> to see the largest individual files</li>"
                "</ol>"
                "<br>Files are categorized by size: GIGANTIC (&gt;10 GB), HUGE (&gt;1 GB), "
                "LARGE (&gt;200 MB), MEDIUM (&gt;50 MB), SMALL."
            ),
        ),

        # --- AI Advisor overview ---
        _KBEntry(
            keywords={"ai", "advisor", "recommend", "suggestion", "smart"},
            patterns=["ai advisor", "what is ai advisor", "smart advisor", "file recommendations"],
            answer=(
                "The <b>AI Advisor</b> uses machine learning techniques to find files safe to delete:<br><br>"
                "<ul>"
                "<li><b>Statistical scoring</b> - Uses z-scores to find files that are unusually "
                "large and old compared to your system's average</li>"
                "<li><b>Duplicate detection</b> - Finds identical file copies wasting space</li>"
                "<li><b>Safety protection</b> - System files are automatically excluded</li>"
                "</ul>"
                "<br>Results are color-coded: <span style='color:green;'><b>green = safe to delete</b></span>, "
                "<span style='color:#CC8800;'><b>yellow = review first</b></span>."
            ),
        ),

        # --- AI: How scoring works ---
        _KBEntry(
            keywords={"score", "scoring", "points", "zscore", "z-score", "how"},
            patterns=["how does scoring work", "how are files scored", "what is z-score", "scoring system"],
            answer=(
                "Each file gets a score from <b>0-100</b> based on three components:<br><br>"
                "<ol>"
                "<li><b>Rule-based (max 50 pts)</b> - Points for junk extensions (.tmp, .log), "
                "Downloads/Temp folder location, known junk directories</li>"
                "<li><b>Statistical ML (max 30 pts)</b> - Z-score analysis: files that are unusually "
                "large AND unusually old relative to your system score higher</li>"
                "<li><b>Duplicate bonus (max 20 pts)</b> - Extra points if the file is a "
                "duplicate copy (not the newest)</li>"
                "</ol>"
                "<br>Score 60+ = <b>Safe to delete</b> | Score 30-59 = <b>Review</b> | "
                "Protected files are excluded entirely."
            ),
        ),

        # --- AI: Duplicates ---
        _KBEntry(
            keywords={"duplicate", "duplicates", "copies", "identical", "same"},
            patterns=["duplicate files", "find duplicates", "identical files", "same files"],
            answer=(
                "The AI Advisor detects <b>duplicate files</b> automatically:<br><br>"
                "<ol>"
                "<li>Files are grouped by exact size (fast pre-filter)</li>"
                "<li>Same-size files are compared using partial MD5 hash (first + last 4 KB)</li>"
                "<li>Files with matching size + hash are marked as duplicates</li>"
                "<li>The <b>newest copy is kept</b>, all others are marked safe to delete</li>"
                "</ol>"
                "<br>Use the category filter and select <b>\"Duplicates Only\"</b> to focus on them."
            ),
        ),

        # --- AI: Safety / Protected ---
        _KBEntry(
            keywords={"protected", "safety", "safe", "system", "dangerous"},
            patterns=["what files are protected", "is it safe", "will it break", "system files"],
            answer=(
                "The AI Advisor automatically <b>protects system-critical files</b>:<br><br>"
                "<ul>"
                + (
                    "<li>Windows: System32, Program Files, Windows directory</li>"
                    if IS_WINDOWS else
                    "<li>Linux: /usr, /bin, /sbin, /lib, /etc, /boot, /var/lib/dpkg</li>"
                )
                + "<li>Protected extensions: .sys, .dll, .so, .ko, .service, .conf</li>"
                "</ul>"
                "<br>Protected files are <b>never shown</b> in the results table, "
                "so you can't accidentally select them for deletion."
            ),
        ),

        # --- AI: Select All Safe ---
        _KBEntry(
            keywords={"select", "safe", "green", "button"},
            patterns=["select all safe", "select safe files", "green button", "one click"],
            answer=(
                "The <b>Select All Safe</b> button selects only the green-highlighted rows "
                "(files classified as safe to delete).<br><br>"
                "Yellow rows (\"Review\") are left unchecked so you can manually decide on those.<br><br>"
                "After selecting, click <b>Delete Selected</b> to remove the safe files. "
                "A confirmation dialog will appear before anything is deleted."
            ),
        ),

        # --- AI: Categories ---
        _KBEntry(
            keywords={"category", "categories", "filter", "type", "types"},
            patterns=["file categories", "category filter", "what categories", "file types"],
            answer=(
                "The AI Advisor categorizes files into:<br><br>"
                "<ul>"
                "<li><b>Cache & Temp</b> - Temporary/cache files</li>"
                "<li><b>Duplicate</b> - Identical file copies</li>"
                "<li><b>Old Downloads</b> - Files in Downloads folders</li>"
                "<li><b>Large Unused</b> - Big files not accessed recently</li>"
                "<li><b>Log Files</b> - Application logs</li>"
                "<li><b>Package Cache</b> - Package manager caches</li>"
                "<li><b>Old Media</b> - Old media files</li>"
                "<li><b>Archive</b> - ZIP, RAR, ISO files</li>"
                "<li><b>Build Artifacts</b> - Compiled output files</li>"
                "</ul>"
                "Use the <b>category filter dropdown</b> to view only specific types."
            ),
        ),

        # --- Admin / Sudo ---
        _KBEntry(
            keywords={"admin", "administrator", "sudo", "root", "privilege", "elevated", "permission"},
            patterns=["run as admin", "how to sudo", "administrator", "need permission", "access denied"],
            answer=(
                f"Some cleaning targets require elevated privileges ({elevate}).<br><br>"
                + (
                    "On Windows:<br>"
                    "<ol>"
                    "<li>Right-click the StorageCleaner shortcut</li>"
                    "<li>Select <b>Run as administrator</b></li>"
                    "</ol>"
                    if IS_WINDOWS else
                    "On Linux:<br>"
                    "<ol>"
                    "<li>Run from terminal: <code>sudo python3 main.py</code></li>"
                    "</ol>"
                )
                + "<br>Running elevated gives access to system temp files and other protected locations."
            ),
        ),

        # --- Setup Wizard ---
        _KBEntry(
            keywords={"setup", "wizard", "first", "run", "configure", "storage", "location"},
            patterns=["setup wizard", "first run", "configure storage", "change drives", "change locations"],
            answer=(
                "The <b>Setup Wizard</b> runs on first launch and lets you select which "
                "storage locations to manage.<br><br>"
                "To re-run it later: go to <b>Help &gt; Re-run Setup Wizard</b>.<br><br>"
                "This lets you add or remove storage locations (drives on Windows, "
                "mount points on Linux) from the app."
            ),
        ),

        # --- Log file ---
        _KBEntry(
            keywords={"log", "logs", "error", "errors", "file", "debug"},
            patterns=["log file", "view logs", "where are logs", "check errors", "debug"],
            answer=(
                "StorageCleaner keeps a log file of all operations.<br><br>"
                "To view it: go to <b>Help &gt; Open Log File</b>.<br>"
                "To open the log folder: go to <b>Help &gt; Open Log Folder</b>.<br><br>"
                "The log file is useful for debugging if a cleaning operation fails "
                "or files couldn't be deleted."
            ),
        ),

        # --- User Guide ---
        _KBEntry(
            keywords={"guide", "manual", "documentation", "docs", "user"},
            patterns=["user guide", "open guide", "manual", "documentation"],
            answer=(
                "StorageCleaner has a built-in User Guide.<br><br>"
                "To open it: go to <b>Help &gt; User Guide</b>.<br><br>"
                "The guide covers every tab and feature with detailed instructions."
            ),
        ),

        # --- Tips ---
        _KBEntry(
            keywords={"tip", "tips", "best", "practice", "advice", "recommend"},
            patterns=["give me tips", "storage tips", "best practices", "advice"],
            answer=(
                "Here are some <b>storage management tips</b>:<br><br>"
                "<ul>"
                "<li>Run a clean scan periodically (e.g. monthly) to keep your system lean</li>"
                "<li>Always review files before deleting, especially in the AI Advisor tab</li>"
                "<li>Close browsers before cleaning their caches</li>"
                f"<li>Run as {get_elevation_hint()} for full access to system files</li>"
                f"<li>Empty the {trash} regularly - deleted files still use space</li>"
                "<li>Use the AI Advisor's <b>Select All Safe</b> button for quick, safe cleanup</li>"
                "<li>Check for duplicate files - they can waste significant space</li>"
                "</ul>"
            ),
        ),

        # --- Platform support ---
        _KBEntry(
            keywords={"platform", "windows", "linux", "ubuntu", "kali", "cross"},
            patterns=["what platforms", "does it work on linux", "windows support", "cross platform"],
            answer=(
                "StorageCleaner works on:<br><br>"
                "<ul>"
                "<li><b>Windows</b> (10, 11) - Full support including registry-based app listing</li>"
                "<li><b>Linux</b> (Ubuntu, Kali, Debian, etc.) - Full support including "
                "dpkg/rpm/flatpak/snap package listing</li>"
                "</ul>"
                f"<br>You are currently running on <b>{os_name}</b>."
            ),
        ),

        # --- Minimum size ---
        _KBEntry(
            keywords={"minimum", "size", "mb", "small", "threshold"},
            patterns=["minimum size", "change size", "scan small files", "file size threshold"],
            answer=(
                "In the <b>AI Advisor</b> tab, you can set the minimum file size to scan:<br><br>"
                "Available options: <b>10 MB, 25 MB, 50 MB, 100 MB, 250 MB, 500 MB</b><br><br>"
                "Lower values find more files but the scan takes longer. "
                "The default is <b>50 MB</b>, which is a good balance between coverage and speed."
            ),
        ),

        # --- Bye ---
        _KBEntry(
            keywords={"bye", "goodbye", "exit", "quit", "close"},
            patterns=["bye", "goodbye", "see you", "that's all"],
            answer=(
                "Goodbye! Feel free to come back anytime you have questions about StorageCleaner. "
                "Happy cleaning!"
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# Matching engine
# ---------------------------------------------------------------------------

_PUNCT_RE = re.compile(r"[^\w\s]")

_kb: List[_KBEntry] = []


def _ensure_kb():
    global _kb
    if not _kb:
        _kb = _build_kb()


def get_response(user_input: str) -> str:
    """Return the best-matching answer for *user_input*."""
    _ensure_kb()

    text = _PUNCT_RE.sub("", user_input.lower()).strip()
    if not text:
        return "Please type a question and I'll do my best to help!"

    words = set(text.split())

    # Phase 1: exact phrase match (highest priority)
    for entry in _kb:
        for pattern in entry.patterns:
            if pattern in text:
                return entry.answer

    # Phase 2: keyword overlap scoring
    best_score = 0
    best_answer = ""
    for entry in _kb:
        overlap = len(words & entry.keywords)
        if overlap > best_score:
            best_score = overlap
            best_answer = entry.answer

    if best_score >= 1:
        return best_answer

    # Phase 3: fallback
    return (
        "I'm not sure about that. I can only help with <b>StorageCleaner</b> topics.<br><br>"
        "Try asking about:<br>"
        "<ul>"
        "<li>How to <b>clean</b> junk files</li>"
        "<li>The <b>AI Advisor</b> and how scoring works</li>"
        "<li><b>Duplicate</b> file detection</li>"
        "<li>Finding <b>large files</b> in Storage tab</li>"
        "<li><b>Uninstalling</b> apps</li>"
        "<li>Running as <b>admin</b></li>"
        "<li>Storage management <b>tips</b></li>"
        "</ul>"
    )


def get_welcome_message() -> str:
    """Return the initial bot welcome message."""
    return (
        "Hi! I'm the <b>StorageCleaner Bot</b>. "
        "I can help you learn how to use this app.<br><br>"
        "Ask me about: <b>Cleaner</b>, <b>Installed Apps</b>, <b>Storage</b>, "
        "<b>AI Advisor</b>, or just ask for <b>tips</b>!<br><br>"
        "<i>Type your question below or click one of the quick-action buttons.</i>"
    )
