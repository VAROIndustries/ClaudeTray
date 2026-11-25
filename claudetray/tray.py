import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional

import pystray

from . import startup
from .config import Config
from .data.db import Database
from .data.models import AppState
from .icon_renderer import render_icon
from .util import copy_to_clipboard, format_reset_countdown, open_claude

BROWSER_REFRESH_SECONDS = 300


class TrayApp:
    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db
        self.state = AppState()
        self._popup = None
        self._dashboard_thread: Optional[threading.Thread] = None
        # Claude Queue (sessions waiting on you); None client = feature off
        self.queue_client = None
        self.queue_rows: list = []
        self.queue_error: Optional[str] = None
        self._queue_seen: Optional[set] = None  # None until the first poll, so startup doesn't notify
        self._queue_poller = None
        # Claude in Chrome browsers, cached because reading profiles touches disk
        self._browsers: Optional[list] = None
        self._browsers_at = 0.0
        self._icon = pystray.Icon(
            "ClaudeTray",
            render_icon(0, 0),
            "Claude: No data yet",
            menu=self._build_menu(),
        )

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(lambda: self._menu_items())

    def _menu_items(self) -> list:
        items = [
            pystray.MenuItem("Open Quick View", self._show_popup, default=True),
            pystray.MenuItem("Open Dashboard", self._open_dashboard),
            pystray.Menu.SEPARATOR,
        ]
        items += self._queue_menu_items()
        items += [
            pystray.MenuItem("Claude Browsers", pystray.Menu(lambda: self._browser_menu_items())),
            pystray.MenuItem("New Claude Session", pystray.Menu(self._project_menu_items)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Run on Startup",
                self._toggle_startup,
                checked=lambda item: self.config.get("run_on_startup"),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("About ClaudeTray", self._show_about),
            pystray.MenuItem("Quit", self._quit),
        ]
        return items

    # ------------------------------------------------------- Claude Queue ---

    def start_queue(self, client, poller_cls, interval: float = 20):
        self.queue_client = client
        self._queue_poller = poller_cls(client, self.on_queue_update, interval=interval)
        self._queue_poller.start()

    def _queue_menu_items(self) -> list:
        if self.queue_client is None:
            return []
        rows = self.queue_rows
        head = f"Waiting on you ({len(rows)})" if rows else "Nothing waiting on you"
        items = [pystray.MenuItem(head, None, enabled=False)]
        if self.queue_error:
            items.append(pystray.MenuItem(f"Can't reach Claude Queue: {self.queue_error[:60]}", None, enabled=False))
        mark = {"permission": "[!!] ", "question": "[?] ", "done": "[ok] "}
        for r in rows[:15]:
            text = f"{mark.get(r.kind, '')}{r.project}  -  {r.label}  -  {r.waited}{' !' if r.is_old else ''}  ({r.host})"
            items.append(pystray.MenuItem(text.replace("&", "&&"), pystray.Menu(*self._session_actions(r))))
        if len(rows) > 15:
            items.append(pystray.MenuItem(f"... and {len(rows) - 15} more", self._open_queue_page))
        items += [pystray.MenuItem("Open Claude Queue Page", self._open_queue_page), pystray.Menu.SEPARATOR]
        return items

    def _session_actions(self, r) -> list:
        if r.can_open_link:
            first = pystray.MenuItem("Open Session", lambda icon, item: webbrowser.open(r.link))
        elif not r.remote:
            first = pystray.MenuItem("Copy Resume Command", lambda icon, item: self._copy(r.resume_command, "Resume command copied"))
        else:
            first = pystray.MenuItem("Open Claude Queue Page", self._open_queue_page)
        return [
            first,
            pystray.MenuItem("Snooze 1 Hour", lambda icon, item: self._queue_action(r.id, "snooze", 60)),
            pystray.MenuItem("Snooze 1 Day", lambda icon, item: self._queue_action(r.id, "snooze", 1440)),
            pystray.MenuItem("Dismiss", lambda icon, item: self._queue_action(r.id, "dismiss")),
        ]

    def _queue_action(self, session_id: str, action: str, minutes: int = 60):
        def work():
            try:
                if action == "snooze":
                    self.queue_client.snooze(session_id, minutes)
                else:
                    self.queue_client.dismiss(session_id)
            except Exception as e:
                self._notify(f"That didn't work: {e}", "Claude Queue")
            if self._queue_poller:
                self._queue_poller.refresh_now()
        threading.Thread(target=work, daemon=True).start()

    def _open_queue_page(self, *args):
        if self.queue_client is not None:
            webbrowser.open(self.queue_client.url)

    def on_queue_update(self, rows, error: Optional[str]):
        self.queue_error = error
        if rows is not None:
            new = [r for r in rows if self._queue_seen is not None
                   and r.id not in self._queue_seen and r.kind != "done"]
            self._queue_seen = {r.id for r in rows}
            self.queue_rows = rows
            if new:
                r = new[0]
                more = f" (+{len(new) - 1} more)" if len(new) > 1 else ""
                self._notify((r.summary or r.host)[:200], f"{r.project}: {r.label}{more}"[:63])
        self._refresh_icon()
        try:
            self._icon.update_menu()
        except Exception:
            pass

    def _queue_badge(self):
        rows = self.queue_rows
        if not rows:
            return 0, ""
        kind = max(rows, key=lambda r: {"permission": 3, "question": 2}.get(r.kind, 1)).kind
        return len(rows), kind

    # ---------------------------------------------------- Claude browsers ---

    def browsers(self, force: bool = False) -> list:
        now = time.monotonic()
        if force or self._browsers is None or now - self._browsers_at > BROWSER_REFRESH_SECONDS:
            try:
                from .browsers import get_claude_browsers
                self._browsers = get_claude_browsers()
            except Exception:
                self._browsers = []
            self._browsers_at = now
        return self._browsers

    def _browser_menu_items(self) -> list:
        found = self.browsers()
        items = [pystray.MenuItem("Click one to copy a \"use this browser\" line for Claude", None, enabled=False),
                 pystray.Menu.SEPARATOR]
        if not found:
            items.append(pystray.MenuItem("No browser profiles with Claude in Chrome found", None, enabled=False))
        for b in found:
            items.append(pystray.MenuItem(b.menu_text.replace("&", "&&"), self._make_copier(b.paste_line)))
        items += [
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Copy Full List", lambda icon, item: self._copy(
                "\r\n".join(f"{b.claude_name} | {b.browser}: {b.profile} | {b.device_id}" for b in found),
                "Browser list copied")),
            pystray.MenuItem("Refresh", lambda icon, item: self._refresh_browsers()),
        ]
        return items

    def _make_copier(self, text: str):
        # Closure, not a default argument: pystray allows at most (icon, item).
        return lambda icon, item: self._copy(text, "Paste it into your Claude chat")

    def _refresh_browsers(self):
        self.browsers(force=True)
        try:
            self._icon.update_menu()
        except Exception:
            pass

    # --------------------------------------------------------------- misc ---

    def _copy(self, text: str, done_message: str):
        if copy_to_clipboard(text):
            self._notify(text[:200], done_message)
        else:
            self._notify("Couldn't reach the clipboard. Try again.", "Not copied")

    def _notify(self, message: str, title: str):
        try:
            self._icon.notify(message, title)
        except Exception:
            pass

    def _project_menu_items(self) -> list:
        projects = self.db.get_recent_projects(limit=8)
        if not projects:
            return [pystray.MenuItem("No recent projects", None, enabled=False)]
        items = []
        for p in projects:
            dirname = Path(p["directory"]).name
            directory = p["directory"]
            items.append(pystray.MenuItem(dirname, self._make_launcher(directory)))
        return items

    def _make_launcher(self, directory: str):
        """Bind `directory` in a closure, not a default argument.

        pystray dispatches actions as action(icon, item), so a default-arg
        capture (lambda _, d=directory) gets `item` in place of the path.
        """
        return lambda icon, item: self._open_claude(directory)

    def _open_claude(self, directory: str):
        open_claude(directory)

    def on_api_update(self, rate_limits):
        """Receive optional API rate limit data."""
        self._api_rate_limits = rate_limits

    def on_state_update(self, state: AppState):
        self.state = state
        self._refresh_icon()
        # Update popup if visible
        if self._popup is not None:
            try:
                self._popup.update_state(state)
            except Exception:
                pass

    def _refresh_icon(self):
        state = self.state
        count, kind = self._queue_badge()
        self._icon.icon = render_icon(
            state.five_hour_pct, state.seven_day_pct,
            dimmed=not state.session_active,
            badge=count, badge_kind=kind,
        )
        self._icon.title = self._tooltip(state, count, kind)

    def _tooltip(self, state: AppState, count: int = 0, kind: str = "") -> str:
        waiting = ""
        if count:
            waiting = f"Waiting on you: {count}" + (" (permission!)" if kind == "permission" else "")
        if state.last_update is None:  # no usage data yet
            return ("Claude: No data yet" + ("\n" + waiting if waiting else ""))[:127]
        title = f"Claude: 5h: {int(state.five_hour_pct)}% | 7d: {int(state.seven_day_pct)}%"
        reset_5h = format_reset_countdown(state.five_hour_resets_at)
        reset_7d = format_reset_countdown(state.seven_day_resets_at)
        resets = []
        if reset_5h:
            resets.append(f"5h resets in {reset_5h}")
        if reset_7d:
            resets.append(f"7d resets in {reset_7d}")
        if resets:
            title += "\n" + " | ".join(resets)
        if not state.session_active and state.last_update:
            delta = datetime.now() - state.last_update
            mins = int(delta.total_seconds() // 60)
            if mins > 0:
                title += f"\nLast: {mins}m ago"
        if waiting:
            title += "\n" + waiting
        return title[:127]  # Windows tooltips hold 127 characters

    def _show_popup(self, icon, item):
        if self._popup is not None:
            try:
                if self._popup.is_visible():
                    self._popup.hide()
                    return
            except Exception:
                self._popup = None

        try:
            from .popup import PopupWindow
            if self._popup is None:
                self._popup = PopupWindow(self.state, self.db, self.config, self._open_dashboard)
            self._popup.show(self.state)
        except ImportError:
            # popup.py not yet implemented (Task 6)
            pass

    def _open_dashboard(self, *args):
        if self._dashboard_thread is None or not self._dashboard_thread.is_alive():
            try:
                from .dashboard.server import create_app, IDLE_TIMEOUT
                import time

                app = create_app(self.config, self.db, self)
                port = self.config.get("dashboard_port")

                from werkzeug.serving import make_server
                server = make_server("127.0.0.1", port, app)
                self._dashboard_server = server

                self._dashboard_thread = threading.Thread(
                    target=server.serve_forever,
                    daemon=True,
                )
                self._dashboard_thread.start()

                def _idle_watcher():
                    while self._dashboard_thread and self._dashboard_thread.is_alive():
                        idle = time.monotonic() - app._last_request_time
                        if idle >= IDLE_TIMEOUT:
                            server.shutdown()
                            self._dashboard_server = None
                            return
                        time.sleep(30)

                threading.Thread(target=_idle_watcher, daemon=True).start()
            except ImportError:
                pass
        port = self.config.get("dashboard_port")
        webbrowser.open(f"http://localhost:{port}")

    def _show_about(self, icon, item):
        from .about import show_about
        show_about()

    def _toggle_startup(self, icon, item):
        current = self.config.get("run_on_startup")
        self.config.set("run_on_startup", not current)
        startup.set_run_on_startup(not current)

    def _quit(self, icon, item):
        if self._queue_poller:
            self._queue_poller.stop()
        self._icon.stop()

    def run(self):
        self._icon.run()

    def stop(self):
        self._icon.stop()
