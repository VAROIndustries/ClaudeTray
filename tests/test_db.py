from datetime import datetime, timedelta
from claudetray.data.models import UsageSnapshot, SessionInfo
from claudetray.data.db import Database


def test_add_and_get_snapshots(tmp_path):
    db = Database(tmp_path / "test.db")
    now = datetime.now()
    snap = UsageSnapshot(
        timestamp=now,
        five_hour_pct=41.0,
        seven_day_pct=37.0,
        context_pct=4.0,
    )
    db.add_snapshot(snap)
    results = db.get_snapshots(since=now - timedelta(minutes=1))
    assert len(results) == 1
    assert results[0].five_hour_pct == 41.0
    assert results[0].seven_day_pct == 37.0
    db.close()


def test_upsert_session(tmp_path):
    db = Database(tmp_path / "test.db")
    now = datetime.now()
    session = SessionInfo(
        session_id="abc-123",
        project_dir="C:\\Projects\\Test",
        model="Opus 4.6",
        start_time=now,
        last_seen=now,
        total_cost=0.50,
        tokens_in=1000,
        tokens_out=500,
    )
    db.upsert_session(session)
    sessions = db.get_sessions(limit=10)
    assert len(sessions) == 1
    assert sessions[0].session_id == "abc-123"
    assert sessions[0].total_cost == 0.50

    # Update same session
    session.total_cost = 1.25
    session.last_seen = now + timedelta(minutes=5)
    db.upsert_session(session)
    sessions = db.get_sessions(limit=10)
    assert len(sessions) == 1
    assert sessions[0].total_cost == 1.25
    db.close()


def test_upsert_project(tmp_path):
    db = Database(tmp_path / "test.db")
    db.upsert_project("C:\\Projects\\Test")
    projects = db.get_recent_projects(limit=5)
    assert len(projects) == 1
    assert projects[0]["directory"] == "C:\\Projects\\Test"
    assert projects[0]["session_count"] == 1
    db.close()


def test_prune_old_snapshots(tmp_path):
    db = Database(tmp_path / "test.db")
    old = datetime.now() - timedelta(days=60)
    recent = datetime.now()
    db.add_snapshot(UsageSnapshot(timestamp=old, five_hour_pct=10, seven_day_pct=10, context_pct=5))
    db.add_snapshot(UsageSnapshot(timestamp=recent, five_hour_pct=40, seven_day_pct=35, context_pct=8))
    db.prune(days=30)
    results = db.get_snapshots(since=old - timedelta(days=1))
    assert len(results) == 1
    assert results[0].five_hour_pct == 40
    db.close()


def test_get_recent_projects_ordered(tmp_path):
    db = Database(tmp_path / "test.db")
    db.upsert_project("C:\\Projects\\Old")
    db.upsert_project("C:\\Projects\\New")
    projects = db.get_recent_projects(limit=5)
    assert projects[0]["directory"] == "C:\\Projects\\New"
    db.close()
