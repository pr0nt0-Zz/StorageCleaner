import shutil
import subprocess
from typing import Dict, List

from core.utils import get_logger
from core.platform_utils import IS_WINDOWS, IS_LINUX

logger = get_logger("StorageCleaner.apps")


def list_installed_apps() -> List[Dict[str, str]]:
    if IS_WINDOWS:
        return _list_windows_apps()
    return _list_linux_apps()


def _list_windows_apps() -> List[Dict[str, str]]:
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


def _list_linux_apps() -> List[Dict[str, str]]:
    apps: List[Dict[str, str]] = []
    seen = set()

    # dpkg (Debian/Ubuntu)
    if shutil.which("dpkg-query"):
        try:
            result = subprocess.run(
                ["dpkg-query", "-W", "-f", "${Package}|||${Version}|||${Installed-Size}\n"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if not line.strip():
                        continue
                    parts = line.split("|||")
                    if len(parts) >= 3:
                        name = parts[0].strip()
                        if name in seen:
                            continue
                        seen.add(name)
                        version = parts[1].strip()
                        size_kb = parts[2].strip()
                        apps.append({
                            "DisplayName": name,
                            "DisplayVersion": version,
                            "Publisher": "dpkg",
                            "InstallDate": "",
                            "EstimatedSize": size_kb,
                            "UninstallString": f"sudo apt remove {name}",
                        })
        except Exception as e:
            logger.debug(f"dpkg-query failed: {e}")

    # rpm (Fedora/RHEL)
    elif shutil.which("rpm"):
        try:
            result = subprocess.run(
                ["rpm", "-qa", "--queryformat", "%{NAME}|||%{VERSION}|||%{SIZE}\n"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if not line.strip():
                        continue
                    parts = line.split("|||")
                    if len(parts) >= 3:
                        name = parts[0].strip()
                        if name in seen:
                            continue
                        seen.add(name)
                        version = parts[1].strip()
                        # rpm SIZE is in bytes, convert to KB
                        try:
                            size_kb = str(int(parts[2].strip()) // 1024)
                        except ValueError:
                            size_kb = parts[2].strip()
                        apps.append({
                            "DisplayName": name,
                            "DisplayVersion": version,
                            "Publisher": "rpm",
                            "InstallDate": "",
                            "EstimatedSize": size_kb,
                            "UninstallString": f"sudo dnf remove {name}",
                        })
        except Exception as e:
            logger.debug(f"rpm query failed: {e}")

    # Flatpak
    if shutil.which("flatpak"):
        try:
            result = subprocess.run(
                ["flatpak", "list", "--app", "--columns=application,version"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if not line.strip():
                        continue
                    parts = line.split("\t")
                    name = parts[0].strip() if len(parts) >= 1 else ""
                    version = parts[1].strip() if len(parts) >= 2 else ""
                    if name and name not in seen:
                        seen.add(name)
                        apps.append({
                            "DisplayName": name,
                            "DisplayVersion": version,
                            "Publisher": "Flatpak",
                            "InstallDate": "",
                            "EstimatedSize": "",
                            "UninstallString": f"flatpak uninstall {name}",
                        })
        except Exception as e:
            logger.debug(f"flatpak list failed: {e}")

    # Snap
    if shutil.which("snap"):
        try:
            result = subprocess.run(
                ["snap", "list"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                for line in lines[1:]:  # skip header
                    parts = line.split()
                    if len(parts) >= 2:
                        name = parts[0].strip()
                        version = parts[1].strip()
                        if name and name not in seen:
                            seen.add(name)
                            apps.append({
                                "DisplayName": name,
                                "DisplayVersion": version,
                                "Publisher": "Snap",
                                "InstallDate": "",
                                "EstimatedSize": "",
                                "UninstallString": f"sudo snap remove {name}",
                            })
        except Exception as e:
            logger.debug(f"snap list failed: {e}")

    apps.sort(key=lambda a: a.get("DisplayName", "").lower())
    logger.info(f"Listed {len(apps)} installed applications (Linux)")
    return apps
