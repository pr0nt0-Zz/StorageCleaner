import os
import shutil
import subprocess
import logging
import logging.handlers
from pathlib import Path

# Configure logging with both console and file output
LOG_DIR = Path(os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))) / "StorageCleaner" / "logs"
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
    # lightweight admin detection for Windows
    try:
        p = subprocess.run(["net", "session"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return p.returncode == 0
    except Exception as e:
        logging.warning(f"Admin check failed: {e}")
        return False

def safe_path_exists(p: Path) -> bool:
    try:
        return p.exists()
    except Exception as e:
        logging.warning(f"Path existence check failed for {p}: {e}")
        return False

def drive_exists(letter: str) -> bool:
    root = f"{letter}:\\"
    return os.path.exists(root)

def drive_usage(drive_root: str):
    # returns (total, used, free) bytes
    total, used, free = shutil.disk_usage(drive_root)
    return total, used, free

def open_in_explorer(path: str):
    # Open folder or select file
    try:
        p = Path(path)
        if p.exists() and p.is_file():
            subprocess.run(["explorer", "/select,", str(p)], check=False)
        else:
            subprocess.run(["explorer", str(p)], check=False)
    except Exception as e:
        logging.warning(f"Failed to open in explorer: {path}: {e}")
        # fallback: just try explorer with raw path
        subprocess.run(["explorer", path], check=False)

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

