import sqlite3
import threading
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
        # One connection shared across watchdog, Timer, and Flask threads —
        # sqlite3 transactions are not safe to interleave, so serialize access.
        self._lock = threading.Lock()
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
            CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON usage_snapshots(timestamp);
        """)
        self.conn.commit()

    def add_snapshot(self, snap: UsageSnapshot):
        with self._lock:
            self.conn.execute(
                "INSERT INTO usage_snapshots (timestamp, five_hour_pct, seven_day_pct, context_pct) VALUES (?, ?, ?, ?)",
                (snap.timestamp.isoformat(), snap.five_hour_pct, snap.seven_day_pct, snap.context_pct),
            )
            self.conn.commit()

    def get_snapshots(self, since: datetime) -> List[UsageSnapshot]:
        with self._lock:
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
        with self._lock:
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
        with self._lock:
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
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM projects ORDER BY last_used DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_sessions(self, limit: int = 50) -> List[SessionInfo]:
        with self._lock:
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
        with self._lock:
            self.conn.execute("DELETE FROM usage_snapshots WHERE timestamp < ?", (cutoff,))
            self.conn.commit()

    def close(self):
        with self._lock:
            self.conn.close()
