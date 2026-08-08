import os
import subprocess
import time
from typing import Optional


def open_claude(directory: str) -> bool:
    """Open a new console in `directory` running `claude`.

    Uses Popen's cwd rather than a `cd /d ...` prefix so paths containing
    spaces need no quoting. Returns False if the directory is gone.
    """
    if not directory or not os.path.isdir(directory):
        return False
    subprocess.Popen(["cmd", "/c", "start", "", "cmd", "/k", "claude"], cwd=directory)
    return True


def format_reset_countdown(resets_at: Optional[int], now: Optional[int] = None) -> str:
    """Format an epoch reset time as a compact countdown, e.g. "2h 15m".

    Returns "" when no reset time is known, and "now" when the reset time
    has already passed. Uses days for spans of 24h or more so the 7-day
    window stays readable.
    """
    if not resets_at:
        return ""
    if now is None:
        now = int(time.time())
    diff = int(resets_at) - now
    if diff <= 0:
        return "now"
    days, rem = divmod(diff, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"
