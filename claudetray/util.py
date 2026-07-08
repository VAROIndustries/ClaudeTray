import time
from typing import Optional


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
