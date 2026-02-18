"""
ML-powered file deletion advisor.

Uses statistical outlier detection (z-scores), duplicate file detection
(size + partial MD5 hash), and system file safety awareness to score files
from 0-100 on how likely they are to be safe to delete.

Pure Python -- zero new dependencies beyond the standard library.
Works on Windows and Linux.
"""

import hashlib
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from statistics import mean, stdev
from typing import Callable, Dict, List, Optional, Set, Tuple

from core.file_categories import (
    CATEGORIES, EXTENSION_CATEGORIES, JUNK_EXTENSIONS,
    JUNK_FOLDER_NAMES, TEMP_FOLDER_NAMES, SafetyTier,
    get_protected_dirs, get_protected_extensions, get_known_junk_dirs,
)
from core.utils import get_logger

logger = get_logger("StorageCleaner.ml_advisor")

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FileInfo:
    path: str
    size: int
    accessed: str          # human-readable date
    modified: str          # human-readable date
    extension: str
    category: str          # key from CATEGORIES
    safety: str            # SafetyTier value
    score: int             # 0-100
    confidence: str        # "High" / "Medium" / "Low"
    recommendation: str    # short human-readable advice
    reasons: str           # comma-separated scoring reasons
    duplicate_group: int   # 0 = not a duplicate, >0 = group ID
    is_newest_in_group: bool


@dataclass
class ScanResult:
    files: List[FileInfo]
    duplicates_found: int
    duplicate_space_reclaimable: int
    total_reclaimable: int
    category_summary: Dict[str, Dict]   # {cat_key: {"count": int, "size": int}}
    scan_stats: Dict[str, object]       # miscellaneous info


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SECONDS_IN_YEAR = 365.25 * 24 * 3600
_SECONDS_IN_6_MONTHS = 182.625 * 24 * 3600

_HASH_BLOCK = 4096   # bytes to read from head + tail for partial hash


def _partial_md5(filepath: str) -> Optional[str]:
    """Compute a fast partial MD5: first 4 KB + last 4 KB."""
    try:
        size = os.path.getsize(filepath)
        h = hashlib.md5()
        with open(filepath, "rb") as f:
            h.update(f.read(_HASH_BLOCK))
            if size > _HASH_BLOCK * 2:
                f.seek(-_HASH_BLOCK, 2)
            h.update(f.read(_HASH_BLOCK))
        return h.hexdigest()
    except Exception:
        return None


def _is_under_protected_dir(path_lower: str, protected: Set[str]) -> bool:
    for d in protected:
        if path_lower.startswith(d + os.sep) or path_lower == d:
            return True
    return False


def _is_in_known_junk_dir(path_lower: str, junk_dirs: List[Dict[str, str]]) -> Tuple[bool, str]:
    for entry in junk_dirs:
        junk_path = entry["path"].lower()
        if path_lower.startswith(junk_path + os.sep) or path_lower == junk_path:
            return True, entry["category"]
    return False, ""


# ---------------------------------------------------------------------------
# Core ML scan pipeline
# ---------------------------------------------------------------------------

