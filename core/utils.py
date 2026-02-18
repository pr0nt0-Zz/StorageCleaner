import os
import logging
import logging.handlers
from pathlib import Path

from core.platform_utils import (
    IS_WINDOWS, IS_LINUX,
    get_app_data_dir,
    is_admin as _platform_is_admin,
    detect_all_storage,
    storage_exists as _platform_storage_exists,
    storage_usage as _platform_storage_usage,
    open_in_file_manager as _platform_open_in_file_manager,
)

# Configure logging with both console and file output
LOG_DIR = get_app_data_dir() / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "storagecleaner.log"

_logger = logging.getLogger("StorageCleaner")
_logger.setLevel(logging.DEBUG)

if not _logger.handlers:
    _console_handler = logging.StreamHandler()
    _console_handler.setLevel(logging.INFO)
    _console_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))

    _file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    _file_handler.setLevel(logging.DEBUG)
    _file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s'))

    _logger.addHandler(_console_handler)
    _logger.addHandler(_file_handler)

def get_logger(name: str = "StorageCleaner") -> logging.Logger:
    return logging.getLogger(name)

def human_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    x = float(n)
    for u in units:
        if x < 1024 or u == units[-1]:
            return f"{x:.2f} {u}"
        x /= 1024
    return f"{n} B"

def is_admin() -> bool:
    return _platform_is_admin()

def drive_exists(letter: str) -> bool:
    """Backward-compat wrapper. On Linux, checks storage_id instead."""
    return _platform_storage_exists(letter)

def detect_all_drives() -> list:
    """
    Backward-compat wrapper. Returns list of dicts with 'letter' key on Windows,
    'id' mapped to 'letter' for compatibility.
    """
    storages = detect_all_storage()
    # Map to old format with 'letter' key for backward compatibility
    result = []
    for s in storages:
        result.append({
            "letter": s["id"],
            "label": s["label"],
            "path": s["path"],
            "total": s["total"],
            "used": s["used"],
            "free": s["free"],
        })
    return result

def drive_usage(drive_root: str):
    """Returns (total, used, free) bytes."""
    return _platform_storage_usage(drive_root)

def open_in_explorer(path: str):
    """Backward-compat wrapper for open_in_file_manager."""
    _platform_open_in_file_manager(path)

def size_class(n_bytes: int) -> str:
    gb = 1024 ** 3
    mb = 1024 ** 2

    if n_bytes >= 10 * gb:
        return "GIGANTIC"
    if n_bytes >= 1 * gb:
        return "HUGE"
    if n_bytes >= 200 * mb:
        return "LARGE"
    if n_bytes >= 50 * mb:
        return "MEDIUM"
    return "SMALL"

def score_label(score: int) -> str:
    if score >= 70:
        return "HIGH RISK"
    if score >= 40:
        return "MEDIUM RISK"
    return "LOW RISK"
