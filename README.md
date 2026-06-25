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
