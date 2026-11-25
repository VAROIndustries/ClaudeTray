"""Tests for the Claude Queue client: parsing, config, wording."""
import json

from claudetray.config import Config
from claudetray.queue_client import QueueSession, format_age, parse_sessions, resolve_queue_config

NOW = 10_000_000


def _s(id, kind, waited_min, **kw):
    return {"id": id, "kind": kind, "project": kw.get("project", id), "host": "SLAB",
            "remote": kw.get("remote", False), "cwd": kw.get("cwd", ""), "link": kw.get("link", ""),
            "summary": "", "waitingSince": NOW - waited_min * 60000, "updated": NOW}


def test_parse_orders_by_urgency_then_longest_wait():
    data = {"now": NOW, "waiting": [_s("a", "done", 50), _s("b", "permission", 1),
                                    _s("c", "question", 5), _s("d", "question", 30)]}
    assert [r.id for r in parse_sessions(data)] == ["b", "d", "c", "a"]


def test_parse_handles_missing_fields():
    (r,) = parse_sessions({"now": NOW, "waiting": [{"id": "x", "updated": NOW - 120000}]})
    assert r.project == "(no folder)" and r.waited == "2m" and r.label == ""


def test_format_age():
    assert format_age(10_000) == "just now"
    assert format_age(5 * 60000) == "5m"
    assert format_age(125 * 60000) == "2h 5m"
    assert format_age(3 * 24 * 3600000) == "3d"


def test_old_after_thirty_minutes():
    (r,) = parse_sessions({"now": NOW, "waiting": [_s("a", "done", 31)]})
    assert r.is_old


def test_resume_command_quotes_path():
    r = QueueSession("abc", "p", "done", "SLAB", False, r"C:\My Projects\x", "", "", 0)
    assert r.resume_command == 'cd /d "C:\\My Projects\\x" && claude --resume abc'


def test_only_https_links_open():
    assert not QueueSession("a", "p", "done", "h", True, "", "javascript:alert(1)", "", 0).can_open_link
    assert QueueSession("a", "p", "done", "h", True, "", "https://claude.ai/x", "", 0).can_open_link


def test_config_prefers_settings(tmp_path):
    cfg = Config(tmp_path / "settings.json")
    cfg.set("queue_url", "https://a.example/")
    cfg.set("queue_view_key", "k1")
    assert resolve_queue_config(cfg, tmp_path / "none.json") == ("https://a.example", "k1")


def test_config_falls_back_to_claude_queue_file(tmp_path):
    f = tmp_path / ".claude-queue.json"
    f.write_text(json.dumps({"url": "https://b.example", "key": "ingest", "viewKey": "v"}), encoding="utf-8-sig")
    assert resolve_queue_config(Config(tmp_path / "settings.json"), f) == ("https://b.example", "v")


def test_config_off_without_view_key(tmp_path):
    f = tmp_path / ".claude-queue.json"
    f.write_text(json.dumps({"url": "https://b.example", "key": "ingest"}))
    assert resolve_queue_config(Config(tmp_path / "settings.json"), f) is None
