import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Tuple, List

from core.platform_utils import IS_WINDOWS, IS_LINUX, get_trash_label

@dataclass
class CleanTarget:
    key: str
    title: str
    kind: str  # "folder" or "action"
    path: Optional[Path] = None
    requires_admin: bool = False
    action: Optional[Callable[[], Tuple[bool, str]]] = None

def get_clean_targets(empty_trash_action) -> List[CleanTarget]:
    if IS_WINDOWS:
        return _get_windows_targets(empty_trash_action)
    return _get_linux_targets(empty_trash_action)


def _get_windows_targets(empty_trash_action) -> List[CleanTarget]:
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    localapp = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")

    targets: List[CleanTarget] = [
        CleanTarget("user_temp", "User Temp (%TEMP%)", "folder", Path(tempfile.gettempdir()), False),
        CleanTarget("localapp_temp", "LocalAppData Temp", "folder", Path(localapp) / "Temp" if localapp else None, False),
        CleanTarget("windows_temp", "Windows Temp (C:\\Windows\\Temp)", "folder", windir / "Temp", True),

        CleanTarget("recycle_bin", "Recycle Bin", "action", None, False, empty_trash_action),

        CleanTarget("wu_cache", "Windows Update Cache (SoftwareDistribution\\Download)", "folder",
                    windir / "SoftwareDistribution" / "Download", True),
    ]

    # Browser cache targets
    if localapp:
        chrome_cache = Path(localapp) / "Google" / "Chrome" / "User Data" / "Default" / "Cache"
        chrome_code_cache = Path(localapp) / "Google" / "Chrome" / "User Data" / "Default" / "Code Cache"
        targets += [
            CleanTarget("chrome_cache", "Chrome Cache", "folder", chrome_cache, False),
            CleanTarget("chrome_code_cache", "Chrome Code Cache", "folder", chrome_code_cache, False),
        ]

        edge_cache = Path(localapp) / "Microsoft" / "Edge" / "User Data" / "Default" / "Cache"
        edge_code_cache = Path(localapp) / "Microsoft" / "Edge" / "User Data" / "Default" / "Code Cache"
        targets += [
            CleanTarget("edge_cache", "Edge Cache", "folder", edge_cache, False),
            CleanTarget("edge_code_cache", "Edge Code Cache", "folder", edge_code_cache, False),
        ]

    # Firefox cache (all profiles)
    if appdata:
        profiles_dir = Path(appdata) / "Mozilla" / "Firefox" / "Profiles"
        if profiles_dir.exists():
            for prof in profiles_dir.glob("*"):
                cache2 = prof / "cache2"
                targets.append(CleanTarget(f"firefox_cache_{prof.name}", f"Firefox Cache ({prof.name})", "folder", cache2, False))

    return _filter_targets(targets)


def _get_linux_targets(empty_trash_action) -> List[CleanTarget]:
    home = Path.home()
    cache_dir = home / ".cache"

    targets: List[CleanTarget] = [
        CleanTarget("user_temp", "User Temp (/tmp)", "folder", Path(tempfile.gettempdir()), False),
        CleanTarget("var_tmp", "System Temp (/var/tmp)", "folder", Path("/var/tmp"), True),

        CleanTarget("trash", "Trash", "action", None, False, empty_trash_action),

        # Package manager caches (require root)
        CleanTarget("apt_cache", "APT Package Cache (/var/cache/apt/archives)", "folder",
                    Path("/var/cache/apt/archives"), True),

        # Thumbnail cache
        CleanTarget("thumbnails", "Thumbnail Cache (~/.cache/thumbnails)", "folder",
                    cache_dir / "thumbnails", False),
    ]

    # Chrome cache (Linux path)
    chrome_cache = cache_dir / "google-chrome" / "Default" / "Cache"
    chrome_code_cache = cache_dir / "google-chrome" / "Default" / "Code Cache"
    targets += [
        CleanTarget("chrome_cache", "Chrome Cache", "folder", chrome_cache, False),
        CleanTarget("chrome_code_cache", "Chrome Code Cache", "folder", chrome_code_cache, False),
    ]

    # Chromium cache
    chromium_cache = cache_dir / "chromium" / "Default" / "Cache"
    chromium_code_cache = cache_dir / "chromium" / "Default" / "Code Cache"
    targets += [
        CleanTarget("chromium_cache", "Chromium Cache", "folder", chromium_cache, False),
        CleanTarget("chromium_code_cache", "Chromium Code Cache", "folder", chromium_code_cache, False),
    ]

    # Edge cache (Linux path)
    edge_cache = cache_dir / "microsoft-edge" / "Default" / "Cache"
    edge_code_cache = cache_dir / "microsoft-edge" / "Default" / "Code Cache"
    targets += [
        CleanTarget("edge_cache", "Edge Cache", "folder", edge_cache, False),
        CleanTarget("edge_code_cache", "Edge Code Cache", "folder", edge_code_cache, False),
    ]

    # Firefox cache (Linux path)
    firefox_dir = home / ".mozilla" / "firefox"
    if firefox_dir.exists():
        for prof in firefox_dir.glob("*.default*"):
            cache2 = prof / "cache2"
            targets.append(CleanTarget(f"firefox_cache_{prof.name}", f"Firefox Cache ({prof.name})", "folder", cache2, False))

    return _filter_targets(targets)


def _filter_targets(targets: List[CleanTarget]) -> List[CleanTarget]:
    """Remove targets with None paths (except actions)."""
    out = []
    for t in targets:
        if t.kind == "action":
            out.append(t)
        else:
            if t.path is not None:
                out.append(t)
    return out
