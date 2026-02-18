import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# Time constants
_SECONDS_IN_YEAR = 365.25 * 24 * 3600
_SECONDS_IN_6_MONTHS = 182.625 * 24 * 3600

_JUNK_EXTENSIONS = {".tmp", ".log", ".bak", ".old", ".dmp", ".temp"}
_ARCHIVE_EXTENSIONS = {".iso", ".zip", ".rar", ".7z"}
_JUNK_FOLDER_NAMES = {"downloads"}
_TEMP_FOLDER_NAMES = {"temp", "tmp", "cache"}


def compute_junk_score(path: str, size: int, accessed: float, modified: float) -> Tuple[int, List[str]]:
    """
    Rate a file from 0-100 on how likely it is to be junk.
    Returns (score, list_of_reasons).
    """
    score = 0
    reasons: List[str] = []
    now = time.time()

    p = Path(path)
    ext = p.suffix.lower()
    parts_lower = [part.lower() for part in p.parts]

    # Extension checks
    if ext in _JUNK_EXTENSIONS:
        score += 25
        reasons.append(f"Junk extension ({ext})")
    elif ext in _ARCHIVE_EXTENSIONS:
        score += 5
        reasons.append("Archive file")

    # Folder location checks
    if any(name in _JUNK_FOLDER_NAMES for name in parts_lower):
        score += 20
        reasons.append("In Downloads folder")

    if any(name in _TEMP_FOLDER_NAMES for name in parts_lower):
        score += 15
        reasons.append("In Temp/Cache folder")

    # Age checks
    age_accessed = now - accessed
    age_modified = now - modified

    if age_accessed > _SECONDS_IN_YEAR:
        score += 20
        reasons.append("Not accessed in >1 year")

    if age_modified > _SECONDS_IN_YEAR:
        score += 10
        reasons.append("Not modified in >1 year")
    elif age_modified > _SECONDS_IN_6_MONTHS:
        score += 5
        reasons.append("Not modified in >6 months")

    # Size check
    if size > 1024 ** 3:
        score += 5
        reasons.append("Very large file (>1GB)")

    return min(score, 100), reasons


def scan_stale_files(root: str, min_size_mb: int = 500, max_depth: int = 5) -> List[Dict]:
    """
    Scan a drive for large files not accessed or modified in over 1 year.
    Returns list of dicts sorted by score descending.
    """
    results: List[Dict] = []
    min_size = min_size_mb * 1024 * 1024
    now = time.time()
    one_year_ago = now - _SECONDS_IN_YEAR

    root_path = Path(root).resolve()
    root_parts = len(root_path.parts)

    for dirpath, dirnames, filenames in os.walk(root_path, onerror=lambda e: None):
        depth = len(Path(dirpath).resolve().parts) - root_parts
        if depth > max_depth:
            dirnames[:] = []
            continue

        for f in filenames:
            fp = Path(dirpath) / f
            try:
                stat = fp.stat()
            except Exception:
                continue

            if stat.st_size < min_size:
                continue

            # At least one of access/modify must be older than 1 year
            if stat.st_atime > one_year_ago and stat.st_mtime > one_year_ago:
                continue

            score, reasons = compute_junk_score(
                str(fp), stat.st_size, stat.st_atime, stat.st_mtime
            )

            results.append({
                "path": str(fp),
                "size": stat.st_size,
                "accessed": datetime.fromtimestamp(stat.st_atime).strftime("%Y-%m-%d"),
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d"),
                "score": score,
                "reasons": ", ".join(reasons),
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results