def ml_scan(
    root: str,
    min_size_mb: int = 50,
    max_depth: int = 6,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> ScanResult:
    """
    Main entry point.  Scans *root* for files >= *min_size_mb* MB and returns
    a ScanResult with scored, categorised, deduplicated file info.

    Pipeline:
        1. Collect files
        2. Compute distribution statistics
        3. Detect duplicates (size + partial hash)
        4. Score each file (rule-based + statistical + duplicate)
        5. Classify safety
        6. Generate recommendations
        7. Build category summary
    """

    protected_dirs = get_protected_dirs()
    protected_exts = get_protected_extensions()
    known_junk = get_known_junk_dirs()
    min_size = min_size_mb * 1024 * 1024

    # --- Phase 1: Collect files -------------------------------------------
    if progress_cb:
        progress_cb(5)

    raw_files: List[dict] = []
    root_path = Path(root).resolve()
    root_parts = len(root_path.parts)

    logger.info(f"ML scan started: root={root} min_size_mb={min_size_mb} max_depth={max_depth}")

    for dirpath, dirnames, filenames in os.walk(root_path, onerror=lambda e: None):
        depth = len(Path(dirpath).resolve().parts) - root_parts
        if depth > max_depth:
            dirnames[:] = []
            continue

        dir_lower = str(Path(dirpath).resolve()).lower()

        # Skip protected directories entirely
        if _is_under_protected_dir(dir_lower, protected_dirs):
            dirnames[:] = []
            continue

        for fname in filenames:
            fp = Path(dirpath) / fname
            try:
                stat = fp.stat()
            except Exception:
                continue

            if stat.st_size < min_size:
                continue

            raw_files.append({
                "path": str(fp),
                "size": stat.st_size,
                "atime": stat.st_atime,
                "mtime": stat.st_mtime,
                "ext": fp.suffix.lower(),
            })

    logger.info(f"Phase 1 done: collected {len(raw_files)} files")
    if progress_cb:
        progress_cb(20)

    if not raw_files:
        return ScanResult(
            files=[], duplicates_found=0, duplicate_space_reclaimable=0,
            total_reclaimable=0, category_summary={}, scan_stats={"files_scanned": 0},
        )

    # --- Phase 2: Statistics ----------------------------------------------
    sizes = [f["size"] for f in raw_files]
    now = time.time()
    ages = [now - f["mtime"] for f in raw_files]

    size_mean = mean(sizes)
    size_sd = stdev(sizes) if len(sizes) > 1 else 1.0
    age_mean = mean(ages)
    age_sd = stdev(ages) if len(ages) > 1 else 1.0

    # Avoid division by zero
    if size_sd == 0:
        size_sd = 1.0
    if age_sd == 0:
        age_sd = 1.0

    logger.info(f"Phase 2 done: size_mean={size_mean:.0f} size_sd={size_sd:.0f} age_mean={age_mean:.0f}")
    if progress_cb:
        progress_cb(30)

    # --- Phase 3: Duplicate detection -------------------------------------
    # Group by size first (fast pre-filter)
    size_groups: Dict[int, List[dict]] = defaultdict(list)
    for f in raw_files:
        size_groups[f["size"]].append(f)

    dup_group_id = 0
    dup_map: Dict[str, int] = {}          # path -> group id
    newest_in_group: Dict[int, str] = {}  # group id -> path of newest file
    total_dup_reclaim = 0

    for sz, group in size_groups.items():
        if len(group) < 2:
            continue

        # Compute partial hash for each file in the same-size group
        hash_buckets: Dict[str, List[dict]] = defaultdict(list)
        for f in group:
            h = _partial_md5(f["path"])
            if h:
                hash_buckets[h].append(f)

        for h, bucket in hash_buckets.items():
            if len(bucket) < 2:
                continue

            dup_group_id += 1
            # Determine newest by mtime
            newest = max(bucket, key=lambda f: f["mtime"])

            for f in bucket:
                dup_map[f["path"]] = dup_group_id
            newest_in_group[dup_group_id] = newest["path"]

            # Reclaimable = size * (copies - 1)
            total_dup_reclaim += sz * (len(bucket) - 1)

    duplicates_found = dup_group_id
    logger.info(f"Phase 3 done: {duplicates_found} duplicate groups, reclaimable={total_dup_reclaim}")
    if progress_cb:
        progress_cb(50)

    # --- Phases 4-6: Score, classify, recommend ---------------------------
    results: List[FileInfo] = []
    total_reclaim = 0

    for idx, f in enumerate(raw_files):
        path = f["path"]
        size = f["size"]
        ext = f["ext"]
        path_lower = path.lower()
        parts_lower = [p.lower() for p in Path(path).parts]

        score = 0
        reasons: List[str] = []

        # ---- Rule-based component (max 50) ----

        # Extension check
        if ext in JUNK_EXTENSIONS:
            score += 15
            reasons.append(f"Junk extension ({ext})")
        elif ext in EXTENSION_CATEGORIES:
            cat_key = EXTENSION_CATEGORIES[ext]
            cat = CATEGORIES.get(cat_key)
            if cat and cat.default_safety == SafetyTier.SAFE:
                score += 10
                reasons.append(f"{cat.label} extension")
            elif ext in {".iso", ".zip", ".rar", ".7z", ".tar", ".gz"}:
                score += 5
                reasons.append("Archive file")

        # Folder location
        if any(name in JUNK_FOLDER_NAMES for name in parts_lower):
            score += 10
            reasons.append("In Downloads folder")

        if any(name in TEMP_FOLDER_NAMES for name in parts_lower):
            score += 15
            reasons.append("In Temp/Cache folder")

        # Known junk directory
        in_junk, junk_cat = _is_in_known_junk_dir(path_lower, known_junk)
        if in_junk:
            score += 10
            reasons.append("In known junk directory")

        # ---- Statistical component (max 30) ----

        size_z = (size - size_mean) / size_sd
        age = now - f["mtime"]
        age_z = (age - age_mean) / age_sd

        if size_z > 1:
            pts = min(int(5 * size_z), 15)
            score += pts
            reasons.append(f"Unusually large (z={size_z:.1f})")

        if age_z > 1:
            pts = min(int(5 * age_z), 15)
            score += pts
            reasons.append(f"Unusually old (z={age_z:.1f})")

        # Age checks (flat bonuses like original advisor)
        age_accessed = now - f["atime"]
        if age_accessed > _SECONDS_IN_YEAR and "old" not in " ".join(reasons).lower():
            reasons.append("Not accessed in >1 year")

        if age > _SECONDS_IN_YEAR and "old" not in " ".join(reasons).lower():
            reasons.append("Not modified in >1 year")

        # ---- Duplicate component (max 20) ----

        dup_gid = dup_map.get(path, 0)
        is_newest = (dup_gid > 0 and newest_in_group.get(dup_gid) == path)

        if dup_gid > 0 and not is_newest:
            score += 20
            reasons.append("Duplicate copy (not newest)")
        elif dup_gid > 0 and is_newest:
            reasons.append("Duplicate (newest copy - kept)")

        # Clamp
        score = min(score, 100)

        # ---- Safety override ----
        is_protected = False
        if ext in get_protected_extensions():
            is_protected = True
        if _is_under_protected_dir(path_lower, protected_dirs):
            is_protected = True

        if is_protected:
            score = 0
            safety = SafetyTier.PROTECTED
        elif score >= 60:
            safety = SafetyTier.SAFE
        elif score >= 30:
            safety = SafetyTier.REVIEW
        else:
            safety = SafetyTier.UNKNOWN

        # ---- Category ----
        if dup_gid > 0 and not is_newest:
            category = "duplicate"
        elif in_junk:
            category = junk_cat
        elif ext in EXTENSION_CATEGORIES:
            category = EXTENSION_CATEGORIES[ext]
        elif any(name in JUNK_FOLDER_NAMES for name in parts_lower):
            category = "old_download"
        elif any(name in TEMP_FOLDER_NAMES for name in parts_lower):
            category = "cache_temp"
        elif age > _SECONDS_IN_YEAR:
            category = "large_unused"
        else:
            category = "large_unused"

        # ---- Confidence ----
        if score >= 70:
            confidence = "High"
        elif score >= 40:
            confidence = "Medium"
        else:
            confidence = "Low"

        # ---- Recommendation ----
        cat_label = CATEGORIES.get(category, CATEGORIES["large_unused"]).label
        if safety == SafetyTier.PROTECTED:
            recommendation = "KEEP - System/protected file"
        elif safety == SafetyTier.SAFE:
            if dup_gid > 0 and not is_newest:
                recommendation = "SAFE TO DELETE - Duplicate copy"
            else:
                recommendation = f"SAFE TO DELETE - {cat_label}"
        elif safety == SafetyTier.REVIEW:
            recommendation = f"REVIEW - {cat_label}"
        else:
            recommendation = f"REVIEW - {cat_label}"

        # ---- Build FileInfo ----
        fi = FileInfo(
            path=path,
            size=size,
            accessed=datetime.fromtimestamp(f["atime"]).strftime("%Y-%m-%d"),
            modified=datetime.fromtimestamp(f["mtime"]).strftime("%Y-%m-%d"),
            extension=ext,
            category=category,
            safety=safety,
            score=score,
            confidence=confidence,
            recommendation=recommendation,
            reasons=", ".join(reasons) if reasons else "Large file",
            duplicate_group=dup_gid,
            is_newest_in_group=is_newest,
        )

        # Only include non-protected files
        if safety != SafetyTier.PROTECTED:
            results.append(fi)
            total_reclaim += size

        # Progress: 50-90% over file scoring
        if progress_cb and len(raw_files) > 0 and (idx + 1) % max(len(raw_files) // 10, 1) == 0:
            pct = 50 + int(40 * (idx + 1) / len(raw_files))
            progress_cb(min(pct, 90))

    # Sort by score descending
    results.sort(key=lambda fi: fi.score, reverse=True)

    # --- Phase 7: Category summary ----------------------------------------
    cat_summary: Dict[str, Dict] = {}
    for fi in results:
        if fi.category not in cat_summary:
            cat_summary[fi.category] = {"count": 0, "size": 0}
        cat_summary[fi.category]["count"] += 1
        cat_summary[fi.category]["size"] += fi.size

    if progress_cb:
        progress_cb(100)

    logger.info(
        f"ML scan done: {len(results)} files, total_reclaimable={total_reclaim}, "
        f"duplicates={duplicates_found}, dup_reclaim={total_dup_reclaim}"
    )

    return ScanResult(
        files=results,
        duplicates_found=duplicates_found,
        duplicate_space_reclaimable=total_dup_reclaim,
        total_reclaimable=total_reclaim,
        category_summary=cat_summary,
        scan_stats={
            "files_scanned": len(raw_files),
            "files_returned": len(results),
            "size_mean": size_mean,
            "size_stdev": size_sd,
            "age_mean_days": age_mean / 86400,
        },
    )
