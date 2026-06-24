# ClaudeTray Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows system tray app that displays Claude Code usage like a battery meter, with a quick popup and full web dashboard.

**Architecture:** pystray for the tray icon with Pillow-rendered dynamic text, tkinter for the quick popup, Flask for the web dashboard. Data comes from watching Claude Code's statusline debug JSON. SQLite stores usage history.

**Tech Stack:** Python 3.12, pystray, Pillow, watchdog, Flask, Chart.js, SQLite, PyInstaller

## Global Constraints

- Python 3.12 at `C:\Users\gvaro\AppData\Local\Programs\Python\Python312\python.exe`
- Windows 11 target platform
- All paths use `pathlib.Path` for cross-compatibility
- Statusline JSON default location: `%TEMP%\statusline_debug.json` (written by Claude Code's git-bash statusline hook as `/tmp/statusline_debug.json`)
- User data directory: `~/.claudetray/`
- Dashboard port: 5199
- Test framework: pytest
- No external frontend frameworks — vanilla HTML/CSS/JS + Chart.js CDN

---

### Task 1: Project Setup + Config Module

**Files:**
- Create: `requirements.txt`
- Create: `claudetray/__init__.py`
- Create: `claudetray/__main__.py`
- Create: `claudetray/config.py`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces: `Config` class with `load()`, `save()`, `get(key)`, `set(key, value)`, `statusline_path` property. `CLAUDETRAY_DIR` and `CONFIG_PATH` constants. `DEFAULTS` dict.

- [ ] **Step 1: Create project structure and requirements.txt**

```
requirements.txt
```

```text
pystray>=0.19
Pillow>=10.0
watchdog>=3.0
Flask>=3.0
requests>=2.31
pytest>=8.0
```

```
claudetray/__init__.py
```

```python
"""ClaudeTray - Windows system tray monitor for Claude Code usage."""
__version__ = "0.1.0"
```

```
claudetray/__main__.py
```

```python
from claudetray.app import main

if __name__ == "__main__":
    main()
```

```
tests/__init__.py
```

(empty file)

- [ ] **Step 2: Write failing test for Config**

```
tests/test_config.py
```

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd C:\Projects\ClaudeTray && C:\Users\gvaro\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_config.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'claudetray.config'`

- [ ] **Step 4: Write Config implementation**

```
claudetray/config.py
```

```python
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
        self._load()

    def _load(self):
        if self.path.exists():
            with open(self.path, "r") as f:
                saved = json.load(f)
            self._data.update(saved)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key, default=None):
        val = self._data.get(key)
        if val is None and default is not None:
            return default
        return val

    def set(self, key, value):
        self._data[key] = value
        self.save()

    @property
    def statusline_path(self) -> Path:
        custom = self._data.get("statusline_path")
        if custom:
            return Path(custom)
        return _detect_statusline_path()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd C:\Projects\ClaudeTray && C:\Users\gvaro\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_config.py -v`

Expected: All 6 tests PASS

- [ ] **Step 6: Commit**

```bash
git add requirements.txt claudetray/ tests/
git commit -m "feat: project scaffolding and config module"
```

---

### Task 2: Data Models + Database

**Files:**
- Create: `claudetray/data/__init__.py`
- Create: `claudetray/data/models.py`
- Create: `claudetray/data/db.py`
- Create: `tests/test_db.py`

**Interfaces:**
- Produces: `AppState`, `UsageSnapshot`, `SessionInfo` dataclasses. `Database` class with `add_snapshot()`, `get_snapshots(since)`, `upsert_session()`, `upsert_project()`, `get_recent_projects(limit)`, `get_sessions(limit)`, `prune(days)`, `close()`.

- [ ] **Step 1: Write failing tests for Database**

```
tests/test_db.py
```

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\Projects\ClaudeTray && C:\Users\gvaro\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_db.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'claudetray.data'`

- [ ] **Step 3: Write models and database implementation**

```
claudetray/data/__init__.py
```

(empty file)

```
claudetray/data/models.py
```

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class UsageSnapshot:
    timestamp: datetime
    five_hour_pct: float
    seven_day_pct: float
    context_pct: float
    five_hour_resets_at: Optional[int] = None
    seven_day_resets_at: Optional[int] = None


@dataclass
class SessionInfo:
    session_id: str
    project_dir: str
    model: str
    start_time: datetime
    last_seen: datetime
    total_cost: float
    tokens_in: int
    tokens_out: int


@dataclass
class AppState:
    five_hour_pct: float = 0.0
    seven_day_pct: float = 0.0
    context_pct: float = 0.0
    five_hour_resets_at: Optional[int] = None
    seven_day_resets_at: Optional[int] = None
    session_id: Optional[str] = None
    project_dir: Optional[str] = None
    model: Optional[str] = None
    total_cost: float = 0.0
    total_duration_ms: int = 0
    session_active: bool = False
    last_update: Optional[datetime] = None
