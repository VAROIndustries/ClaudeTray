import subprocess
import threading
import tkinter as tk
from pathlib import Path
from typing import Callable, Optional

from .config import Config
from .data.db import Database
from .data.models import AppState

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
        proj_header = tk.Frame(root, bg=BG)
        proj_header.pack(fill="x", padx=12, pady=(8, 4))
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
        subprocess.Popen(["cmd", "/c", "start", "cmd", "/k", f"cd /d {directory} && claude"])

    def _start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _do_drag(self, event):
        x = self._root.winfo_x() + event.x - self._drag_x
        y = self._root.winfo_y() + event.y - self._drag_y
        self._root.geometry(f"+{x}+{y}")
