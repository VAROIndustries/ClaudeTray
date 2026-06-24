import json
from pathlib import Path
from claudetray.config import Config, DEFAULTS


def test_config_loads_defaults(tmp_path):
    cfg = Config(path=tmp_path / "settings.json")
    assert cfg.get("run_on_startup") is False
    assert cfg.get("refresh_interval_active") == 5
    assert cfg.get("dashboard_port") == 5199
    assert cfg.get("theme") == "dark"
    assert cfg.get("data_retention_days") == 30


def test_config_save_and_reload(tmp_path):
    path = tmp_path / "settings.json"
    cfg = Config(path=path)
    cfg.set("theme", "light")
    cfg.set("dashboard_port", 9999)

    cfg2 = Config(path=path)
    assert cfg2.get("theme") == "light"
    assert cfg2.get("dashboard_port") == 9999
    assert cfg2.get("run_on_startup") is False  # unchanged default


def test_config_statusline_path_default(tmp_path):
    cfg = Config(path=tmp_path / "settings.json")
    p = cfg.statusline_path
    assert p.name == "statusline_debug.json"


def test_config_statusline_path_custom(tmp_path):
    path = tmp_path / "settings.json"
    cfg = Config(path=path)
    cfg.set("statusline_path", str(tmp_path / "custom.json"))
    assert cfg.statusline_path == tmp_path / "custom.json"


def test_config_get_missing_key_returns_default(tmp_path):
    cfg = Config(path=tmp_path / "settings.json")
    assert cfg.get("nonexistent", "fallback") == "fallback"


def test_config_creates_parent_dirs(tmp_path):
    path = tmp_path / "subdir" / "deep" / "settings.json"
    cfg = Config(path=path)
    cfg.set("theme", "dark")
    assert path.exists()
