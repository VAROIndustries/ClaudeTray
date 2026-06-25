"""Build ClaudeTray into a standalone .exe using PyInstaller."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
ENTRY = ROOT / "claudetray" / "app.py"
TEMPLATES = ROOT / "claudetray" / "dashboard" / "templates"
STATIC = ROOT / "claudetray" / "dashboard" / "static"
ICON = ROOT / "assets" / "icon.ico"


def build():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "ClaudeTray",
        "--add-data", f"{TEMPLATES};claudetray/dashboard/templates",
        "--add-data", f"{STATIC};claudetray/dashboard/static",
    ]
    if ICON.exists():
        cmd.extend(["--icon", str(ICON)])
    cmd.append(str(ENTRY))

    print(f"Building ClaudeTray...")
    subprocess.run(cmd, check=True)
    print(f"\nBuild complete! Executable at: dist/ClaudeTray.exe")


if __name__ == "__main__":
    build()
