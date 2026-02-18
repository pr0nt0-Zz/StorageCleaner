import os
import subprocess
from pathlib import Path
from typing import Tuple

from core.utils import get_logger

logger = get_logger("StorageCleaner.cleaner")

def folder_size_bytes(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for root, _, files in os.walk(path, onerror=lambda e: None):
        for f in files:
            try:
                fp = Path(root) / f
                total += fp.stat().st_size
            except Exception as e:
                logger.debug(f"Cannot stat file {root}/{f}: {e}")
    return total

def delete_contents(path: Path) -> Tuple[int, int, int]:
    """
    Delete contents under 'path' (not the folder itself).
    Returns (deleted_files, deleted_dirs, errors)
    """
    deleted_files = 0
    deleted_dirs = 0
    errors = 0

    if not path.exists():
        logger.info(f"Delete target does not exist: {path}")
        return (0, 0, 0)

    logger.info(f"DELETE_START: Cleaning contents of {path}")

    for root, dirs, files in os.walk(path, topdown=False, onerror=lambda e: None):
        for name in files:
            fp = Path(root) / name
            try:
                fp.unlink(missing_ok=True)
                deleted_files += 1
                logger.debug(f"DELETED_FILE: {fp}")
            except Exception as e:
                errors += 1
                logger.warning(f"FAILED_DELETE_FILE: {fp} - {e}")

        for name in dirs:
            dp = Path(root) / name
            try:
                dp.rmdir()  # only empty dirs
                deleted_dirs += 1
                logger.debug(f"DELETED_DIR: {dp}")
            except Exception as e:
                logger.debug(f"SKIP_DIR (in use or not empty): {dp} - {e}")

    logger.info(f"DELETE_DONE: {path} | files={deleted_files} dirs={deleted_dirs} errors={errors}")
    return (deleted_files, deleted_dirs, errors)

def empty_recycle_bin() -> Tuple[bool, str]:
    """
    Clears recycle bin using PowerShell.
    """
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
