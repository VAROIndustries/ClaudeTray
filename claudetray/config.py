import json
import os
from pathlib import Path

CLAUDETRAY_DIR = Path.home() / ".claudetray"
CONFIG_PATH = CLAUDETRAY_DIR / "settings.json"
DB_PATH = CLAUDETRAY_DIR / "history.db"

DEFAULTS = {
    "run_on_startup": False,
    "refresh_interval_active": 5,
    "refresh_interval_idle": 60,
    "api_key": None,
    "dashboard_port": 5199,
    "theme": "dark",
    "data_retention_days": 30,
    "statusline_path": None,
}


def _detect_statusline_path() -> Path:
    candidates = [
        Path(os.environ.get("TEMP", "")) / "statusline_debug.json",
        Path(os.environ.get("TMP", "")) / "statusline_debug.json",
        Path("/tmp") / "statusline_debug.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return Path(os.environ.get("TEMP", "/tmp")) / "statusline_debug.json"


class Config:
    def __init__(self, path: Path = CONFIG_PATH):
        self.path = path
        self._data = dict(DEFAULTS)
        self.load()

    def load(self):
        if self.path.exists():
            with open(self.path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            self._data.update(saved)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key, default=None):
        if key not in self._data:
            return default
        return self._data[key]

    def set(self, key, value):
        self._data[key] = value
        self.save()

    @property
    def statusline_path(self) -> Path:
        custom = self._data.get("statusline_path")
        if custom:
            return Path(custom)
        return _detect_statusline_path()
