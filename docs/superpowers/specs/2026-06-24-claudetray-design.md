# ClaudeTray — Design Spec

## Overview

ClaudeTray is a Windows system tray application that provides always-visible Claude Code usage monitoring (like a battery meter), quick access to session info, and a full web dashboard for history and settings. Built in Python, packaged as a standalone `.exe`.

**Public repo:** `VAROIndustries/ClaudeTray`

## Architecture

```
┌─────────────────────────────────────────────┐
│                  ClaudeTray                  │
├─────────────┬───────────────┬───────────────┤
│  Tray Icon  │  Quick Popup  │  Web Dashboard│
│  (pystray)  │  (tkinter)    │  (Flask)      │
├─────────────┴───────────────┴───────────────┤
│              Core Data Engine               │
│  ┌──────────┐ ┌───────────┐ ┌────────────┐ │
│  │File Watch│ │ API Poll  │ │  History   │ │
│  │(statusln)│ │(Anthropic)│ │  (SQLite)  │ │
│  └──────────┘ └───────────┘ └────────────┘ │
├─────────────────────────────────────────────┤
│           Config (JSON settings)            │
└─────────────────────────────────────────────┘
```

### Components

- **Tray Icon** — pystray + Pillow renders "41/37" (5h%/7d%) text dynamically as the icon image
- **Quick Popup** — tkinter window anchored near tray for at-a-glance stats
- **Web Dashboard** — Flask on localhost:5199, launched on-demand for full dashboard
- **Core Data Engine** — watches the statusline debug JSON (default: `/tmp/statusline_debug.json` on git-bash, auto-detected), falls back to Anthropic API, stores history in SQLite
- **Config** — JSON file in `~/.claudetray/settings.json`

## Tray Icon

### Icon Rendering
- Pillow generates a small image with text "41/37" (5h%/7d%) on dark background
- Updates every 5 seconds when a session is active (file watcher detects changes)
- Updates every 60 seconds when idle (polls API if configured, otherwise shows last known)
- Color coding based on whichever limit is higher: green (<60%), yellow (60-80%), red (>80%)

### Data Freshness
- Session active: solid icon
- Stale data: dimmed/faded, tooltip shows "Last update: Xm ago"

### Tooltip
- "Claude: 5h: 41% | 7d: 37% | Last update: 2m ago"

### Right-Click Menu
- Open Quick View
- Open Dashboard
- New Claude Session → submenu of recent projects
- Settings
- ---
- Run on Startup (checkbox)
- ---
- Quit

### Left-Click
- Toggles the quick popup window

## Quick Popup (tkinter)

~300x400px dark-themed window anchored near tray icon.

### Layout
```
┌──────────────────────────────┐
│  Claude Usage          ── ×  │
├──────────────────────────────┤
│  5-Hour     ████████░░  41%  │
│  7-Day      ███████░░░  37%  │
│  Context    █░░░░░░░░░   4%  │
├──────────────────────────────┤
│  Session: ClaudeTray         │
│  Model: Opus 4.6 (1M)       │
│  Cost: $0.37                 │
│  Duration: 4m 26s            │
├──────────────────────────────┤
│  Recent Projects             │
│  > ClaudeTray     (active)   │
│  > KnotDo         2h ago     │
│  > NoteSmith      yesterday  │
├──────────────────────────────┤
│  [ Open Dashboard ]          │
└──────────────────────────────┘
```

### Behavior
- Progress bars color-coded (green/yellow/red)
- Clicking a recent project opens a new terminal with `claude` in that directory
- "Active" badge when a session is running in that project
- Window dismisses on focus loss
- No taskbar entry

## Web Dashboard (Flask)

Runs on `localhost:5199`. Only starts when user clicks "Open Dashboard". Shuts down after 5 min idle.

### Pages

**Usage Overview (home)**
- Large usage gauges for 5h and 7d limits
- Usage history chart (last 24h / 7d) from SQLite, plotted with Chart.js
- Rate limit reset countdown timers
- Current session card (if active)

**Sessions**
- List of past sessions: project, model, cost, duration, token counts
- Data from SQLite history

**Projects**
- Directories where Claude has been used (discovered from `~/.claude/projects/`)
- Click to launch a new Claude terminal in that directory
- Last session date/cost per project

**Settings**
- Run on startup toggle (adds/removes Start menu shortcut)
- Refresh interval slider
- API key input (fallback when CLI auth unavailable)
- Theme: dark/light
- Dashboard port config
- Data retention setting

### Tech
- Flask backend, vanilla HTML/CSS/JS, Chart.js for graphs
- Dark theme by default, no frontend framework

## Data Engine

### File Watcher
- Watches `/tmp/statusline_debug.json` using `watchdog` library
- On change: parse JSON, update in-memory state, write snapshot to SQLite, trigger tray icon redraw
- If file unchanged for 60s: mark session as inactive

### API Fallback
- When no active session and API key configured, poll Anthropic API for rate limit info
- Frequency: every 60 seconds when idle
- Auto-detect CLI auth from `~/.claude/` credentials if available

### SQLite Database (`~/.claudetray/history.db`)

**Tables:**
- `usage_snapshots` — timestamp, five_hour_pct, seven_day_pct, context_pct
- `sessions` — session_id, project_dir, model, start_time, last_seen, total_cost, tokens_in, tokens_out
- `projects` — directory path, last_used, session_count

Auto-prune based on retention setting (default 30 days).

### Config (`~/.claudetray/settings.json`)
```json
{
  "run_on_startup": false,
  "refresh_interval_active": 5,
  "refresh_interval_idle": 60,
  "api_key": null,
  "dashboard_port": 5199,
  "theme": "dark",
  "data_retention_days": 30
}
```

## Auth Strategy

1. **Primary:** Piggyback on existing Claude CLI auth — detect that `claude` is logged in and use its session data
2. **Fallback:** User pastes an Anthropic API key in settings, stored in `~/.claudetray/settings.json`

## Packaging & Distribution

### Build
- PyInstaller single-file `.exe`: `pyinstaller --onefile --windowed --icon=icon.ico claudetray.py`
- Target size: ~20-30MB

### Dependencies
- `pystray` — system tray
- `Pillow` — dynamic icon rendering
- `watchdog` — file system monitoring
- `Flask` — web dashboard
- `requests` — API calls
- Chart.js (bundled) — dashboard charts
- SQLite — stdlib

### Installation
- Download `.exe` from GitHub releases, run it
- No installer — settings/data in `~/.claudetray/`
- First run creates directory and default config

### Startup
- Start menu shortcut in `shell:startup` folder, toggled via settings

### GitHub
- Public repo: `VAROIndustries/ClaudeTray`
- GitHub Actions to build `.exe` on release tags
- Link from VAROIndustries site apps page

## Project Structure

```
ClaudeTray/
├── claudetray/
│   ├── __init__.py
│   ├── app.py              # Entry point, tray setup
│   ├── tray.py             # Tray icon, menu, popup trigger
│   ├── icon_renderer.py    # Pillow dynamic text icon
│   ├── popup.py            # tkinter quick view
│   ├── dashboard/
│   │   ├── server.py       # Flask app
│   │   ├── templates/      # HTML
│   │   └── static/         # CSS, JS, Chart.js
│   ├── data/
│   │   ├── watcher.py      # File watcher
│   │   ├── api_client.py   # Anthropic API fallback
│   │   ├── db.py           # SQLite operations
│   │   └── models.py       # Data classes
│   └── config.py           # Settings management
├── assets/
│   └── icon.ico
├── requirements.txt
├── build.py                # PyInstaller build script
├── deploy.sh
└── README.md
```
