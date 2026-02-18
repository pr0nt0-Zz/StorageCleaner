"""
StorageAdvisor - Cross-platform storage assistant chatbot.

A local, offline chatbot embedded in StorageCleaner that helps users free
disk space safely using a strict decision framework:
  SAFE_DELETE  - low-risk temp/cache items, queue for deletion
  REVIEW       - user data or unknown; recommend manual inspection
  DO_NOT_DELETE - OS/system paths; hard warning

No internet, no external APIs. Works on Windows and Linux.
"""

import re
from dataclasses import dataclass
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
# Safety constants
# ---------------------------------------------------------------------------

_WIN_PROTECTED = [
    "C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)",
    "C:\\ProgramData", "System Volume Information",
    "pagefile.sys", "hiberfil.sys", "swapfile.sys",
]

_LINUX_PROTECTED = [
    "/bin", "/sbin", "/lib", "/lib64", "/usr", "/etc", "/boot",
    "/sys", "/proc", "/dev", "/run", "/var/lib/dpkg", "/var/lib/apt/lists",
]

_SAFE_DELETE_ITEMS_WIN = [
    ("User Temp files", "%TEMP%", "Usually 200 MB - 2 GB"),
    ("System Temp files", "C:\\Windows\\Temp", "100 MB - 1 GB (needs admin)"),
    ("Browser caches", "Chrome / Firefox / Edge cache", "500 MB - 5 GB"),
    ("Recycle Bin", "Recycle Bin contents", "Varies"),
    ("Thumbnail cache", "Explorer thumbnail DB", "50 - 500 MB"),
    ("Windows Update cleanup", "Old update files", "1 - 10 GB"),
]

_SAFE_DELETE_ITEMS_LINUX = [
    ("User cache", "~/.cache", "500 MB - 5 GB"),
    ("APT package cache", "/var/cache/apt/archives", "500 MB - 3 GB"),
    ("Browser caches", "Chrome / Firefox cache dirs", "500 MB - 5 GB"),
    ("Trash", "~/.local/share/Trash", "Varies"),
    ("Thumbnail cache", "~/.cache/thumbnails", "50 - 500 MB"),
    ("Journal logs", "/var/log/journal (old)", "200 MB - 2 GB"),
    ("Snap cache", "~/snap/*/common", "100 MB - 1 GB"),
]


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------

