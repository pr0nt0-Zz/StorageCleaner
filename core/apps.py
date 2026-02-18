from typing import Dict, List

from core.utils import get_logger

logger = get_logger("StorageCleaner.apps")

def list_installed_apps() -> List[Dict[str, str]]:
    import winreg

    uninstall_keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    fields = ["DisplayName", "DisplayVersion", "Publisher", "InstallDate", "EstimatedSize", "UninstallString"]

    def read_value(key, name):
        try:
            val, _ = winreg.QueryValueEx(key, name)
            return val
        except OSError:
            return None

    apps = []
    seen = set()

    for hive, path in uninstall_keys:
        try:
            with winreg.OpenKey(hive, path) as root:
                subcount = winreg.QueryInfoKey(root)[0]
                for i in range(subcount):
                    try:
                        sub_name = winreg.EnumKey(root, i)
                        with winreg.OpenKey(root, sub_name) as sub:
                            dn = read_value(sub, "DisplayName")
                            if not dn:
                                continue
                            if dn in seen:
                                continue
                            seen.add(dn)

                            row = {f: read_value(sub, f) for f in fields}
                            out = {}
                            for k, v in row.items():
                                out[k] = "" if v is None else str(v)
                            apps.append(out)
                    except OSError as e:
                        logger.debug(f"Failed to read registry subkey {i} under {path}: {e}")
        except OSError as e:
            logger.debug(f"Failed to open registry key {path}: {e}")

    apps.sort(key=lambda a: a.get("DisplayName", "").lower())
    logger.info(f"Listed {len(apps)} installed applications")
    return apps
