"""Claude Queue: which Claude sessions are waiting on you.

Talks to your own Claude Queue Worker (github.com/VAROIndustries/claude-queue).
Configured by `queue_url` and `queue_view_key` in ~/.claudetray/settings.json,
or else by "url" and "viewKey" in ~/.claude-queue.json (the file the Claude
Queue plugin already reads). With neither, the feature stays off.
"""
import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple
from urllib.parse import quote

import requests

LABELS = {"permission": "needs permission", "question": "asked you something", "done": "finished"}
RANK = {"permission": 3, "question": 2, "done": 1}
QUEUE_CONFIG_PATH = Path.home() / ".claude-queue.json"


@dataclass
class QueueSession:
    id: str
    project: str
    kind: str
    host: str
    remote: bool
    cwd: str
    link: str
    summary: str
    waited_ms: float

    @property
    def label(self) -> str:
        return LABELS.get(self.kind, self.kind)

    @property
    def waited(self) -> str:
        return format_age(self.waited_ms)

    @property
    def is_old(self) -> bool:
        return self.waited_ms > 30 * 60 * 1000

    @property
    def can_open_link(self) -> bool:
        return self.link.startswith("https://")

    @property
    def resume_command(self) -> str:
        if self.cwd:
            return f'cd /d "{self.cwd}" && claude --resume {self.id}'
        return f"claude --resume {self.id}"


def format_age(ms: float) -> str:
    m = int(ms // 60000)
    if m < 1:
        return "just now"
    if m < 60:
        return f"{m}m"
    h = m // 60
    if h < 48:
        return f"{h}h {m % 60}m"
    return f"{h // 24}d"


def resolve_queue_config(config, path: Path = QUEUE_CONFIG_PATH) -> Optional[Tuple[str, str]]:
    """(url, view key) from ClaudeTray settings, else ~/.claude-queue.json, else None."""
    url, key = config.get("queue_url"), config.get("queue_view_key")
    if not (url and key):
        try:
            with open(path, encoding="utf-8-sig") as fh:
                data = json.load(fh)
            url, key = url or data.get("url"), key or data.get("viewKey")
        except Exception:
            pass
    if url and key:
        return str(url).rstrip("/"), str(key)
    return None


def parse_sessions(data: dict) -> List[QueueSession]:
    now = float(data.get("now") or time.time() * 1000)
    rows = []
    for s in data.get("waiting") or []:
        since = s.get("waitingSince") or s.get("updated") or now
        rows.append(QueueSession(
            id=str(s.get("id", "")),
            project=s.get("project") or "(no folder)",
            kind=str(s.get("kind") or ""),
            host=str(s.get("host") or ""),
            remote=bool(s.get("remote")),
            cwd=str(s.get("cwd") or ""),
            link=str(s.get("link") or ""),
            summary=str(s.get("summary") or ""),
            waited_ms=max(0.0, now - float(since)),
        ))
    rows.sort(key=lambda r: (-RANK.get(r.kind, 0), -r.waited_ms))
    return rows


class QueueClient:
    def __init__(self, url: str, key: str, timeout: float = 8):
        self.url, self.key, self.timeout = url, key, timeout

    def _call(self, method: str, path: str, body=None):
        r = requests.request(method, self.url + path, json=body, timeout=self.timeout,
                             headers={"Authorization": "Bearer " + self.key})
        r.raise_for_status()
        return r.json()

    def sessions(self) -> List[QueueSession]:
        return parse_sessions(self._call("GET", "/api/sessions"))

    def snooze(self, session_id: str, minutes: int):
        self._call("POST", f"/api/sessions/{quote(session_id, safe='')}/snooze", {"minutes": minutes})

    def dismiss(self, session_id: str):
        self._call("POST", f"/api/sessions/{quote(session_id, safe='')}/dismiss", {})


class QueuePoller:
    """Polls the queue on a background thread and reports (rows, error)."""

    def __init__(self, client: QueueClient, on_update: Callable[[List[QueueSession], Optional[str]], None],
                 interval: float = 20):
        self.client, self.on_update, self.interval = client, on_update, interval
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def refresh_now(self):
        self._wake.set()

    def stop(self):
        self._stop.set()
        self._wake.set()

    def _run(self):
        time.sleep(1)  # let the tray icon come up first
        while not self._stop.is_set():
            try:
                rows, err = self.client.sessions(), None
            except Exception as e:  # network down, bad key: keep the last list, report the error
                rows, err = None, str(e)
            try:
                self.on_update(rows, err)
            except Exception:
                pass
            self._wake.wait(self.interval)
            self._wake.clear()
