import os
from pathlib import Path
from typing import List, Tuple

from core.utils import get_logger

logger = get_logger("StorageCleaner.drive_scan")

def top_largest_folders(root: Path, top_n=30, max_depth=3) -> List[Tuple[int, str]]:
    """
    Returns list of (size_bytes, folder_path).
    Depth-limited for speed.
    Note: folder size is computed as sum of files directly inside that folder,
    not recursive full folder size (fast). Still useful for hotspots.
    """
    results: List[Tuple[int, str]] = []

    root = root.resolve()
    root_parts = len(root.parts)

    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
        depth = len(Path(dirpath).resolve().parts) - root_parts
        if depth > max_depth:
            dirnames[:] = []
            continue

        folder = Path(dirpath)
        s = 0
        for f in filenames:
            try:
                s += (folder / f).stat().st_size
            except Exception as e:
                logger.debug(f"Cannot stat {folder / f}: {e}")
        results.append((s, str(folder)))

    results.sort(key=lambda x: x[0], reverse=True)
    logger.info(f"Folder scan complete: {root} | found {len(results)} folders, returning top {top_n}")
    return results[:top_n]

def top_largest_files(root: Path, top_n=30, max_depth=4) -> List[Tuple[int, str]]:
    """
    Returns list of (size_bytes, file_path). Depth-limited.
    """
    results: List[Tuple[int, str]] = []

    root = root.resolve()
    root_parts = len(root.parts)

    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
        depth = len(Path(dirpath).resolve().parts) - root_parts
        if depth > max_depth:
            dirnames[:] = []
            continue

        for f in filenames:
            p = Path(dirpath) / f
            try:
                results.append((p.stat().st_size, str(p)))
            except Exception as e:
                logger.debug(f"Cannot stat {p}: {e}")

    results.sort(key=lambda x: x[0], reverse=True)
    logger.info(f"File scan complete: {root} | found {len(results)} files, returning top {top_n}")
    return results[:top_n]