```

```
claudetray/data/db.py
```

```python
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import List
from .models import UsageSnapshot, SessionInfo


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS usage_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                five_hour_pct REAL NOT NULL,
                seven_day_pct REAL NOT NULL,
                context_pct REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                project_dir TEXT NOT NULL,
                model TEXT,
                start_time TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                total_cost REAL DEFAULT 0,
                tokens_in INTEGER DEFAULT 0,
                tokens_out INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS projects (
                directory TEXT PRIMARY KEY,
                last_used TEXT NOT NULL,
                session_count INTEGER DEFAULT 0
            );
        """)
        self.conn.commit()

    def add_snapshot(self, snap: UsageSnapshot):
        self.conn.execute(
            "INSERT INTO usage_snapshots (timestamp, five_hour_pct, seven_day_pct, context_pct) VALUES (?, ?, ?, ?)",
            (snap.timestamp.isoformat(), snap.five_hour_pct, snap.seven_day_pct, snap.context_pct),
        )
        self.conn.commit()

    def get_snapshots(self, since: datetime) -> List[UsageSnapshot]:
        rows = self.conn.execute(
            "SELECT * FROM usage_snapshots WHERE timestamp >= ? ORDER BY timestamp",
            (since.isoformat(),),
        ).fetchall()
        return [
            UsageSnapshot(
                timestamp=datetime.fromisoformat(r["timestamp"]),
                five_hour_pct=r["five_hour_pct"],
                seven_day_pct=r["seven_day_pct"],
                context_pct=r["context_pct"],
            )
            for r in rows
        ]

    def upsert_session(self, session: SessionInfo):
        self.conn.execute(
            """INSERT INTO sessions (session_id, project_dir, model, start_time, last_seen, total_cost, tokens_in, tokens_out)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                last_seen=excluded.last_seen,
                total_cost=excluded.total_cost,
                tokens_in=excluded.tokens_in,
                tokens_out=excluded.tokens_out""",
            (
                session.session_id,
                session.project_dir,
                session.model,
                session.start_time.isoformat(),
                session.last_seen.isoformat(),
                session.total_cost,
                session.tokens_in,
                session.tokens_out,
            ),
        )
        self.conn.commit()

    def upsert_project(self, directory: str):
        now = datetime.now().isoformat()
        self.conn.execute(
            """INSERT INTO projects (directory, last_used, session_count)
            VALUES (?, ?, 1)
            ON CONFLICT(directory) DO UPDATE SET
                last_used=?,
                session_count=session_count + 1""",
            (directory, now, now),
        )
        self.conn.commit()

    def get_recent_projects(self, limit: int = 10) -> list:
        rows = self.conn.execute(
            "SELECT * FROM projects ORDER BY last_used DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_sessions(self, limit: int = 50) -> List[SessionInfo]:
        rows = self.conn.execute(
            "SELECT * FROM sessions ORDER BY last_seen DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            SessionInfo(
                session_id=r["session_id"],
                project_dir=r["project_dir"],
                model=r["model"] or "",
                start_time=datetime.fromisoformat(r["start_time"]),
                last_seen=datetime.fromisoformat(r["last_seen"]),
                total_cost=r["total_cost"],
                tokens_in=r["tokens_in"],
                tokens_out=r["tokens_out"],
            )
            for r in rows
        ]

    def prune(self, days: int):
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        self.conn.execute("DELETE FROM usage_snapshots WHERE timestamp < ?", (cutoff,))
        self.conn.commit()

    def close(self):
        self.conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:\Projects\ClaudeTray && C:\Users\gvaro\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_db.py -v`

Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add claudetray/data/ tests/test_db.py
git commit -m "feat: data models and SQLite database layer"
```

---

### Task 3: Statusline Parser + File Watcher

**Files:**
- Create: `claudetray/data/watcher.py`
- Create: `tests/test_watcher.py`

**Interfaces:**
- Consumes: `AppState`, `UsageSnapshot`, `SessionInfo` from `claudetray.data.models`. `Database` from `claudetray.data.db`.
- Produces: `StatuslineParser.parse(data: dict) -> tuple[AppState, UsageSnapshot, SessionInfo | None]`. `StatuslineWatcher` class with `start()`, `stop()`, `state` property.

- [ ] **Step 1: Write failing tests for parser and watcher**

```
tests/test_watcher.py
```

```python
import json
import time
from pathlib import Path
from claudetray.data.watcher import StatuslineParser, StatuslineWatcher
from claudetray.data.models import AppState

SAMPLE_JSON = {
    "session_id": "317f713a-2b33-4b86-82d5-58392a51fef0",
    "cwd": "C:\\Projects\\ClaudeTray",
    "model": {"id": "claude-opus-4-6[1m]", "display_name": "Opus 4.6 (1M context)"},
    "workspace": {"current_dir": "C:\\Projects\\ClaudeTray"},
    "cost": {"total_cost_usd": 0.365, "total_duration_ms": 265896},
    "context_window": {
        "used_percentage": 4,
        "current_usage": {
            "input_tokens": 1,
            "output_tokens": 98,
            "cache_creation_input_tokens": 813,
            "cache_read_input_tokens": 34209,
        },
    },
    "rate_limits": {
        "five_hour": {"used_percentage": 41, "resets_at": 1782336600},
        "seven_day": {"used_percentage": 37, "resets_at": 1782367200},
    },
}


def test_parser_extracts_rate_limits():
    state, snapshot, session = StatuslineParser.parse(SAMPLE_JSON)
    assert state.five_hour_pct == 41
    assert state.seven_day_pct == 37
    assert state.context_pct == 4


def test_parser_extracts_session_info():
    state, snapshot, session = StatuslineParser.parse(SAMPLE_JSON)
    assert state.session_id == "317f713a-2b33-4b86-82d5-58392a51fef0"
    assert state.model == "Opus 4.6 (1M context)"
    assert state.project_dir == "C:\\Projects\\ClaudeTray"
    assert state.total_cost == 0.365


def test_parser_creates_snapshot():
    state, snapshot, session = StatuslineParser.parse(SAMPLE_JSON)
    assert snapshot.five_hour_pct == 41
    assert snapshot.seven_day_pct == 37
    assert snapshot.context_pct == 4


def test_parser_creates_session():
    state, snapshot, session = StatuslineParser.parse(SAMPLE_JSON)
    assert session is not None
    assert session.session_id == "317f713a-2b33-4b86-82d5-58392a51fef0"
    assert session.tokens_in == 34210  # input_tokens + cache_read
    assert session.tokens_out == 98


def test_parser_handles_missing_fields():
    minimal = {"rate_limits": {}, "context_window": {}}
    state, snapshot, session = StatuslineParser.parse(minimal)
    assert state.five_hour_pct == 0
    assert state.seven_day_pct == 0
    assert session is None


def test_parser_extracts_reset_times():
    state, snapshot, session = StatuslineParser.parse(SAMPLE_JSON)
    assert state.five_hour_resets_at == 1782336600
    assert state.seven_day_resets_at == 1782367200


def test_parser_extracts_duration():
    state, snapshot, session = StatuslineParser.parse(SAMPLE_JSON)
    assert state.total_duration_ms == 265896


def test_watcher_reads_file(tmp_path):
    json_file = tmp_path / "statusline_debug.json"
    json_file.write_text(json.dumps(SAMPLE_JSON))

    updates = []
    watcher = StatuslineWatcher(
        file_path=json_file,
        on_update=lambda s: updates.append(s),
    )
    watcher._read_file()
    assert len(updates) == 1
    assert updates[0].five_hour_pct == 41


def test_watcher_ignores_missing_file(tmp_path):
    json_file = tmp_path / "nonexistent.json"
    updates = []
    watcher = StatuslineWatcher(
        file_path=json_file,
        on_update=lambda s: updates.append(s),
    )
    watcher._read_file()
    assert len(updates) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\Projects\ClaudeTray && C:\Users\gvaro\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_watcher.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'claudetray.data.watcher'`

- [ ] **Step 3: Write watcher implementation**

```
claudetray/data/watcher.py
```

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:\Projects\ClaudeTray && C:\Users\gvaro\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_watcher.py -v`

Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add claudetray/data/watcher.py tests/test_watcher.py
git commit -m "feat: statusline JSON parser and file watcher"
```

---

### Task 4: Icon Renderer

**Files:**
- Create: `claudetray/icon_renderer.py`
- Create: `tests/test_icon_renderer.py`

**Interfaces:**
- Produces: `render_icon(five_pct: float, seven_pct: float, size: int = 64) -> Image.Image`

- [ ] **Step 1: Write failing tests for icon renderer**

```
tests/test_icon_renderer.py
```

```python
from PIL import Image
from claudetray.icon_renderer import render_icon


def test_render_icon_returns_image():
    img = render_icon(41, 37)
    assert isinstance(img, Image.Image)
    assert img.size == (64, 64)
    assert img.mode == "RGBA"


def test_render_icon_custom_size():
    img = render_icon(50, 60, size=128)
    assert img.size == (128, 128)


def test_render_icon_zero_values():
    img = render_icon(0, 0)
    assert img.size == (64, 64)


def test_render_icon_max_values():
    img = render_icon(100, 100)
    assert img.size == (64, 64)


def test_render_icon_not_blank():
    img = render_icon(41, 37)
    pixels = list(img.getdata())
    bg_color = (26, 26, 46, 255)
    non_bg = [p for p in pixels if p != bg_color]
    assert len(non_bg) > 0, "Icon should contain rendered text, not just background"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\Projects\ClaudeTray && C:\Users\gvaro\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_icon_renderer.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'claudetray.icon_renderer'`

- [ ] **Step 3: Write icon renderer implementation**

```
claudetray/icon_renderer.py
```

```python
from PIL import Image, ImageDraw, ImageFont


def _get_color(five_pct: float, seven_pct: float) -> tuple:
    max_pct = max(five_pct, seven_pct)
    if max_pct >= 80:
        return (239, 68, 68)  # red
    elif max_pct >= 60:
        return (234, 179, 8)  # yellow
    return (34, 197, 94)  # green


def _load_font(size: int):
    font_size = max(size // 3, 8)
    for name in ("arial.ttf", "Arial.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, font_size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_icon(five_pct: float, seven_pct: float, size: int = 64) -> Image.Image:
    bg = (26, 26, 46, 255)
    img = Image.new("RGBA", (size, size), bg)
    draw = ImageDraw.Draw(img)

    color = _get_color(five_pct, seven_pct)
    font = _load_font(size)

    five_text = str(int(five_pct))
    seven_text = str(int(seven_pct))

    # Top number (5h usage)
    bbox1 = draw.textbbox((0, 0), five_text, font=font)
    w1 = bbox1[2] - bbox1[0]
    h1 = bbox1[3] - bbox1[1]
    x1 = (size - w1) // 2
    y1 = size // 8
    draw.text((x1, y1), five_text, fill=color, font=font)

    # Divider line
    div_y = size // 2 - 1
    draw.line([(size // 6, div_y), (size - size // 6, div_y)], fill=(100, 100, 140), width=1)

    # Bottom number (7d usage)
    bbox2 = draw.textbbox((0, 0), seven_text, font=font)
    w2 = bbox2[2] - bbox2[0]
    x2 = (size - w2) // 2
    y2 = size // 2 + size // 16
    draw.text((x2, y2), seven_text, fill=color, font=font)

    return img
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:\Projects\ClaudeTray && C:\Users\gvaro\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_icon_renderer.py -v`

Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add claudetray/icon_renderer.py tests/test_icon_renderer.py
git commit -m "feat: dynamic tray icon renderer with usage percentages"
```

---

### Task 5: Tray Icon + App Entry Point

**Files:**
- Create: `claudetray/tray.py`
- Create: `claudetray/app.py`

**Interfaces:**
- Consumes: `Config` from `claudetray.config`. `Database` from `claudetray.data.db`. `StatuslineWatcher` from `claudetray.data.watcher`. `render_icon` from `claudetray.icon_renderer`. `AppState` from `claudetray.data.models`.
- Produces: `TrayApp` class with `run()`, `on_state_update(state)`, `stop()`. `main()` entry point function.

- [ ] **Step 1: Write tray.py**

```
claudetray/tray.py
```

```python
import os
import subprocess
import threading
import webbrowser
from pathlib import Path
from typing import Optional
import pystray
from .config import Config
from .data.db import Database
from .data.models import AppState
from .icon_renderer import render_icon


class TrayApp:
    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db
        self.state = AppState()
        self._popup = None
        self._dashboard_thread: Optional[threading.Thread] = None
        self._icon = pystray.Icon(
            "ClaudeTray",
            render_icon(0, 0),
            "Claude: No data yet",
            menu=self._build_menu(),
        )

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem("Open Quick View", self._show_popup, default=True),
            pystray.MenuItem("Open Dashboard", self._open_dashboard),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("New Claude Session", pystray.Menu(self._project_menu_items)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Run on Startup",
                self._toggle_startup,
                checked=lambda item: self.config.get("run_on_startup"),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit),
        )

    def _project_menu_items(self) -> list:
        projects = self.db.get_recent_projects(limit=8)
        if not projects:
            return [pystray.MenuItem("No recent projects", None, enabled=False)]
        items = []
        for p in projects:
            dirname = Path(p["directory"]).name
            directory = p["directory"]
            items.append(pystray.MenuItem(dirname, lambda _, d=directory: self._open_claude(d)))
        return items

    def _open_claude(self, directory: str):
        cmd = f'start cmd /k "cd /d {directory} && claude"'
        subprocess.Popen(cmd, shell=True)

    def on_state_update(self, state: AppState):
        self.state = state
        self._icon.icon = render_icon(state.five_hour_pct, state.seven_day_pct)
        if state.session_active:
            self._icon.title = f"Claude: 5h: {int(state.five_hour_pct)}% | 7d: {int(state.seven_day_pct)}%"
        else:
            ago = ""
            if state.last_update:
                from datetime import datetime
                delta = datetime.now() - state.last_update
                mins = int(delta.total_seconds() // 60)
                ago = f" | Last: {mins}m ago" if mins > 0 else ""
            self._icon.title = f"Claude: 5h: {int(state.five_hour_pct)}% | 7d: {int(state.seven_day_pct)}%{ago}"
        # Update popup if visible
        if self._popup:
            self._popup.update_state(state)

    def _show_popup(self, icon, item):
        if self._popup and self._popup.is_visible():
            self._popup.hide()
            return
        from .popup import PopupWindow
        if self._popup is None:
            self._popup = PopupWindow(self.state, self.db, self.config, self._open_dashboard)
        self._popup.show(self.state)

    def _open_dashboard(self, *args):
        if self._dashboard_thread is None or not self._dashboard_thread.is_alive():
            from .dashboard.server import create_app
            app = create_app(self.config, self.db, self)
            port = self.config.get("dashboard_port")
            self._dashboard_thread = threading.Thread(
                target=lambda: app.run(host="127.0.0.1", port=port, use_reloader=False),
                daemon=True,
            )
            self._dashboard_thread.start()
        port = self.config.get("dashboard_port")
        webbrowser.open(f"http://localhost:{port}")

    def _toggle_startup(self, icon, item):
        current = self.config.get("run_on_startup")
        self.config.set("run_on_startup", not current)
        self._manage_startup_shortcut(not current)

    def _manage_startup_shortcut(self, enable: bool):
        import sys
        startup_dir = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        shortcut_path = startup_dir / "ClaudeTray.lnk"
        if enable:
            try:
                import winreg
                # Use PowerShell to create shortcut since it's simpler than COM
                exe_path = sys.executable if getattr(sys, "frozen", False) else f'"{sys.executable}" -m claudetray'
                ps_cmd = (
                    f'$ws = New-Object -ComObject WScript.Shell; '
                    f'$s = $ws.CreateShortcut("{shortcut_path}"); '
                    f'$s.TargetPath = "{sys.executable}"; '
                )
                if not getattr(sys, "frozen", False):
                    ps_cmd += f'$s.Arguments = "-m claudetray"; '
                ps_cmd += '$s.Save()'
                subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
            except Exception:
                pass
        else:
            if shortcut_path.exists():
                shortcut_path.unlink()

    def _quit(self, icon, item):
        self._icon.stop()

    def run(self):
        self._icon.run()

    def stop(self):
        self._icon.stop()
```

- [ ] **Step 2: Write app.py entry point**

```
claudetray/app.py
```

```python
import sys
from pathlib import Path
from .config import Config, CLAUDETRAY_DIR, DB_PATH
from .data.db import Database
from .data.watcher import StatuslineWatcher
from .tray import TrayApp


def main():
    CLAUDETRAY_DIR.mkdir(parents=True, exist_ok=True)

    config = Config()
    db = Database(DB_PATH)

    # Prune old data on startup
    db.prune(config.get("data_retention_days"))

    tray = TrayApp(config, db)

    watcher = StatuslineWatcher(
        file_path=config.statusline_path,
        on_update=tray.on_state_update,
        db=db,
    )
    watcher.start()

    try:
        tray.run()
    finally:
        watcher.stop()
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Manually test the tray icon**

Run: `cd C:\Projects\ClaudeTray && C:\Users\gvaro\AppData\Local\Programs\Python\Python312\python.exe -m claudetray`

Expected: A system tray icon appears with "0/0" (or current usage if a Claude session is active). Right-click shows the context menu. Hovering shows the tooltip. Quit exits cleanly.

- [ ] **Step 4: Commit**

```bash
git add claudetray/tray.py claudetray/app.py
git commit -m "feat: system tray icon with menu and app entry point"
```

---

### Task 6: Quick Popup

**Files:**
- Create: `claudetray/popup.py`

**Interfaces:**
- Consumes: `AppState` from `claudetray.data.models`. `Database` from `claudetray.data.db`. `Config` from `claudetray.config`.
- Produces: `PopupWindow` class with `show(state)`, `hide()`, `is_visible()`, `update_state(state)`.

- [ ] **Step 1: Write popup.py**

```
claudetray/popup.py
```

```python
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from .data.models import AppState
from .data.db import Database
from .config import Config

BG = "#1a1a2e"
BG_SECTION = "#16213e"
FG = "#e0e0e0"
FG_DIM = "#888888"
GREEN = "#22c55e"
YELLOW = "#eab308"
RED = "#ef4444"
ACCENT = "#0f3460"


def _pct_color(pct: float) -> str:
    if pct >= 80:
        return RED
    elif pct >= 60:
        return YELLOW
    return GREEN


class PopupWindow:
    def __init__(self, state: AppState, db: Database, config: Config, open_dashboard: Callable):
        self._db = db
        self._config = config
        self._open_dashboard = open_dashboard
        self._root: Optional[tk.Tk] = None
        self._visible = False
        self._thread: Optional[threading.Thread] = None
        self._state = state
        # Widget references for updates
        self._bar_5h = None
        self._lbl_5h = None
        self._bar_7d = None
        self._lbl_7d = None
        self._bar_ctx = None
        self._lbl_ctx = None
        self._lbl_session = None
        self._lbl_model = None
        self._lbl_cost = None
        self._lbl_duration = None
        self._projects_frame = None

    def show(self, state: AppState):
        self._state = state
        if self._root is not None and self._visible:
            self._root.after(0, lambda: self._root.deiconify())
            self._root.after(10, lambda: self._refresh_ui())
            return
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=lambda: self._create_and_show(state), daemon=True)
            self._thread.start()

    def hide(self):
        if self._root and self._visible:
            self._root.after(0, self._root.withdraw)
            self._visible = False

    def is_visible(self) -> bool:
        return self._visible

    def update_state(self, state: AppState):
        self._state = state
        if self._root and self._visible:
            self._root.after(0, self._refresh_ui)

    def _create_and_show(self, state: AppState):
        self._root = tk.Tk()
        self._root.title("Claude Usage")
        self._root.configure(bg=BG)
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)

        w, h = 300, 420
        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        x = screen_w - w - 12
        y = screen_h - h - 60
        self._root.geometry(f"{w}x{h}+{x}+{y}")

        self._build_ui()
        self._refresh_ui()
        self._visible = True

        self._root.bind("<FocusOut>", lambda e: self.hide())
        self._root.after(100, lambda: self._root.focus_force())
        self._root.mainloop()

    def _build_ui(self):
        root = self._root

        # Title bar
        title_frame = tk.Frame(root, bg=ACCENT, height=30)
        title_frame.pack(fill="x")
        title_frame.pack_propagate(False)
        tk.Label(title_frame, text="Claude Usage", bg=ACCENT, fg=FG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=8)
        close_btn = tk.Label(title_frame, text="\u00d7", bg=ACCENT, fg=FG, font=("Segoe UI", 12), cursor="hand2")
        close_btn.pack(side="right", padx=8)
        close_btn.bind("<Button-1>", lambda e: self.hide())

        # Make title bar draggable
        title_frame.bind("<Button-1>", self._start_drag)
        title_frame.bind("<B1-Motion>", self._do_drag)

        # Usage bars section
        usage_frame = tk.Frame(root, bg=BG, pady=8, padx=12)
        usage_frame.pack(fill="x")

        self._bar_5h, self._lbl_5h = self._make_bar(usage_frame, "5-Hour")
        self._bar_7d, self._lbl_7d = self._make_bar(usage_frame, "7-Day")
        self._bar_ctx, self._lbl_ctx = self._make_bar(usage_frame, "Context")

        # Divider
        tk.Frame(root, bg=ACCENT, height=1).pack(fill="x", padx=12)

        # Session info
        info_frame = tk.Frame(root, bg=BG, pady=8, padx=12)
        info_frame.pack(fill="x")

        self._lbl_session = self._make_info_row(info_frame, "Session:")
        self._lbl_model = self._make_info_row(info_frame, "Model:")
        self._lbl_cost = self._make_info_row(info_frame, "Cost:")
        self._lbl_duration = self._make_info_row(info_frame, "Duration:")

        # Divider
        tk.Frame(root, bg=ACCENT, height=1).pack(fill="x", padx=12)

        # Recent projects
        proj_header = tk.Frame(root, bg=BG, padx=12, pady=(8, 4))
        proj_header.pack(fill="x")
        tk.Label(proj_header, text="Recent Projects", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(anchor="w")

        self._projects_frame = tk.Frame(root, bg=BG, padx=12)
        self._projects_frame.pack(fill="x", expand=True)

        # Divider
        tk.Frame(root, bg=ACCENT, height=1).pack(fill="x", padx=12, pady=(4, 0))

        # Dashboard button
        btn_frame = tk.Frame(root, bg=BG, pady=8)
        btn_frame.pack(fill="x")
        dash_btn = tk.Label(
            btn_frame,
            text="Open Dashboard",
            bg=ACCENT,
            fg=FG,
            font=("Segoe UI", 9),
            padx=16,
            pady=6,
            cursor="hand2",
        )
        dash_btn.pack()
        dash_btn.bind("<Button-1>", lambda e: self._open_dashboard())

    def _make_bar(self, parent, label: str):
        row = tk.Frame(parent, bg=BG, pady=2)
        row.pack(fill="x")
        tk.Label(row, text=label, bg=BG, fg=FG_DIM, font=("Segoe UI", 9), width=8, anchor="w").pack(side="left")

        bar_bg = tk.Frame(row, bg="#2a2a4a", height=14, width=150)
        bar_bg.pack(side="left", padx=(4, 4))
        bar_bg.pack_propagate(False)
        bar_fill = tk.Frame(bar_bg, bg=GREEN, height=14)
        bar_fill.place(x=0, y=0, relheight=1.0, relwidth=0.0)

        lbl = tk.Label(row, text="0%", bg=BG, fg=FG, font=("Segoe UI", 9, "bold"), width=5, anchor="e")
        lbl.pack(side="left")

        return bar_fill, lbl

    def _make_info_row(self, parent, label: str) -> tk.Label:
        row = tk.Frame(parent, bg=BG, pady=1)
        row.pack(fill="x")
        tk.Label(row, text=label, bg=BG, fg=FG_DIM, font=("Segoe UI", 9), width=9, anchor="w").pack(side="left")
        val = tk.Label(row, text="--", bg=BG, fg=FG, font=("Segoe UI", 9), anchor="w")
        val.pack(side="left", fill="x")
        return val

    def _refresh_ui(self):
        s = self._state
        self._update_bar(self._bar_5h, self._lbl_5h, s.five_hour_pct)
        self._update_bar(self._bar_7d, self._lbl_7d, s.seven_day_pct)
        self._update_bar(self._bar_ctx, self._lbl_ctx, s.context_pct)

        project_name = Path(s.project_dir).name if s.project_dir else "--"
        self._lbl_session.config(text=project_name)
        self._lbl_model.config(text=s.model or "--")
        self._lbl_cost.config(text=f"${s.total_cost:.2f}" if s.total_cost else "--")

        if s.total_duration_ms:
            secs = s.total_duration_ms // 1000
            mins, secs = divmod(secs, 60)
            self._lbl_duration.config(text=f"{mins}m {secs}s")
        else:
            self._lbl_duration.config(text="--")

        self._refresh_projects()

    def _update_bar(self, bar_fill, label, pct: float):
        color = _pct_color(pct)
        clamped = max(0, min(100, pct))
        bar_fill.configure(bg=color)
        bar_fill.place(x=0, y=0, relheight=1.0, relwidth=clamped / 100.0)
        label.config(text=f"{int(pct)}%")

    def _refresh_projects(self):
        for widget in self._projects_frame.winfo_children():
            widget.destroy()
        projects = self._db.get_recent_projects(limit=5)
        for p in projects:
            dirname = Path(p["directory"]).name
            is_active = self._state.project_dir and Path(self._state.project_dir).name == dirname
            row = tk.Frame(self._projects_frame, bg=BG, pady=1)
            row.pack(fill="x")
            lbl = tk.Label(
                row,
                text=f"  \u25b8 {dirname}",
                bg=BG,
                fg=GREEN if is_active else FG_DIM,
                font=("Segoe UI", 9),
                cursor="hand2",
                anchor="w",
            )
            lbl.pack(side="left")
            if is_active:
                tk.Label(row, text="(active)", bg=BG, fg=GREEN, font=("Segoe UI", 8)).pack(side="right")
            directory = p["directory"]
            lbl.bind("<Button-1>", lambda e, d=directory: self._launch_claude(d))

    def _launch_claude(self, directory: str):
        import subprocess
        subprocess.Popen(f'start cmd /k "cd /d {directory} && claude"', shell=True)

    def _start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _do_drag(self, event):
        x = self._root.winfo_x() + event.x - self._drag_x
        y = self._root.winfo_y() + event.y - self._drag_y
        self._root.geometry(f"+{x}+{y}")
```

- [ ] **Step 2: Manually test the popup**

Run: `cd C:\Projects\ClaudeTray && C:\Users\gvaro\AppData\Local\Programs\Python\Python312\python.exe -m claudetray`

Expected: Left-click the tray icon opens the dark-themed popup near the taskbar. Shows usage bars (0% if no active session, live values if session running). Close button and click-away dismiss the popup. Recent projects list is clickable.

- [ ] **Step 3: Commit**

```bash
git add claudetray/popup.py
git commit -m "feat: tkinter quick popup with usage bars and project list"
```

---

### Task 7: Web Dashboard

**Files:**
- Create: `claudetray/dashboard/__init__.py`
- Create: `claudetray/dashboard/server.py`
- Create: `claudetray/dashboard/templates/base.html`
- Create: `claudetray/dashboard/templates/index.html`
- Create: `claudetray/dashboard/templates/sessions.html`
- Create: `claudetray/dashboard/templates/projects.html`
- Create: `claudetray/dashboard/templates/settings.html`
- Create: `claudetray/dashboard/static/style.css`
- Create: `claudetray/dashboard/static/app.js`
- Create: `tests/test_dashboard.py`

**Interfaces:**
- Consumes: `Config` from `claudetray.config`. `Database` from `claudetray.data.db`. `TrayApp` (for live state) passed via `create_app()`.
- Produces: `create_app(config, db, tray=None) -> Flask` factory function. Routes: `/` (usage overview), `/sessions` (session history), `/projects` (project list), `/settings` (settings page), `/api/state` (JSON current state), `/api/snapshots` (JSON usage history), `/api/settings` (GET/POST settings).

- [ ] **Step 1: Write failing tests for dashboard routes**

```
tests/test_dashboard.py
```

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\Projects\ClaudeTray && C:\Users\gvaro\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_dashboard.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'claudetray.dashboard'`

- [ ] **Step 3: Write Flask server**

```
claudetray/dashboard/__init__.py
```

(empty file)

```
claudetray/dashboard/server.py
```

```python
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request
from ..config import Config
from ..data.db import Database


def create_app(config: Config, db: Database, tray=None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    @app.route("/")
    def index():
        state = _get_state(tray)
        snapshots = db.get_snapshots(since=datetime.now() - timedelta(hours=24))
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
        updates = request.get_json()
        for key, value in updates.items():
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
```

- [ ] **Step 4: Write HTML templates**

```
claudetray/dashboard/templates/base.html
```

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ClaudeTray Dashboard</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
</head>
<body>
    <nav>
        <div class="nav-brand">ClaudeTray</div>
        <div class="nav-links">
            <a href="/" class="{% if request.path == '/' %}active{% endif %}">Usage</a>
            <a href="/sessions" class="{% if request.path == '/sessions' %}active{% endif %}">Sessions</a>
            <a href="/projects" class="{% if request.path == '/projects' %}active{% endif %}">Projects</a>
            <a href="/settings" class="{% if request.path == '/settings' %}active{% endif %}">Settings</a>
        </div>
    </nav>
    <main>
        {% block content %}{% endblock %}
    </main>
    <script src="{{ url_for('static', filename='app.js') }}"></script>
</body>
</html>
```

```
claudetray/dashboard/templates/index.html
```

```html
{% extends "base.html" %}
{% block content %}
<div class="dashboard-grid">
    <div class="card gauge-card">
        <h3>5-Hour Usage</h3>
        <div class="gauge" id="gauge-5h">
            <canvas id="chart-5h" width="200" height="200"></canvas>
            <div class="gauge-value" id="val-5h">{{ state.five_hour_pct | default(0) | int }}%</div>
        </div>
        <div class="reset-timer" id="reset-5h"></div>
    </div>
    <div class="card gauge-card">
        <h3>7-Day Usage</h3>
        <div class="gauge" id="gauge-7d">
            <canvas id="chart-7d" width="200" height="200"></canvas>
            <div class="gauge-value" id="val-7d">{{ state.seven_day_pct | default(0) | int }}%</div>
        </div>
        <div class="reset-timer" id="reset-7d"></div>
    </div>
    <div class="card session-card">
        <h3>Current Session</h3>
        {% if state.session_active %}
        <div class="session-info">
            <div class="info-row"><span class="label">Project:</span> <span>{{ state.project_dir | default('--') }}</span></div>
            <div class="info-row"><span class="label">Model:</span> <span>{{ state.model | default('--') }}</span></div>
            <div class="info-row"><span class="label">Cost:</span> <span>${{ "%.2f" | format(state.total_cost | default(0)) }}</span></div>
            <div class="info-row"><span class="label">Context:</span> <span>{{ state.context_pct | default(0) | int }}%</span></div>
        </div>
        {% else %}
        <div class="no-session">No active session</div>
        {% endif %}
    </div>
</div>
<div class="card chart-card">
    <h3>Usage History (24h)</h3>
    <canvas id="history-chart" height="80"></canvas>
</div>
<script>
    const snapshots = {{ snapshots | tojson }};
    const state = {{ state | tojson }};
</script>
{% endblock %}
```

```
claudetray/dashboard/templates/sessions.html
```

```html
{% extends "base.html" %}
{% block content %}
<div class="card">
    <h2>Session History</h2>
    <table>
        <thead>
            <tr>
                <th>Project</th>
                <th>Model</th>
                <th>Cost</th>
                <th>Tokens In</th>
                <th>Tokens Out</th>
                <th>Last Active</th>
            </tr>
        </thead>
        <tbody>
            {% for s in sessions %}
            <tr>
                <td>{{ s.project_dir.split('\\')[-1] }}</td>
                <td>{{ s.model }}</td>
                <td>${{ "%.2f" | format(s.total_cost) }}</td>
                <td>{{ "{:,}".format(s.tokens_in) }}</td>
                <td>{{ "{:,}".format(s.tokens_out) }}</td>
                <td>{{ s.last_seen.strftime('%Y-%m-%d %H:%M') }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
```

```
claudetray/dashboard/templates/projects.html
```

```html
{% extends "base.html" %}
{% block content %}
<div class="card">
    <h2>Projects</h2>
    <div class="project-grid">
        {% for p in projects %}
        <div class="project-item">
            <div class="project-name">{{ p.directory.split('\\')[-1] }}</div>
            <div class="project-path">{{ p.directory }}</div>
            <div class="project-meta">{{ p.session_count }} sessions &middot; Last: {{ p.last_used[:10] }}</div>
        </div>
        {% endfor %}
    </div>
</div>
{% endblock %}
```

```
claudetray/dashboard/templates/settings.html
```

```html
{% extends "base.html" %}
{% block content %}
<div class="card">
    <h2>Settings</h2>
    <form id="settings-form">
        <div class="setting-row">
            <label for="run_on_startup">Run on Startup</label>
            <input type="checkbox" id="run_on_startup" {% if config.get('run_on_startup') %}checked{% endif %}>
        </div>
        <div class="setting-row">
            <label for="refresh_interval_active">Active Refresh (seconds)</label>
            <input type="number" id="refresh_interval_active" value="{{ config.get('refresh_interval_active') }}" min="1" max="60">
        </div>
        <div class="setting-row">
            <label for="refresh_interval_idle">Idle Refresh (seconds)</label>
            <input type="number" id="refresh_interval_idle" value="{{ config.get('refresh_interval_idle') }}" min="10" max="300">
        </div>
        <div class="setting-row">
            <label for="api_key">API Key (optional fallback)</label>
            <input type="password" id="api_key" value="{{ config.get('api_key') or '' }}" placeholder="sk-ant-...">
        </div>
        <div class="setting-row">
            <label for="dashboard_port">Dashboard Port</label>
            <input type="number" id="dashboard_port" value="{{ config.get('dashboard_port') }}" min="1024" max="65535">
        </div>
        <div class="setting-row">
            <label for="theme">Theme</label>
            <select id="theme">
                <option value="dark" {% if config.get('theme') == 'dark' %}selected{% endif %}>Dark</option>
                <option value="light" {% if config.get('theme') == 'light' %}selected{% endif %}>Light</option>
            </select>
        </div>
        <div class="setting-row">
            <label for="data_retention_days">Data Retention (days)</label>
            <input type="number" id="data_retention_days" value="{{ config.get('data_retention_days') }}" min="1" max="365">
        </div>
        <button type="submit" class="btn">Save Settings</button>
        <div id="save-status"></div>
    </form>
</div>
{% endblock %}
```

- [ ] **Step 5: Write CSS and JavaScript**

```
claudetray/dashboard/static/style.css
```

```css
:root {
    --bg: #0f0f1a;
    --bg-card: #1a1a2e;
    --bg-nav: #16213e;
    --fg: #e0e0e0;
    --fg-dim: #888;
    --accent: #0f3460;
    --green: #22c55e;
    --yellow: #eab308;
    --red: #ef4444;
    --border: #2a2a4a;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: var(--bg);
    color: var(--fg);
    min-height: 100vh;
}

nav {
    background: var(--bg-nav);
    display: flex;
    align-items: center;
    padding: 0 24px;
    height: 48px;
    border-bottom: 1px solid var(--border);
}

.nav-brand {
    font-size: 16px;
    font-weight: 700;
    margin-right: 32px;
}

.nav-links a {
    color: var(--fg-dim);
    text-decoration: none;
    padding: 12px 16px;
    font-size: 14px;
    transition: color 0.2s;
}

.nav-links a:hover, .nav-links a.active {
    color: var(--fg);
}

.nav-links a.active {
    border-bottom: 2px solid var(--green);
}

main {
    max-width: 1000px;
    margin: 24px auto;
    padding: 0 24px;
}

.card {
    background: var(--bg-card);
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 16px;
    border: 1px solid var(--border);
}

.card h2, .card h3 {
    margin-bottom: 16px;
    font-weight: 600;
}

.dashboard-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 16px;
    margin-bottom: 16px;
}

.gauge-card {
    text-align: center;
}

.gauge {
    position: relative;
    width: 200px;
    height: 200px;
    margin: 0 auto;
}

.gauge-value {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    font-size: 32px;
    font-weight: 700;
}

.reset-timer {
    margin-top: 8px;
    font-size: 13px;
    color: var(--fg-dim);
}

.session-card .session-info { line-height: 2; }
.session-card .info-row .label { color: var(--fg-dim); margin-right: 8px; }
.no-session { color: var(--fg-dim); font-style: italic; padding: 20px 0; }

.chart-card { margin-top: 16px; }

table {
    width: 100%;
    border-collapse: collapse;
}

th, td {
    padding: 10px 12px;
    text-align: left;
    border-bottom: 1px solid var(--border);
}

th {
    color: var(--fg-dim);
    font-weight: 600;
    font-size: 13px;
    text-transform: uppercase;
}

.project-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.project-item {
    background: var(--bg);
    border-radius: 6px;
    padding: 14px;
    border: 1px solid var(--border);
}
.project-name { font-weight: 600; font-size: 15px; margin-bottom: 4px; }
.project-path { font-size: 12px; color: var(--fg-dim); word-break: break-all; margin-bottom: 4px; }
.project-meta { font-size: 12px; color: var(--fg-dim); }

.setting-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 0;
    border-bottom: 1px solid var(--border);
}

.setting-row label { font-size: 14px; }

.setting-row input[type="number"],
.setting-row input[type="password"],
.setting-row select {
    background: var(--bg);
    color: var(--fg);
    border: 1px solid var(--border);
    padding: 6px 10px;
    border-radius: 4px;
    font-size: 14px;
    width: 200px;
}

.setting-row input[type="checkbox"] {
    width: 18px;
    height: 18px;
}

.btn {
    background: var(--accent);
    color: var(--fg);
    border: none;
    padding: 10px 24px;
    border-radius: 6px;
    font-size: 14px;
    cursor: pointer;
    margin-top: 16px;
}

.btn:hover { opacity: 0.9; }

#save-status {
    margin-top: 8px;
    font-size: 13px;
    color: var(--green);
}
```

```
claudetray/dashboard/static/app.js
```

```javascript
document.addEventListener('DOMContentLoaded', function() {
    // Gauge charts on index page
    if (document.getElementById('chart-5h')) {
        initGauges();
        initHistoryChart();
        initResetTimers();
        setInterval(refreshState, 10000);
    }

    // Settings form
    const form = document.getElementById('settings-form');
    if (form) {
        form.addEventListener('submit', saveSettings);
    }
});

function pctColor(pct) {
    if (pct >= 80) return '#ef4444';
    if (pct >= 60) return '#eab308';
    return '#22c55e';
}

function initGauges() {
    createGauge('chart-5h', state.five_hour_pct || 0);
    createGauge('chart-7d', state.seven_day_pct || 0);
}

function createGauge(canvasId, pct) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            datasets: [{
                data: [pct, 100 - pct],
                backgroundColor: [pctColor(pct), '#2a2a4a'],
                borderWidth: 0,
            }]
        },
        options: {
            cutout: '75%',
            responsive: false,
            plugins: { legend: { display: false }, tooltip: { enabled: false } },
            rotation: -90,
            circumference: 360,
        }
    });
}

function initHistoryChart() {
    const ctx = document.getElementById('history-chart');
    if (!ctx || !snapshots || snapshots.length === 0) return;

    const labels = snapshots.map(s => {
        const d = new Date(s.timestamp);
        return d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
    });

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: '5-Hour',
                    data: snapshots.map(s => s.five_hour_pct),
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59,130,246,0.1)',
                    fill: true,
                    tension: 0.3,
                },
                {
                    label: '7-Day',
                    data: snapshots.map(s => s.seven_day_pct),
                    borderColor: '#8b5cf6',
                    backgroundColor: 'rgba(139,92,246,0.1)',
                    fill: true,
                    tension: 0.3,
                }
            ]
        },
        options: {
            responsive: true,
            scales: {
                y: { min: 0, max: 100, grid: { color: '#2a2a4a' }, ticks: { color: '#888' } },
                x: { grid: { color: '#2a2a4a' }, ticks: { color: '#888', maxTicksLimit: 12 } },
            },
            plugins: {
                legend: { labels: { color: '#e0e0e0' } },
            },
        }
    });
}

function initResetTimers() {
    updateResetTimer('reset-5h', state.five_hour_resets_at);
    updateResetTimer('reset-7d', state.seven_day_resets_at);
    setInterval(function() {
        updateResetTimer('reset-5h', state.five_hour_resets_at);
        updateResetTimer('reset-7d', state.seven_day_resets_at);
    }, 1000);
}

function updateResetTimer(elementId, resetEpoch) {
    const el = document.getElementById(elementId);
    if (!el || !resetEpoch) { if (el) el.textContent = ''; return; }
    const now = Math.floor(Date.now() / 1000);
    const diff = resetEpoch - now;
    if (diff <= 0) { el.textContent = 'Resetting...'; return; }
    const h = Math.floor(diff / 3600);
    const m = Math.floor((diff % 3600) / 60);
    el.textContent = 'Resets in ' + h + 'h ' + m + 'm';
}

function refreshState() {
    fetch('/api/state')
        .then(r => r.json())
        .then(data => {
            document.getElementById('val-5h').textContent = Math.round(data.five_hour_pct) + '%';
            document.getElementById('val-7d').textContent = Math.round(data.seven_day_pct) + '%';
            state.five_hour_resets_at = data.five_hour_resets_at;
            state.seven_day_resets_at = data.seven_day_resets_at;
        })
        .catch(() => {});
}

function saveSettings(e) {
    e.preventDefault();
    const data = {
        run_on_startup: document.getElementById('run_on_startup').checked,
        refresh_interval_active: parseInt(document.getElementById('refresh_interval_active').value),
        refresh_interval_idle: parseInt(document.getElementById('refresh_interval_idle').value),
        api_key: document.getElementById('api_key').value || null,
        dashboard_port: parseInt(document.getElementById('dashboard_port').value),
        theme: document.getElementById('theme').value,
        data_retention_days: parseInt(document.getElementById('data_retention_days').value),
    };
    fetch('/api/settings', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data),
    })
    .then(r => r.json())
    .then(() => {
        document.getElementById('save-status').textContent = 'Settings saved!';
        setTimeout(() => document.getElementById('save-status').textContent = '', 3000);
    });
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd C:\Projects\ClaudeTray && C:\Users\gvaro\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_dashboard.py -v`

Expected: All 8 tests PASS

- [ ] **Step 7: Manually test the full dashboard**

Run: `cd C:\Projects\ClaudeTray && C:\Users\gvaro\AppData\Local\Programs\Python\Python312\python.exe -m claudetray`

Right-click tray → Open Dashboard. Browser opens to `http://localhost:5199`. Verify: usage gauges render, history chart shows (if data exists), sessions/projects/settings pages load, settings save works.

- [ ] **Step 8: Commit**

```bash
git add claudetray/dashboard/ tests/test_dashboard.py
git commit -m "feat: Flask web dashboard with usage charts and settings"
```

---

### Task 8: Startup Manager + Build + README

**Files:**
- Create: `build.py`
- Create: `README.md`
- Create: `.github/workflows/build.yml`
- Create: `.gitignore`
- Create: `assets/` (placeholder for icon)

**Interfaces:**
- Consumes: All previous modules.
- Produces: PyInstaller build script, GitHub Actions workflow, project README.

- [ ] **Step 1: Create .gitignore and assets**

```
.gitignore
```

```
__pycache__/
*.pyc
*.pyo
*.egg-info/
dist/
build/
*.spec
.pytest_cache/
logs/session_log.md
*.db
.env
```

Create `assets/` directory (icon will be generated or added manually).

- [ ] **Step 2: Write build.py**

```
build.py
```

```python
"""Build ClaudeTray into a standalone .exe using PyInstaller."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
ENTRY = ROOT / "claudetray" / "app.py"
TEMPLATES = ROOT / "claudetray" / "dashboard" / "templates"
STATIC = ROOT / "claudetray" / "dashboard" / "static"
ICON = ROOT / "assets" / "icon.ico"


