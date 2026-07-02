import subprocess
import threading
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
        subprocess.Popen(["cmd", "/c", "start", "cmd", "/k", f"cd /d {directory} && claude"])

    def on_api_update(self, rate_limits):
        """Receive optional API rate limit data."""
        self._api_rate_limits = rate_limits

    def on_state_update(self, state: AppState):
        self.state = state
        self._icon.icon = render_icon(
            state.five_hour_pct, state.seven_day_pct,
            dimmed=not state.session_active,
        )
        if state.session_active:
            self._icon.title = (
                f"Claude: 5h: {int(state.five_hour_pct)}% | 7d: {int(state.seven_day_pct)}%"
            )
        else:
            ago = ""
            if state.last_update:
                delta = datetime.now() - state.last_update
                mins = int(delta.total_seconds() // 60)
                ago = f" | Last: {mins}m ago" if mins > 0 else ""
            self._icon.title = (
                f"Claude: 5h: {int(state.five_hour_pct)}% | 7d: {int(state.seven_day_pct)}%{ago}"
            )
        # Update popup if visible
        if self._popup is not None:
            try:
                self._popup.update_state(state)
            except Exception:
                pass

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

    def _toggle_startup(self, icon, item):
        current = self.config.get("run_on_startup")
        self.config.set("run_on_startup", not current)
        startup.set_run_on_startup(not current)

    def _quit(self, icon, item):
        self._icon.stop()

    def run(self):
        self._icon.run()

    def stop(self):
        self._icon.stop()
