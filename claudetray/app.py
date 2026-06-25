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
