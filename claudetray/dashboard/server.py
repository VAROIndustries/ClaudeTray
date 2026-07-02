import os
import sys
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request
from ..config import Config
from ..data.db import Database
from .. import startup

IDLE_TIMEOUT = 300  # 5 minutes in seconds

ALLOWED_SETTINGS = {
    "run_on_startup",
    "refresh_interval_active",
    "refresh_interval_idle",
    "api_key",
    "dashboard_port",
    "theme",
    "data_retention_days",
}


def _resource_dir():
    """Return the dashboard resource directory, handling PyInstaller frozen builds."""
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "claudetray", "dashboard")
    return os.path.dirname(os.path.abspath(__file__))


def create_app(config: Config, db: Database, tray=None) -> Flask:
    base = _resource_dir()
    app = Flask(
        __name__,
        template_folder=os.path.join(base, "templates"),
        static_folder=os.path.join(base, "static"),
    )
    app._last_request_time = time.monotonic()

    @app.after_request
    def _track_activity(response):
        app._last_request_time = time.monotonic()
        return response

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
                if key == "run_on_startup":
                    startup.set_run_on_startup(bool(value))
        return jsonify({"status": "ok"})

    return app


def _get_state(tray) -> dict:
    if tray and hasattr(tray, "state"):
        s = tray.state
        api_rl = None
        if hasattr(tray, "_api_rate_limits") and tray._api_rate_limits:
            rl = tray._api_rate_limits
            api_rl = {
                "requests_used_pct": rl.requests_used_pct,
                "tokens_used_pct": rl.tokens_used_pct,
                "requests_limit": rl.requests_limit,
                "requests_remaining": rl.requests_remaining,
                "tokens_limit": rl.tokens_limit,
                "tokens_remaining": rl.tokens_remaining,
                "timestamp": rl.timestamp.isoformat() if rl.timestamp else None,
            }
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
            "api_rate_limits": api_rl,
        }
    return {
        "five_hour_pct": 0, "seven_day_pct": 0, "context_pct": 0,
        "session_id": None, "project_dir": None, "model": None,
        "total_cost": 0, "total_duration_ms": 0, "session_active": False,
        "last_update": None, "five_hour_resets_at": None, "seven_day_resets_at": None,
        "api_rate_limits": None,
    }