def build():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "ClaudeTray",
        "--add-data", f"{TEMPLATES};claudetray/dashboard/templates",
        "--add-data", f"{STATIC};claudetray/dashboard/static",
    ]
    if ICON.exists():
        cmd.extend(["--icon", str(ICON)])
    cmd.append(str(ENTRY))

    print(f"Building ClaudeTray...")
    subprocess.run(cmd, check=True)
    print(f"\nBuild complete! Executable at: dist/ClaudeTray.exe")


if __name__ == "__main__":
    build()
```

- [ ] **Step 3: Write GitHub Actions workflow**

```
.github/workflows/build.yml
```

```yaml
name: Build ClaudeTray

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pyinstaller

      - name: Build executable
        run: python build.py

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: ClaudeTray
          path: dist/ClaudeTray.exe

      - name: Create Release
        uses: softprops/action-gh-release@v2
        with:
          files: dist/ClaudeTray.exe
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

- [ ] **Step 4: Write README.md**

```
README.md
```

```markdown
# ClaudeTray

Windows system tray monitor for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) usage. Like a battery meter for your Claude rate limits.

![System Tray](https://img.shields.io/badge/platform-Windows-blue)
![Python](https://img.shields.io/badge/python-3.12+-green)

## Features

- **Always-visible usage** — Tray icon shows 5-hour and 7-day rate limit percentages, color-coded green/yellow/red
- **Quick popup** — Click the tray icon for at-a-glance usage bars, session info, and recent projects
- **Web dashboard** — Full usage history charts, session browser, project launcher, and settings
- **Auto-detect** — Reads Claude Code's statusline data automatically, no configuration needed
- **Usage history** — Tracks usage over time in a local SQLite database
- **Run on startup** — Optional Windows startup integration

## Install

### Download

Grab `ClaudeTray.exe` from the [latest release](../../releases/latest) and run it. No installer needed.

### From source

```
git clone https://github.com/VAROIndustries/ClaudeTray.git
cd ClaudeTray
pip install -r requirements.txt
python -m claudetray
```

## Setup

ClaudeTray works automatically if you have Claude Code installed with the statusline hook enabled. It reads the statusline debug JSON that Claude Code emits.

### Statusline Hook

ClaudeTray reads from the statusline debug JSON file. If you have a custom statusline command in Claude Code that writes to `/tmp/statusline_debug.json`, ClaudeTray will pick it up automatically.

### Settings

Settings are stored in `~/.claudetray/settings.json`:

| Setting | Default | Description |
|---------|---------|-------------|
| `run_on_startup` | `false` | Launch ClaudeTray at Windows login |
| `refresh_interval_active` | `5` | Seconds between updates when session active |
| `refresh_interval_idle` | `60` | Seconds between updates when idle |
| `dashboard_port` | `5199` | Port for the web dashboard |
| `theme` | `dark` | Dashboard theme (dark/light) |
| `data_retention_days` | `30` | How long to keep usage history |

## Build

```
pip install pyinstaller
python build.py
```

Output: `dist/ClaudeTray.exe`

## License

MIT
```

- [ ] **Step 5: Create a LICENSE file**

```
LICENSE
```

```
MIT License

Copyright (c) 2026 VARO Industries

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 6: Run full test suite**

Run: `cd C:\Projects\ClaudeTray && C:\Users\gvaro\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/ -v`

Expected: All tests PASS (config: 6, db: 5, watcher: 9, icon: 5, dashboard: 8 = 33 total)

- [ ] **Step 7: Commit and create GitHub repo**

```bash
git init
git add -A
git commit -m "feat: ClaudeTray v0.1.0 - Windows system tray monitor for Claude Code"
gh repo create VAROIndustries/ClaudeTray --public --source=. --remote=origin --push
```

Note: This is a **public** repo per user requirement.

- [ ] **Step 8: Test the build**

Run: `cd C:\Projects\ClaudeTray && C:\Users\gvaro\AppData\Local\Programs\Python\Python312\python.exe -m pip install pyinstaller && C:\Users\gvaro\AppData\Local\Programs\Python\Python312\python.exe build.py`

Expected: `dist/ClaudeTray.exe` is created. Run it and verify tray icon appears.

- [ ] **Step 9: Commit build artifacts config**

```bash
git add .
git commit -m "chore: add build script, CI workflow, README, and LICENSE"
```
