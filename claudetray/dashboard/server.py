from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request
from ..config import Config
from ..data.db import Database


ALLOWED_SETTINGS = {
    "run_on_startup",
    "refresh_interval_active",
    "refresh_interval_idle",
    "api_key",
    "dashboard_port",
    "theme",
    "data_retention_days",
}


def create_app(config: Config, db: Database, tray=None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    @app.route("/")
    def index():
        state = _get_state(tray)
        raw_snapshots = db.get_snapshots(since=datetime.now() - timedelta(hours=24))
        snapshots = [
            {
                "timestamp": s.timestamp.isoformat(),
                "five_hour_pct": s.five_hour_pct,
                "seven_day_pct": s.seven_day_pct,
                "context_pct": s.context_pct,
            }
            for s in raw_snapshots
        ]
        return render_template("index.html", state=state, snapshots=snapshots, config=config)

    @app.route("/sessions")
    def sessions():
        session_list = db.get_sessions(limit=50)
        return render_template("sessions.html", sessions=session_list)

    @app.route("/projects")
    def projects():
        project_list = db.get_recent_projects(limit=20)
        return render_template("projects.html", projects=project_list)

    @app.route("/settings")
    def settings():
        return render_template("settings.html", config=config)

    @app.route("/api/state")
    def api_state():
        state = _get_state(tray)
        return jsonify(state)

    @app.route("/api/snapshots")
    def api_snapshots():
        hours = request.args.get("hours", 24, type=int)
        since = datetime.now() - timedelta(hours=hours)
        snaps = db.get_snapshots(since=since)
        return jsonify([
            {
                "timestamp": s.timestamp.isoformat(),
                "five_hour_pct": s.five_hour_pct,
                "seven_day_pct": s.seven_day_pct,
                "context_pct": s.context_pct,
            }
            for s in snaps
        ])

    @app.route("/api/settings", methods=["GET"])
    def api_settings_get():
        return jsonify(config._data)

    @app.route("/api/settings", methods=["POST"])
    def api_settings_post():
        updates = request.get_json() or {}
        for key, value in updates.items():
            if key in ALLOWED_SETTINGS:
                config.set(key, value)
        return jsonify({"status": "ok"})

    return app


def _get_state(tray) -> dict:
    if tray and hasattr(tray, "state"):
        s = tray.state
        return {
            "five_hour_pct": s.five_hour_pct,
            "seven_day_pct": s.seven_day_pct,
            "context_pct": s.context_pct,
            "session_id": s.session_id,
            "project_dir": s.project_dir,
            "model": s.model,
            "total_cost": s.total_cost,
            "total_duration_ms": s.total_duration_ms,
            "session_active": s.session_active,
            "last_update": s.last_update.isoformat() if s.last_update else None,
            "five_hour_resets_at": s.five_hour_resets_at,
            "seven_day_resets_at": s.seven_day_resets_at,
        }
    return {
        "five_hour_pct": 0, "seven_day_pct": 0, "context_pct": 0,
        "session_id": None, "project_dir": None, "model": None,
        "total_cost": 0, "total_duration_ms": 0, "session_active": False,
        "last_update": None, "five_hour_resets_at": None, "seven_day_resets_at": None,
    }
