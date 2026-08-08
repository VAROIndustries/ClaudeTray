"""Tests for the tray menu, focused on the project launcher."""
import pystray
import pytest

from claudetray import util
from claudetray.config import Config
from claudetray.data.db import Database
from claudetray.tray import TrayApp


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("claudetray.config.CLAUDETRAY_DIR", tmp_path)
    config = Config(tmp_path / "settings.json")
    db = Database(tmp_path / "test.db")
    tray = TrayApp(config, db)
    yield tray, db
    db.close()


def test_project_item_launches_with_full_path(app, tmp_path, monkeypatch):
    """pystray calls action(icon, item) -- the captured directory must survive.

    Regression: a `lambda _, d=directory` signature let pystray's second
    positional (the MenuItem) overwrite `d`, so the launcher received the
    MenuItem, whose str() is just the display text ("VAROEtsy"). The relative
    path then failed to resolve from the tray's cwd.
    """
    tray, db = app
    project = tmp_path / "VAROEtsy"
    project.mkdir()
    db.upsert_project(str(project))

    launched = []
    monkeypatch.setattr("claudetray.tray.open_claude", launched.append)

    (item,) = tray._project_menu_items()
    assert item.text == "VAROEtsy"

    # Mirror pystray._base.MenuItem.__call__: self._action(icon, self)
    item(object())

    assert launched == [str(project)]


def test_open_claude_uses_cwd_not_cd(tmp_path, monkeypatch):
    """Paths with spaces must not need quoting -- cwd carries the directory."""
    calls = []
    monkeypatch.setattr(util.subprocess, "Popen", lambda *a, **kw: calls.append((a, kw)))
    directory = tmp_path / "My Projects"
    directory.mkdir()

    assert util.open_claude(str(directory)) is True
    (args, kwargs) = calls[0]
    assert kwargs["cwd"] == str(directory)
    assert not any("cd /d" in part for part in args[0])


def test_open_claude_skips_missing_directory(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(util.subprocess, "Popen", lambda *a, **kw: calls.append((a, kw)))

    assert util.open_claude(str(tmp_path / "gone")) is False
    assert calls == []


def test_menu_builds_without_projects(app):
    tray, _ = app
    (item,) = tray._project_menu_items()
    assert item.text == "No recent projects"
    assert not item.enabled
    assert isinstance(item, pystray.MenuItem)
