"""
Platform abstraction layer for StorageCleaner.
Centralizes all OS-specific logic so the rest of the app stays cross-platform.
"""

import os
import sys
import shutil
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Tuple

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

logger = logging.getLogger("StorageCleaner.platform")


# -------------------------
# Paths & Directories
# -------------------------

def get_app_data_dir() -> Path:
    if IS_WINDOWS:
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))
    return Path(base) / "StorageCleaner"


def get_default_font() -> str:
    if IS_WINDOWS:
        return "Segoe UI"
    return "Sans"


# -------------------------
# Admin / Elevation
# -------------------------

def is_admin() -> bool:
    if IS_WINDOWS:
        try:
            p = subprocess.run(["net", "session"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return p.returncode == 0
        except Exception as e:
            logger.warning(f"Admin check failed: {e}")
            return False
    else:
        try:
            return os.geteuid() == 0
        except AttributeError:
            return False


def get_elevation_hint() -> str:
    if IS_WINDOWS:
        return "right-click EXE -> Run as administrator"
    return "run with sudo"


# -------------------------
# Storage Detection
# -------------------------

def detect_all_storage() -> List[Dict]:
    """
    Detect available storage locations.
    Returns list of dicts:
      {"id": str, "label": str, "path": str, "total": int, "used": int, "free": int}

    Windows: scan drive letters A-Z
    Linux: parse /proc/mounts for real filesystems
    """
    if IS_WINDOWS:
        return _detect_windows_drives()
    return _detect_linux_mounts()


def _detect_windows_drives() -> List[Dict]:
    import string
    drives = []
    for letter in string.ascii_uppercase:
        root = f"{letter}:\\"
        if os.path.exists(root):
            try:
                total, used, free = shutil.disk_usage(root)
                drives.append({
                    "id": letter,
                    "label": f"{letter}:",
                    "path": root,
                    "total": total,
                    "used": used,
                    "free": free,
                })
            except Exception:
                pass
    return drives


def _detect_linux_mounts() -> List[Dict]:
    mounts = []
    seen_devices = set()

    # Interesting mount points
    interesting_prefixes = ("/", "/home", "/mnt/", "/media/", "/opt", "/var")

    # Virtual/pseudo filesystems to skip
    skip_fs_types = {
        "sysfs", "proc", "devtmpfs", "devpts", "tmpfs", "securityfs",
        "cgroup", "cgroup2", "pstore", "efivarfs", "bpf", "autofs",
        "hugetlbfs", "mqueue", "debugfs", "tracefs", "fusectl",
        "configfs", "ramfs", "binfmt_misc", "overlay", "nsfs",
        "fuse.snapfuse", "squashfs", "fuse.portal",
    }

    try:
        with open("/proc/mounts", "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 3:
                    continue
                device, mount_point, fs_type = parts[0], parts[1], parts[2]

                if fs_type in skip_fs_types:
                    continue

                if device in seen_devices:
                    continue

                # Only include real-looking mount points
                if not any(mount_point == p or mount_point.startswith(p) for p in interesting_prefixes):
                    continue

                try:
                    total, used, free = shutil.disk_usage(mount_point)
                    if total == 0:
                        continue
                    seen_devices.add(device)

                    # Create a short id from mount point
                    if mount_point == "/":
                        sid = "root"
                    else:
                        sid = mount_point.strip("/").replace("/", "_")

                    mounts.append({
                        "id": sid,
                        "label": mount_point,
                        "path": mount_point,
                        "total": total,
                        "used": used,
                        "free": free,
                    })
                except Exception:
                    pass
    except FileNotFoundError:
        # Fallback: just check / and /home
        for mp in ["/", "/home"]:
            if os.path.exists(mp):
                try:
                    total, used, free = shutil.disk_usage(mp)
                    sid = "root" if mp == "/" else mp.strip("/").replace("/", "_")
                    mounts.append({
                        "id": sid,
                        "label": mp,
                        "path": mp,
                        "total": total,
                        "used": used,
                        "free": free,
                    })
                except Exception:
                    pass

    return mounts


def storage_exists(storage_id: str) -> bool:
    if IS_WINDOWS:
        root = f"{storage_id}:\\"
        return os.path.exists(root)
    else:
        for s in detect_all_storage():
            if s["id"] == storage_id:
                return True
        return False


def get_storage_path(storage_id: str) -> str:
    if IS_WINDOWS:
        return f"{storage_id}:\\"
    else:
        for s in detect_all_storage():
            if s["id"] == storage_id:
                return s["path"]
        # fallback
        if storage_id == "root":
            return "/"
        return f"/{storage_id.replace('_', '/')}"


def storage_usage(storage_path: str) -> Tuple[int, int, int]:
    total, used, free = shutil.disk_usage(storage_path)
    return total, used, free


# -------------------------
# File Manager / Text Editor
# -------------------------

def open_in_file_manager(path: str):
    try:
        p = Path(path)
        if IS_WINDOWS:
            if p.exists() and p.is_file():
                subprocess.run(["explorer", "/select,", str(p)], check=False)
            else:
                subprocess.run(["explorer", str(p)], check=False)
        else:
            # xdg-open opens the parent directory for files
            target = str(p.parent) if p.exists() and p.is_file() else str(p)
            subprocess.run(["xdg-open", target], check=False)
    except Exception as e:
        logger.warning(f"Failed to open in file manager: {path}: {e}")


def open_text_file(path: str):
    try:
        if IS_WINDOWS:
            subprocess.run(["notepad", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
    except Exception as e:
        logger.warning(f"Failed to open text file: {path}: {e}")


# -------------------------
# Trash / Recycle Bin
# -------------------------

def empty_trash() -> Tuple[bool, str]:
    if IS_WINDOWS:
        return _empty_windows_recycle_bin()
    return _empty_linux_trash()


def _empty_windows_recycle_bin() -> Tuple[bool, str]:
    logger.info("DELETE_START: Emptying Recycle Bin")
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Clear-RecycleBin -Force"],
            capture_output=True, text=True
        )
        if p.returncode == 0:
            logger.info("DELETE_DONE: Recycle Bin emptied successfully")
            return (True, "Recycle Bin emptied.")
        msg = (p.stderr or p.stdout or "Failed to empty Recycle Bin.").strip()
        logger.warning(f"DELETE_FAILED: Recycle Bin - {msg}")
        return (False, msg)
    except Exception as e:
        logger.error(f"DELETE_ERROR: Recycle Bin - {e}")
        return (False, f"Exception: {e}")


def _empty_linux_trash() -> Tuple[bool, str]:
    logger.info("DELETE_START: Emptying Trash")
    trash_dir = Path.home() / ".local" / "share" / "Trash"
    deleted = 0
    errors = 0

    for sub in ["files", "info"]:
        target = trash_dir / sub
        if not target.exists():
            continue
        for item in target.iterdir():
            try:
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
                deleted += 1
            except Exception as e:
                errors += 1
                logger.warning(f"Failed to delete trash item {item}: {e}")

    if deleted > 0 or errors == 0:
        logger.info(f"DELETE_DONE: Trash emptied ({deleted} items, {errors} errors)")
        return (True, f"Trash emptied ({deleted} items removed).")
    return (False, f"Trash empty failed ({errors} errors).")


# -------------------------
# System Apps Settings
# -------------------------

def open_system_apps_settings():
    try:
        if IS_WINDOWS:
            subprocess.run(["cmd", "/c", "start", "ms-settings:appsfeatures"], shell=False)
        else:
            # Try common Linux app managers
            for cmd in ["gnome-software", "snap-store", "plasma-discover"]:
                if shutil.which(cmd):
                    subprocess.Popen([cmd])
                    return
            # Fallback: open system settings
            subprocess.run(["xdg-open", "file:///usr/share/applications"], check=False)
    except Exception as e:
        logger.warning(f"Failed to open system apps settings: {e}")


def get_trash_label() -> str:
    return "Recycle Bin" if IS_WINDOWS else "Trash"
