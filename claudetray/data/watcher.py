import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Callable, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .models import AppState, UsageSnapshot, SessionInfo


class StatuslineParser:
    @staticmethod
    def parse(data: dict) -> tuple:
        """Parse statusline JSON into (AppState, UsageSnapshot, SessionInfo | None)."""
        state = AppState()

        rate_limits = data.get("rate_limits", {})
        five_hour = rate_limits.get("five_hour", {})
        seven_day = rate_limits.get("seven_day", {})
        state.five_hour_pct = five_hour.get("used_percentage", 0)
        state.seven_day_pct = seven_day.get("used_percentage", 0)
        state.five_hour_resets_at = five_hour.get("resets_at")
        state.seven_day_resets_at = seven_day.get("resets_at")

        ctx = data.get("context_window", {})
        state.context_pct = ctx.get("used_percentage", 0)

        state.session_id = data.get("session_id")
        workspace = data.get("workspace", {})
        state.project_dir = workspace.get("current_dir") or data.get("cwd")
        model_data = data.get("model", {})
        state.model = model_data.get("display_name")
        cost_data = data.get("cost", {})
        state.total_cost = cost_data.get("total_cost_usd", 0)
        state.total_duration_ms = cost_data.get("total_duration_ms", 0)
        state.session_active = True
        state.last_update = datetime.now()

        now = datetime.now()
        snapshot = UsageSnapshot(
            timestamp=now,
            five_hour_pct=state.five_hour_pct,
            seven_day_pct=state.seven_day_pct,
            context_pct=state.context_pct,
            five_hour_resets_at=state.five_hour_resets_at,
            seven_day_resets_at=state.seven_day_resets_at,
        )

        session = None
        if state.session_id:
            tokens = ctx.get("current_usage", {})
            session = SessionInfo(
                session_id=state.session_id,
                project_dir=state.project_dir or "",
                model=state.model or "",
                start_time=now,
                last_seen=now,
                total_cost=state.total_cost,
                tokens_in=tokens.get("input_tokens", 0) + tokens.get("cache_read_input_tokens", 0),
                tokens_out=tokens.get("output_tokens", 0),
            )

        return state, snapshot, session


class _FileHandler(FileSystemEventHandler):
    def __init__(self, callback, filename):
        self.callback = callback
        self.filename = filename

    def on_modified(self, event):
        if not event.is_directory and Path(event.src_path).name == self.filename:
            self.callback()


class StatuslineWatcher:
    def __init__(self, file_path: Path, on_update: Callable[[AppState], None], db=None):
        self.file_path = file_path
        self.on_update = on_update
        self.db = db
        self.state = AppState()
        self._observer = None
        self._last_modified = 0.0
        self._inactive_timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()

    def start(self):
        self._read_file()
        if not self.file_path.parent.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
        handler = _FileHandler(self._on_file_changed, self.file_path.name)
        self._observer = Observer()
        self._observer.schedule(handler, str(self.file_path.parent), recursive=False)
        self._observer.daemon = True
        self._observer.start()

    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2)
        if self._inactive_timer:
            self._inactive_timer.cancel()

    def _on_file_changed(self):
        self._read_file()

    def _read_file(self):
        try:
            if not self.file_path.exists():
                return
            mod_time = self.file_path.stat().st_mtime
            if mod_time == self._last_modified:
                return
            self._last_modified = mod_time

            with open(self.file_path, "r") as f:
                data = json.load(f)

            state, snapshot, session = StatuslineParser.parse(data)

            with self._lock:
                self.state = state

            if self.db and snapshot:
                self.db.add_snapshot(snapshot)
            if self.db and session:
                self.db.upsert_session(session)
                self.db.upsert_project(session.project_dir)

            self.on_update(state)
            self._reset_inactive_timer()

        except (json.JSONDecodeError, OSError):
            pass

    def _reset_inactive_timer(self):
        if self._inactive_timer:
            self._inactive_timer.cancel()
        self._inactive_timer = threading.Timer(60.0, self._mark_inactive)
        self._inactive_timer.daemon = True
        self._inactive_timer.start()

    def _mark_inactive(self):
        with self._lock:
            self.state.session_active = False
        self.on_update(self.state)
