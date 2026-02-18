"""
File category definitions, protected paths, and extension mappings
for the AI-powered file deletion advisor.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, FrozenSet, List, Set

from core.platform_utils import IS_WINDOWS, IS_LINUX


# --- Safety Tiers ---

class SafetyTier:
    PROTECTED = "protected"
    SAFE = "safe"
    REVIEW = "review"
    UNKNOWN = "unknown"


# --- File Categories ---

@dataclass(frozen=True)
class FileCategory:
    key: str
    label: str
    description: str
    default_safety: str


CATEGORIES: Dict[str, FileCategory] = {
    "cache_temp": FileCategory("cache_temp", "Cache & Temp Files",
        "Temporary and cache files that can be safely removed", SafetyTier.SAFE),
    "duplicate": FileCategory("duplicate", "Duplicate Files",
        "Duplicate copies of files wasting space", SafetyTier.SAFE),
    "old_download": FileCategory("old_download", "Old Downloads",
        "Old files in download directories", SafetyTier.REVIEW),
    "large_unused": FileCategory("large_unused", "Large Unused Files",
        "Large files not accessed or modified in a long time", SafetyTier.REVIEW),
    "log_file": FileCategory("log_file", "Log Files",
        "Log files that can usually be cleaned up", SafetyTier.SAFE),
    "package_cache": FileCategory("package_cache", "Package Cache",
        "Cached package manager downloads", SafetyTier.SAFE),
    "old_media": FileCategory("old_media", "Old Media Files",
        "Old video, audio, or image files", SafetyTier.REVIEW),
    "archive": FileCategory("archive", "Archive Files",
        "Compressed archives (.zip, .iso, .tar, etc.)", SafetyTier.REVIEW),
    "build_artifact": FileCategory("build_artifact", "Build Artifacts",
        "Compiled objects, bytecode, and build outputs", SafetyTier.SAFE),
}


# --- Extension to Category Mapping ---

EXTENSION_CATEGORIES: Dict[str, str] = {
    # cache_temp
    ".tmp": "cache_temp", ".temp": "cache_temp", ".cache": "cache_temp",
    ".bak": "cache_temp", ".old": "cache_temp", ".dmp": "cache_temp",
    ".swp": "cache_temp", ".swo": "cache_temp",

    # log_file
    ".log": "log_file",

    # archive
    ".iso": "archive", ".zip": "archive", ".rar": "archive",
    ".7z": "archive", ".tar": "archive", ".gz": "archive",
    ".bz2": "archive", ".xz": "archive", ".tgz": "archive",
    ".tbz2": "archive", ".zst": "archive",

    # old_media
    ".mp4": "old_media", ".avi": "old_media", ".mkv": "old_media",
    ".mov": "old_media", ".wmv": "old_media", ".flv": "old_media",
    ".webm": "old_media", ".flac": "old_media", ".wav": "old_media",
    ".m4a": "old_media", ".m4v": "old_media",

    # build_artifact
    ".o": "build_artifact", ".obj": "build_artifact",
    ".pyc": "build_artifact", ".pyo": "build_artifact",
    ".class": "build_artifact", ".elc": "build_artifact",
    ".whl": "build_artifact",
}

# Junk extensions (high score)
JUNK_EXTENSIONS: FrozenSet[str] = frozenset({
    ".tmp", ".temp", ".cache", ".bak", ".old", ".dmp", ".swp", ".swo", ".log",
})

# Junk folder names
JUNK_FOLDER_NAMES: FrozenSet[str] = frozenset({
    "downloads", "download",
})

# Temp/cache folder names
TEMP_FOLDER_NAMES: FrozenSet[str] = frozenset({
    "temp", "tmp", "cache", ".cache", "__pycache__",
})


# --- Protected Paths ---

def get_protected_dirs() -> Set[str]:
    """Directories whose files should NEVER be suggested for deletion."""
    dirs: Set[str] = set()

    if IS_WINDOWS:
        import os
        windir = os.environ.get("WINDIR", r"C:\Windows")
        progfiles = os.environ.get("ProgramFiles", r"C:\Program Files")
        progfiles86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        dirs.update({
            windir.lower(),
            (windir + "\\System32").lower(),
            (windir + "\\SysWOW64").lower(),
            (windir + "\\WinSxS").lower(),
            progfiles.lower(),
            progfiles86.lower(),
            r"c:\programdata\microsoft".lower(),
        })
    else:
        dirs.update({
            "/usr/bin", "/usr/lib", "/usr/lib64", "/usr/sbin",
            "/usr/share", "/usr/include",
            "/bin", "/sbin", "/lib", "/lib64", "/lib32",
            "/etc", "/boot",
            "/var/lib/dpkg", "/var/lib/apt/lists",
            "/var/lib/rpm",
            "/snap/core", "/snap/snapd",
            "/proc", "/sys", "/dev", "/run",
        })

    return dirs


def get_protected_extensions() -> FrozenSet[str]:
    """Extensions that indicate system-critical files."""
    common = {".conf", ".cfg", ".ini", ".service", ".timer", ".socket", ".mount"}
    if IS_WINDOWS:
        return frozenset(common | {".sys", ".dll", ".drv", ".msi", ".reg", ".cat"})
    else:
        return frozenset(common | {".so", ".ko", ".deb", ".rpm", ".desktop"})


# --- Known Junk Directories ---

def get_known_junk_dirs() -> List[Dict[str, str]]:
    """
    Known directories whose contents are typically safe to suggest deleting.
    Returns list of {"path": str, "category": str, "description": str}.
    """
    dirs: List[Dict[str, str]] = []

    if IS_LINUX:
        home = str(Path.home())
        dirs += [
            {"path": f"{home}/.cache", "category": "cache_temp",
             "description": "User cache directory"},
            {"path": "/var/cache/apt/archives", "category": "package_cache",
             "description": "APT package cache"},
            {"path": "/var/cache/apt/archives/partial", "category": "package_cache",
             "description": "APT partial downloads"},
            {"path": "/var/cache/PackageKit", "category": "package_cache",
             "description": "PackageKit cache"},
            {"path": "/var/lib/snapd/cache", "category": "package_cache",
             "description": "Snap daemon cache"},
            {"path": f"{home}/.local/share/Trash", "category": "cache_temp",
             "description": "Trash contents"},
            {"path": "/var/log", "category": "log_file",
             "description": "System logs"},
            {"path": "/tmp", "category": "cache_temp",
             "description": "Temporary files"},
            {"path": "/var/tmp", "category": "cache_temp",
             "description": "Persistent temp files"},
            {"path": "/var/lib/docker/overlay2", "category": "cache_temp",
             "description": "Docker image layers"},
        ]
    elif IS_WINDOWS:
        import os, tempfile
        localapp = os.environ.get("LOCALAPPDATA", "")
        dirs += [
            {"path": tempfile.gettempdir(), "category": "cache_temp",
             "description": "User temp directory"},
        ]
        if localapp:
            dirs.append({"path": f"{localapp}\\Temp", "category": "cache_temp",
                         "description": "LocalAppData Temp"})

    return dirs