def _build_kb() -> List[_KBEntry]:
    trash = get_trash_label()
    elevate = get_elevation_hint()
    os_name = "Windows" if IS_WINDOWS else "Linux"

    safe_items = _SAFE_DELETE_ITEMS_WIN if IS_WINDOWS else _SAFE_DELETE_ITEMS_LINUX
    protected = _WIN_PROTECTED if IS_WINDOWS else _LINUX_PROTECTED

    # Build quick wins HTML
    quick_wins_rows = ""
    for name, loc, est in safe_items:
        quick_wins_rows += (
            f"<tr><td><b>{name}</b></td>"
            f"<td><code>{loc}</code></td>"
            f"<td>{est}</td>"
            f"<td style='color:green;'><b>SAFE_DELETE</b></td></tr>"
        )

    quick_wins_html = (
        "<table border='0' cellpadding='4' cellspacing='2'>"
        "<tr><td><b>Item</b></td><td><b>Location</b></td>"
        "<td><b>Est. Size</b></td><td><b>Classification</b></td></tr>"
        f"{quick_wins_rows}</table>"
    )

    # Build protected paths HTML
    protected_html = "".join(f"<li><code>{p}</code></li>" for p in protected)

    return [
        # --- Greetings ---
        _KBEntry(
            keywords={"hi", "hello", "hey", "greetings", "yo", "sup"},
            patterns=["hi", "hello", "hey there", "good morning", "good afternoon"],
            answer=(
                f"Hello! I'm <b>StorageAdvisor</b>, your {os_name} storage assistant.<br><br>"
                "I help you free disk space <b>safely</b>. Every item I discuss gets a classification:<br>"
                "<ul>"
                "<li><span style='color:green;'><b>SAFE_DELETE</b></span> - Low-risk, queue for deletion</li>"
                "<li><span style='color:#CC8800;'><b>REVIEW</b></span> - Check before removing</li>"
                "<li><span style='color:red;'><b>DO_NOT_DELETE</b></span> - System-critical, hands off</li>"
                "</ul>"
                "Ask me: <i>\"What can I safely delete?\"</i>, <i>\"Quick wins\"</i>, "
                "<i>\"Is this folder safe?\"</i>, or <i>\"Storage tips\"</i>"
            ),
        ),

        # --- Thanks ---
        _KBEntry(
            keywords={"thanks", "thank", "thx", "appreciate"},
            patterns=["thank you", "thanks a lot", "thx"],
            answer="You're welcome! Remember: always confirm before deleting. Stay safe out there.",
        ),

        # --- Help / What can you do ---
        _KBEntry(
            keywords={"help", "can", "do", "support", "feature", "features"},
            patterns=["what can you do", "help me", "what do you support", "list features"],
            answer=(
                "I'm <b>StorageAdvisor</b>. I can help you with:<br><br>"
                "<ul>"
                "<li><i>\"What can I safely delete?\"</i> - Quick wins list with SAFE_DELETE items</li>"
                "<li><i>\"Is [folder] safe to delete?\"</i> - I'll classify it</li>"
                "<li><i>\"How to free space?\"</i> - Step-by-step cleanup guide</li>"
                "<li><i>\"What should I never delete?\"</i> - Hard stops list</li>"
                "<li><i>\"Storage tips\"</i> - Hygiene recommendations</li>"
                "<li><i>\"How does AI Advisor work?\"</i> - ML scoring explained</li>"
                "<li><i>\"How to use the Cleaner?\"</i> - Tab guides</li>"
                "</ul>"
                "<br>Every recommendation follows the <b>SAFE_DELETE / REVIEW / DO_NOT_DELETE</b> framework."
            ),
        ),

        # --- Quick wins / What can I safely delete ---
        _KBEntry(
            keywords={"safely", "delete", "quick", "wins", "free", "space", "what"},
            patterns=["what can i safely delete", "quick wins", "safe to delete", "free up space",
                       "what should i delete", "what can i delete", "free space"],
            answer=(
                f"<b>Quick Wins</b> - Items classified as <span style='color:green;'><b>SAFE_DELETE</b></span> on {os_name}:<br><br>"
                f"{quick_wins_html}<br>"
                "<b>Next step:</b> Go to the <b>Cleaner</b> tab, click <b>Scan</b>, "
                "check the items above, then click <b>Clean Selected</b>.<br><br>"
                "For deeper analysis, go to the <b>AI Advisor</b> tab and click <b>AI Scan</b>, "
                "then use <b>Select All Safe</b> to queue only green-classified files."
            ),
        ),

        # --- What should I never delete / Hard stops ---
        _KBEntry(
            keywords={"never", "dont", "dangerous", "break", "destroy", "hard", "stop", "stops"},
            patterns=["what should i never delete", "hard stops", "never delete", "dangerous files",
                       "dont delete", "will it break"],
            answer=(
                "<b>Hard Stops</b> - <span style='color:red;'><b>DO_NOT_DELETE</b></span>:<br><br>"
                f"These paths are system-critical on {os_name}. <b>Never</b> delete or modify them:<br>"
                f"<ul>{protected_html}</ul>"
                "<b>StorageAdvisor will never recommend deleting these.</b> "
                "The AI Advisor automatically excludes them from scan results.<br><br>"
                "If you see any of these paths suggested elsewhere, <b>do not proceed</b>."
            ),
        ),

        # --- Is this folder safe? ---
        _KBEntry(
            keywords={"folder", "directory", "path", "safe", "check"},
            patterns=["is this safe", "is this folder safe", "can i delete this folder",
                       "check this path", "is it safe to delete"],
            answer=(
                "To check if a folder is safe to delete, use this framework:<br><br>"
                "<span style='color:green;'><b>SAFE_DELETE</b></span> if the path is:<br>"
                "<ul>"
                "<li>Inside <code>Temp</code>, <code>Cache</code>, or <code>Thumbnails</code></li>"
                f"<li>Inside the {trash}</li>"
                "<li>A browser cache directory</li>"
                "<li>Inside <code>Downloads</code> (after verifying contents)</li>"
                "</ul>"
                "<span style='color:#CC8800;'><b>REVIEW</b></span> if:<br>"
                "<ul>"
                "<li>It's in your user profile but you don't recognize it</li>"
                "<li>It contains documents, media, or project files</li>"
                "<li><b>Action:</b> Open the folder first and verify contents</li>"
                "</ul>"
                "<span style='color:red;'><b>DO_NOT_DELETE</b></span> if:<br>"
                "<ul>"
                + (
                    "<li>It's under <code>C:\\Windows</code>, <code>C:\\Program Files</code>, or <code>C:\\ProgramData</code></li>"
                    if IS_WINDOWS else
                    "<li>It's under <code>/usr</code>, <code>/bin</code>, <code>/etc</code>, <code>/boot</code>, or <code>/lib</code></li>"
                )
                + "<li>It contains <code>.sys</code>, <code>.dll</code>, <code>.so</code>, or <code>.service</code> files</li>"
                "</ul>"
                "<b>Tip:</b> Run the <b>AI Advisor</b> scan - it classifies files automatically using this exact framework."
            ),
        ),

        # --- How to free space step by step ---
        _KBEntry(
            keywords={"how", "free", "space", "step", "guide", "cleanup", "clean"},
            patterns=["how to free space", "step by step", "cleanup guide", "how do i clean",
                       "how to clean", "free disk space"],
            answer=(
                f"<b>Step-by-step cleanup guide for {os_name}:</b><br><br>"
                "<b>Step 1 - Quick Clean</b> (SAFE_DELETE):<br>"
                "Go to <b>Cleaner</b> tab &rarr; Click <b>Scan</b> &rarr; Check all items &rarr; Click <b>Clean Selected</b><br><br>"
                "<b>Step 2 - AI Analysis</b> (SAFE_DELETE + REVIEW):<br>"
                "Go to <b>AI Advisor</b> tab &rarr; Set min size to <b>25 MB</b> &rarr; Click <b>AI Scan</b> &rarr; "
                "Click <b>Select All Safe</b> (green rows only) &rarr; Click <b>Delete Selected</b><br><br>"
                "<b>Step 3 - Review yellow rows</b> (REVIEW):<br>"
                "For each yellow row, right-click the path to open the folder. "
                "Verify contents before deciding to delete or archive.<br><br>"
                "<b>Step 4 - Check large files</b>:<br>"
                "Go to <b>Storage</b> tab &rarr; Click <b>Scan Files</b> to find the biggest items. "
                "Classify each one before acting.<br><br>"
                f"<b>Step 5 - Empty {trash}</b>:<br>"
                f"In <b>Cleaner</b> tab, check <b>{trash}</b> and clean it."
            ),
        ),

        # --- Cleaner tab ---
        _KBEntry(
            keywords={"cleaner", "tab", "scan", "targets", "junk", "temp"},
            patterns=["how to use cleaner", "cleaner tab", "clean targets", "what are targets",
                       "cleaning categories"],
            answer=(
                "<b>Cleaner Tab</b> - All items here are classified <span style='color:green;'><b>SAFE_DELETE</b></span>:<br><br>"
                "<ol>"
                "<li>Click <b>Scan</b> to calculate sizes of each target</li>"
                "<li>Review the list - each shows the reclaimable size</li>"
                "<li>Check the targets you want to clean</li>"
                "<li>Click <b>Clean Selected</b></li>"
                "</ol>"
                f"<b>Targets include:</b> System temp, User temp, Browser caches, {trash}, Thumbnail cache<br><br>"
                "<b>Tip:</b> Close browsers before cleaning their caches. "
                f"Some system targets need {elevate}."
            ),
        ),

        # --- Browser cache ---
        _KBEntry(
            keywords={"browser", "cache", "chrome", "firefox", "edge"},
            patterns=["browser cache", "chrome cache", "firefox cache", "clear browser"],
            answer=(
                "<b>Browser Caches</b> - <span style='color:green;'><b>SAFE_DELETE</b></span><br><br>"
                "Supported browsers: <b>Chrome</b>, <b>Firefox</b>, <b>Edge</b><br>"
                "Estimated size: <b>500 MB - 5 GB</b> typically<br><br>"
                "<b>Important:</b> Close the browser before cleaning, otherwise files may be locked.<br><br>"
                "<b>Next step:</b> Go to <b>Cleaner</b> tab &rarr; <b>Scan</b> &rarr; check browser cache items &rarr; <b>Clean Selected</b>"
            ),
        ),

        # --- Recycle Bin / Trash ---
        _KBEntry(
            keywords={"recycle", "bin", "trash", "empty"},
            patterns=["empty recycle bin", "empty trash", "clear recycle", "clear trash"],
            answer=(
                f"<b>{trash}</b> - <span style='color:green;'><b>SAFE_DELETE</b></span><br><br>"
                f"The {trash} holds files you've already deleted but haven't permanently removed. "
                "They still consume disk space.<br><br>"
                f"<b>Next step:</b> Go to <b>Cleaner</b> tab &rarr; check <b>{trash}</b> &rarr; click <b>Clean Selected</b><br><br>"
                "This is a <b>reversible-first</b> action - files are already in the trash, "
                "so emptying it is the final confirmation."
            ),
        ),

        # --- Installed Apps ---
        _KBEntry(
            keywords={"installed", "apps", "applications", "programs", "software", "uninstall"},
            patterns=["installed apps", "list apps", "view applications", "how to uninstall",
                       "remove app", "uninstall program"],
            answer=(
                "<b>Installed Apps Tab</b><br><br>"
                "View and manage installed applications. Classification depends on the app:<br>"
                "<ul>"
                "<li><span style='color:#CC8800;'><b>REVIEW</b></span> - Most apps. Verify you no longer need them before removing.</li>"
                "<li><span style='color:red;'><b>DO_NOT_DELETE</b></span> - System packages. "
                "Enable <b>Safe Mode</b> to hide these.</li>"
                "</ul>"
                "<b>Next step:</b> Search for unused apps &rarr; Select &rarr; Click <b>Uninstall</b><br><br>"
                + (
                    "On Windows, this runs the app's built-in uninstaller.<br>"
                    if IS_WINDOWS else
                    "On Linux, the uninstall command is shown for terminal execution.<br>"
                )
                + "<b>Always keep Safe Mode ON</b> to protect system-critical packages."
            ),
        ),

        # --- Storage tab ---
        _KBEntry(
            keywords={"storage", "large", "files", "folders", "biggest", "space", "scan"},
            patterns=["find large files", "scan storage", "biggest files", "what uses space",
                       "disk space", "storage tab"],
            answer=(
                "<b>Storage Tab</b> - Find what's using the most space.<br><br>"
                "<ol>"
                "<li>Select a storage location from the dropdown</li>"
                "<li>Click <b>Scan Folders</b> or <b>Scan Files</b></li>"
                "<li>Review results - classify each item before acting:</li>"
                "</ol>"
                "<ul>"
                "<li><span style='color:green;'><b>SAFE_DELETE</b></span> - Files in Temp/Cache/Downloads (after review)</li>"
                "<li><span style='color:#CC8800;'><b>REVIEW</b></span> - Large files you don't recognize. "
                "Click to <b>Open folder</b> and inspect.</li>"
                "<li><span style='color:red;'><b>DO_NOT_DELETE</b></span> - System directories. Leave alone.</li>"
                "</ul>"
                "Size categories: GIGANTIC (&gt;10 GB), HUGE (&gt;1 GB), LARGE (&gt;200 MB), MEDIUM (&gt;50 MB)"
            ),
        ),

        # --- AI Advisor ---
        _KBEntry(
            keywords={"ai", "advisor", "recommend", "suggestion", "smart", "ml", "machine"},
            patterns=["ai advisor", "what is ai advisor", "smart advisor", "file recommendations",
                       "how does ai work", "machine learning"],
            answer=(
                "<b>AI Advisor</b> - Automated file classification engine.<br><br>"
                "The AI Advisor maps directly to the StorageAdvisor framework:<br>"
                "<ul>"
                "<li><span style='color:green;'><b>Green rows = SAFE_DELETE</b></span> (score 60+) - Queue for deletion</li>"
                "<li><span style='color:#CC8800;'><b>Yellow rows = REVIEW</b></span> (score 30-59) - Inspect first</li>"
                "<li><b>Protected files = DO_NOT_DELETE</b> - Auto-excluded from results</li>"
                "</ul>"
                "<b>Scoring uses 3 components:</b><br>"
                "<ol>"
                "<li><b>Rule-based</b> (max 50 pts) - Junk extensions, known cache dirs</li>"
                "<li><b>Statistical ML</b> (max 30 pts) - Z-score outlier detection for size + age</li>"
                "<li><b>Duplicate bonus</b> (max 20 pts) - Identical copies detected via partial hash</li>"
                "</ol>"
                "<b>Next step:</b> Go to <b>AI Advisor</b> tab &rarr; Click <b>AI Scan</b> &rarr; "
                "Click <b>Select All Safe</b> &rarr; Click <b>Delete Selected</b>"
            ),
        ),

        # --- Duplicates ---
        _KBEntry(
            keywords={"duplicate", "duplicates", "copies", "identical", "same"},
            patterns=["duplicate files", "find duplicates", "identical files", "same files"],
            answer=(
                "<b>Duplicate Detection</b> - <span style='color:green;'><b>SAFE_DELETE</b></span> (copies only)<br><br>"
                "The AI Advisor detects duplicate files automatically:<br>"
                "<ol>"
                "<li>Files grouped by exact size (fast pre-filter)</li>"
                "<li>Same-size files compared via partial MD5 hash (first + last 4 KB)</li>"
                "<li>Matching files = duplicates</li>"
                "<li><b>Newest copy is kept</b>, others marked SAFE_DELETE</li>"
                "</ol>"
                "<b>Next step:</b> In <b>AI Advisor</b> tab, use the category filter &rarr; "
                "select <b>\"Duplicates Only\"</b> to focus on them.<br><br>"
                "Duplicate copies are classified SAFE_DELETE because the newest version is always preserved."
            ),
        ),

        # --- Protected / Safety ---
        _KBEntry(
            keywords={"protected", "safety", "system", "critical"},
            patterns=["what files are protected", "system files", "protected paths",
                       "what is protected"],
            answer=(
                "<b>Protected Paths</b> - <span style='color:red;'><b>DO_NOT_DELETE</b></span>:<br><br>"
                f"On {os_name}, these are <b>never</b> suggested for deletion:<br>"
                f"<ul>{protected_html}</ul>"
                "<b>Protected extensions:</b> .sys, .dll, .so, .ko, .service, .conf<br><br>"
                "The AI Advisor automatically excludes all protected paths from scan results. "
                "They will <b>never appear</b> in the results table."
            ),
        ),

        # --- Select All Safe ---
        _KBEntry(
            keywords={"select", "safe", "green", "button", "queue"},
            patterns=["select all safe", "queue safe clean", "green button", "one click delete"],
            answer=(
                "<b>Select All Safe</b> = Queue all SAFE_DELETE items.<br><br>"
                "This button selects <b>only green rows</b> (SAFE_DELETE classification).<br>"
                "Yellow rows (REVIEW) are left unchecked for manual inspection.<br><br>"
                "<b>Next step:</b><br>"
                "<ol>"
                "<li>Click <b>Select All Safe</b></li>"
                "<li>Review the selection count in the dashboard</li>"
                "<li>Click <b>Delete Selected</b></li>"
                "<li>Confirm in the dialog</li>"
                "</ol>"
                "Deletion is <b>always user-confirmed</b>. Nothing happens without your approval."
            ),
        ),

        # --- Categories ---
        _KBEntry(
            keywords={"category", "categories", "filter", "type", "types"},
            patterns=["file categories", "category filter", "what categories", "file types"],
            answer=(
                "<b>File Categories</b> with default classifications:<br><br>"
                "<table border='0' cellpadding='3' cellspacing='1'>"
                "<tr><td><b>Category</b></td><td><b>Classification</b></td></tr>"
                "<tr><td>Cache & Temp</td><td style='color:green;'>SAFE_DELETE</td></tr>"
                "<tr><td>Duplicate Copies</td><td style='color:green;'>SAFE_DELETE</td></tr>"
                "<tr><td>Log Files</td><td style='color:green;'>SAFE_DELETE</td></tr>"
                "<tr><td>Package Cache</td><td style='color:green;'>SAFE_DELETE</td></tr>"
                "<tr><td>Build Artifacts</td><td style='color:green;'>SAFE_DELETE</td></tr>"
                "<tr><td>Old Downloads</td><td style='color:#CC8800;'>REVIEW</td></tr>"
                "<tr><td>Large Unused</td><td style='color:#CC8800;'>REVIEW</td></tr>"
                "<tr><td>Old Media</td><td style='color:#CC8800;'>REVIEW</td></tr>"
                "<tr><td>Archives</td><td style='color:#CC8800;'>REVIEW</td></tr>"
                "</table><br>"
                "Use the <b>category filter dropdown</b> in the AI Advisor tab to focus on specific types."
            ),
        ),

        # --- Admin / Sudo ---
        _KBEntry(
            keywords={"admin", "administrator", "sudo", "root", "privilege", "elevated", "permission"},
            patterns=["run as admin", "how to sudo", "administrator", "need permission", "access denied"],
            answer=(
                f"<b>Elevated Privileges</b> ({elevate})<br><br>"
                "Some SAFE_DELETE targets (system temp, package cache) require elevation.<br><br>"
                + (
                    "<b>Windows:</b> Right-click StorageCleaner &rarr; <b>Run as administrator</b><br>"
                    if IS_WINDOWS else
                    "<b>Linux:</b> Run <code>sudo python3 main.py</code> from terminal<br>"
                )
                + "<br><b>Note:</b> Running elevated does NOT change the safety classification. "
                "System-critical paths remain <span style='color:red;'><b>DO_NOT_DELETE</b></span> regardless of privilege level."
            ),
        ),

        # --- Setup Wizard ---
        _KBEntry(
            keywords={"setup", "wizard", "first", "configure", "location"},
            patterns=["setup wizard", "first run", "configure storage", "change drives", "change locations"],
            answer=(
                "<b>Setup Wizard</b><br><br>"
                "The wizard lets you select which storage locations to manage.<br>"
                "To re-run: <b>Help &gt; Re-run Setup Wizard</b><br><br>"
                + (
                    "On Windows: select drives (C:, D:, etc.)<br>"
                    if IS_WINDOWS else
                    "On Linux: select mount points (/, /home, /mnt/data, etc.)<br>"
                )
                + "<br><b>Note:</b> Only user-scoped directories within selected locations "
                "will be suggested for deletion. System paths remain DO_NOT_DELETE."
            ),
        ),

        # --- Log file ---
        _KBEntry(
            keywords={"log", "logs", "error", "errors", "debug"},
            patterns=["log file", "view logs", "where are logs", "check errors", "debug"],
            answer=(
                "<b>Log File</b><br><br>"
                "StorageCleaner logs all operations for auditing.<br>"
                "View it: <b>Help &gt; Open Log File</b><br>"
                "Open folder: <b>Help &gt; Open Log Folder</b><br><br>"
                "Check the log if a deletion fails - it shows exactly which files "
                "couldn't be removed and why (usually «file in use» or «permission denied»)."
            ),
        ),

        # --- User Guide ---
        _KBEntry(
            keywords={"guide", "manual", "documentation", "docs"},
            patterns=["user guide", "open guide", "manual", "documentation"],
            answer=(
                "<b>User Guide</b><br><br>"
                "Full documentation: <b>Help &gt; User Guide</b><br><br>"
                "Covers all tabs, features, and the StorageAdvisor decision framework."
            ),
        ),

        # --- Storage tips / hygiene ---
        _KBEntry(
            keywords={"tip", "tips", "best", "practice", "advice", "hygiene", "recommend"},
            patterns=["give me tips", "storage tips", "best practices", "advice",
                       "storage hygiene", "recommendations"],
            answer=(
                f"<b>Storage Hygiene - {os_name} Recommendations:</b><br><br>"
                "<ol>"
                "<li><b>Monthly cleanup</b> - Run the <b>Cleaner</b> tab scan + clean. "
                "All targets are SAFE_DELETE. Click <b>Scan</b> then <b>Clean Selected</b>.</li>"
                "<li><b>Quarterly AI scan</b> - Run <b>AI Advisor</b> with min size 25 MB. "
                "Use <b>Select All Safe</b> for green items, manually review yellow.</li>"
                "<li><b>Duplicate audit</b> - Filter by <b>Duplicates Only</b> in AI Advisor. "
                "Duplicate copies are SAFE_DELETE (newest kept).</li>"
                + (
                    "<li><b>Windows Update cleanup</b> - Run Disk Cleanup as admin to clear old updates (1-10 GB potential).</li>"
                    "<li><b>Hibernate file</b> - If you don't use hibernate, run <code>powercfg /h off</code> as admin "
                    "to reclaim the hiberfil.sys space (often 4-8 GB). Classification: REVIEW.</li>"
                    if IS_WINDOWS else
                    "<li><b>APT cache</b> - The Cleaner handles this, but you can also run "
                    "<code>sudo apt clean</code> for a thorough purge. Classification: SAFE_DELETE.</li>"
                    "<li><b>Docker cleanup</b> - If you use Docker, run <code>docker system prune</code> "
                    "to clear unused images/containers. Classification: REVIEW (inspect first).</li>"
                )
                + "<li><b>Downloads folder</b> - Classification: REVIEW. Open it periodically, "
                "archive what you need, delete the rest.</li>"
                "</ol>"
            ),
        ),

        # --- Platform support ---
        _KBEntry(
            keywords={"platform", "windows", "linux", "ubuntu", "kali", "cross"},
            patterns=["what platforms", "does it work on linux", "windows support", "cross platform"],
            answer=(
                "<b>Cross-Platform Support</b><br><br>"
                "<ul>"
                "<li><b>Windows</b> (10, 11) - Registry-based app listing, PowerShell recycle bin cleanup</li>"
                "<li><b>Linux</b> (Ubuntu, Kali, Debian) - dpkg/rpm/flatpak/snap app listing, "
                "~/.local/share/Trash cleanup</li>"
                "</ul>"
                f"Currently running on <b>{os_name}</b>.<br><br>"
                "Safety rules are platform-specific - protected paths differ between Windows and Linux."
            ),
        ),

        # --- Minimum size ---
        _KBEntry(
            keywords={"minimum", "size", "mb", "small", "threshold"},
            patterns=["minimum size", "change size", "scan small files", "file size threshold"],
            answer=(
                "<b>Minimum File Size</b> (AI Advisor)<br><br>"
                "Options: <b>10 MB, 25 MB, 50 MB, 100 MB, 250 MB, 500 MB</b><br>"
                "Default: <b>50 MB</b><br><br>"
                "<b>Recommendation:</b> Set to <b>25 MB</b> if your disk is nearly full. "
                "Lower values find more SAFE_DELETE candidates but scan takes longer.<br><br>"
                "<b>Next step:</b> In <b>AI Advisor</b> tab, change the min size dropdown, then click <b>AI Scan</b>."
            ),
        ),

        # --- About / What is this ---
        _KBEntry(
            keywords={"what", "storagecleaner", "about", "app", "application"},
            patterns=["what is storagecleaner", "what is this app", "about this app", "tell me about"],
            answer=(
                f"<b>StorageCleaner v1.2</b> - Cross-platform storage management tool.<br><br>"
                "Features:<br>"
                "<ul>"
                "<li><b>Cleaner</b> - Scan and delete junk (SAFE_DELETE targets)</li>"
                "<li><b>Installed Apps</b> - View and manage applications</li>"
                "<li><b>Storage</b> - Find largest files and folders</li>"
                "<li><b>AI Advisor</b> - ML-powered file classification with safety scoring</li>"
                "<li><b>StorageAdvisor</b> - This chatbot. Guides you through safe cleanup.</li>"
                "</ul>"
                f"Running on <b>{os_name}</b>. All actions follow the SAFE_DELETE / REVIEW / DO_NOT_DELETE framework."
            ),
        ),

        # --- Bye ---
        _KBEntry(
            keywords={"bye", "goodbye", "exit", "quit", "close"},
            patterns=["bye", "goodbye", "see you", "that's all"],
            answer=(
                "Goodbye! Remember the golden rule: <b>when in doubt, classify as REVIEW</b> "
                "and inspect before deleting. Stay safe!"
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
        return "Please type a question and I'll help you free space safely!"

    words = set(text.split())

    # Phase 1: exact phrase match (highest priority)
    # Use word boundaries so short patterns like "hi" don't match inside "this"
    for entry in _kb:
        for pattern in entry.patterns:
            if re.search(r"\b" + re.escape(pattern) + r"\b", text):
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
        "I'm not sure about that specific topic. I can only help with "
        "<b>StorageCleaner</b> and safe disk cleanup.<br><br>"
        "Try asking:<br>"
        "<ul>"
        "<li><i>\"What can I safely delete?\"</i> - Quick wins list</li>"
        "<li><i>\"How to free space?\"</i> - Step-by-step guide</li>"
        "<li><i>\"What should I never delete?\"</i> - Hard stops</li>"
        "<li><i>\"Is this folder safe?\"</i> - Classification check</li>"
        "<li><i>\"Storage tips\"</i> - Hygiene recommendations</li>"
        "<li><i>\"How does AI Advisor work?\"</i> - Scoring explained</li>"
        "</ul>"
        "<br>Every recommendation follows the <b>SAFE_DELETE / REVIEW / DO_NOT_DELETE</b> framework."
    )


def get_welcome_message() -> str:
    """Return the initial bot welcome message."""
    os_name = "Windows" if IS_WINDOWS else "Linux"
    return (
        f"Hi! I'm <b>StorageAdvisor</b>, your {os_name} storage assistant.<br><br>"
        "I help you free disk space <b>safely</b>. Every item gets a classification:<br>"
        "<ul>"
        "<li><span style='color:green;'><b>SAFE_DELETE</b></span> - Low-risk, queue for deletion</li>"
        "<li><span style='color:#CC8800;'><b>REVIEW</b></span> - Inspect before removing</li>"
        "<li><span style='color:red;'><b>DO_NOT_DELETE</b></span> - System-critical, hands off</li>"
        "</ul>"
        "<i>Type your question below or click a quick-action button to get started.</i>"
    )
