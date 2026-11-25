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


from claudetray.queue_client import QueueSession


def _row(id, kind, project="FairKeep", remote=False):
    return QueueSession(id, project, kind, "SLAB", remote, "C:\\Projects\\" + project, "", "Can I deploy?", 120000)


class _FakeClient:
    url = "https://queue.example"


def test_queue_section_hidden_when_not_configured(app):
    tray, _ = app
    assert tray._queue_menu_items() == []


def test_queue_section_lists_waiting_sessions(app):
    tray, _ = app
    tray.queue_client = _FakeClient()
    tray.on_queue_update([_row("a", "permission"), _row("b", "done", "Rideline")], None)
    texts = [i.text for i in tray._queue_menu_items() if i is not pystray.Menu.SEPARATOR]
    assert texts[0] == "Waiting on you (2)"
    assert texts[1].startswith("[!!] FairKeep  -  needs permission  -  2m")
    assert "Open Claude Queue Page" in texts
    assert "Waiting on you: 2 (permission!)" in tray._icon.title


def test_queue_notifies_only_for_new_non_done_sessions(app, monkeypatch):
    tray, _ = app
    tray.queue_client = _FakeClient()
    sent = []
    monkeypatch.setattr(tray, "_notify", lambda msg, title: sent.append(title))
    tray.on_queue_update([_row("a", "question")], None)          # first poll: no alerts
    tray.on_queue_update([_row("a", "question"), _row("b", "done"), _row("c", "permission", "Rideline")], None)
    assert sent == ["Rideline: needs permission"]


def test_queue_error_keeps_last_list(app):
    tray, _ = app
    tray.queue_client = _FakeClient()
    tray.on_queue_update([_row("a", "question")], None)
    tray.on_queue_update(None, "timed out")
    texts = [i.text for i in tray._queue_menu_items() if i is not pystray.Menu.SEPARATOR]
    assert texts[0] == "Waiting on you (1)" and texts[1].startswith("Can't reach Claude Queue")


def test_local_session_offers_resume_command(app):
    tray, _ = app
    first = tray._session_actions(_row("a", "done"))[0]
    assert first.text == "Copy Resume Command"
    assert tray._session_actions(_row("b", "done", remote=True))[0].text == "Open Claude Queue Page"


def test_browser_menu_copies_paste_line(app, monkeypatch):
    from claudetray.browsers import ClaudeBrowser
    tray, _ = app
    b = ClaudeBrowser("Personal", "Chrome", "Me", "Default", "", "id-1")
    monkeypatch.setattr(tray, "browsers", lambda force=False: [b])
    copied = []
    monkeypatch.setattr("claudetray.tray.copy_to_clipboard", lambda t: copied.append(t) or True)
    monkeypatch.setattr(tray, "_notify", lambda *a: None)
    item = [i for i in tray._browser_menu_items() if getattr(i, "text", "").startswith("Personal")][0]
    item(object())
    assert copied == [b.paste_line]
