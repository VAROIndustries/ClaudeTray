import json
from datetime import datetime, timedelta
from claudetray.dashboard.server import create_app
from claudetray.config import Config
from claudetray.data.db import Database
from claudetray.data.models import UsageSnapshot, SessionInfo


def _setup(tmp_path):
    config = Config(path=tmp_path / "settings.json")
    db = Database(tmp_path / "test.db")
    app = create_app(config, db)
    app.config["TESTING"] = True
    return app, config, db


def test_index_returns_200(tmp_path):
    app, _, _ = _setup(tmp_path)
    with app.test_client() as c:
        r = c.get("/")
        assert r.status_code == 200
        assert b"Claude" in r.data


def test_sessions_page(tmp_path):
    app, _, db = _setup(tmp_path)
    now = datetime.now()
    db.upsert_session(SessionInfo("s1", "C:\\Test", "Opus", now, now, 0.5, 100, 50))
    with app.test_client() as c:
        r = c.get("/sessions")
        assert r.status_code == 200


def test_projects_page(tmp_path):
    app, _, db = _setup(tmp_path)
    db.upsert_project("C:\\Projects\\MyApp")
    with app.test_client() as c:
        r = c.get("/projects")
        assert r.status_code == 200


def test_settings_page(tmp_path):
    app, _, _ = _setup(tmp_path)
    with app.test_client() as c:
        r = c.get("/settings")
        assert r.status_code == 200


def test_api_state(tmp_path):
    app, _, _ = _setup(tmp_path)
    with app.test_client() as c:
        r = c.get("/api/state")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "five_hour_pct" in data


def test_api_snapshots(tmp_path):
    app, _, db = _setup(tmp_path)
    now = datetime.now()
    db.add_snapshot(UsageSnapshot(timestamp=now, five_hour_pct=41, seven_day_pct=37, context_pct=4))
    with app.test_client() as c:
        r = c.get("/api/snapshots?hours=24")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert len(data) == 1


def test_api_settings_get(tmp_path):
    app, _, _ = _setup(tmp_path)
    with app.test_client() as c:
        r = c.get("/api/settings")
        data = json.loads(r.data)
        assert data["theme"] == "dark"


def test_api_settings_post(tmp_path):
    app, config, _ = _setup(tmp_path)
    with app.test_client() as c:
        r = c.post("/api/settings", json={"theme": "light"})
        assert r.status_code == 200
    assert config.get("theme") == "light"
