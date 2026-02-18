import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Tuple, List

@dataclass
class CleanTarget:
    key: str
    title: str
    kind: str  # "folder" or "action"
    path: Optional[Path] = None
    requires_admin: bool = False
    action: Optional[Callable[[], Tuple[bool, str]]] = None

def get_clean_targets(empty_recycle_bin_action) -> List[CleanTarget]:
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    localapp = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")

    targets: List[CleanTarget] = [
        CleanTarget("user_temp", "User Temp (%TEMP%)", "folder", Path(tempfile.gettempdir()), False),
        CleanTarget("localapp_temp", "LocalAppData Temp", "folder", Path(localapp) / "Temp" if localapp else None, False),
        CleanTarget("windows_temp", "Windows Temp (C:\\Windows\\Temp)", "folder", windir / "Temp", True),

        CleanTarget("recycle_bin", "Recycle Bin", "action", None, False, empty_recycle_bin_action),

        # Optional but useful (often large). Needs admin, can fail if Windows Update services lock it.
        CleanTarget("wu_cache", "Windows Update Cache (SoftwareDistribution\\Download)", "folder",
                    windir / "SoftwareDistribution" / "Download", True),
    ]

    # Browser cache targets (cache only; NOT cookies/passwords)
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

    # Remove None paths
    out = []
    for t in targets:
        if t.kind == "action":
            out.append(t)
        else:
            if t.path is not None:
                out.append(t)
    return out
