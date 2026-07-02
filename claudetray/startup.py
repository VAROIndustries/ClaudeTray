"""Windows run-on-startup registration via the HKCU Run registry key."""
import os
import sys
import winreg
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "ClaudeTray"


def _default_legacy_dir() -> Path:
    return (
        Path(os.environ.get("APPDATA", ""))
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
    )


def _launch_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" -m claudetray'


def set_run_on_startup(enable: bool, key_path: str = RUN_KEY, legacy_dir: Path = None):
    """Register or unregister the app in the HKCU Run key.

    Also removes the legacy Startup-folder shortcut from pre-v0.3.2 builds.
    """
    _remove_legacy_shortcut(legacy_dir or _default_legacy_dir())
    if enable:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
        with key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _launch_command())
    else:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.DeleteValue(key, APP_NAME)
        except OSError:
            pass


def is_registered(key_path: str = RUN_KEY) -> bool:
    return get_registered_command(key_path) is not None


def get_registered_command(key_path: str = RUN_KEY):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return value
    except OSError:
        return None


def _remove_legacy_shortcut(startup_dir: Path):
    shortcut = startup_dir / f"{APP_NAME}.lnk"
    try:
        if shortcut.exists():
            shortcut.unlink()
    except OSError:
        pass
