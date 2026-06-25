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

    # Optional API polling (only if api_key is configured)
    api_poller = None
    api_key = config.get("api_key")
    if api_key:
        from .data.api_client import AnthropicPoller
        api_poller = AnthropicPoller(
            api_key=api_key,
            on_update=tray.on_api_update,
            interval=config.get("refresh_interval_idle", 60),
        )
        api_poller.start()

    try:
        tray.run()
    finally:
        watcher.stop()
        if api_poller:
            api_poller.stop()
        db.close()


if __name__ == "__main__":
    main()
