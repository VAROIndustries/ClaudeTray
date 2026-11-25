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


def copy_to_clipboard(text: str) -> bool:
    """Put text on the Windows clipboard. Returns False if that isn't possible."""
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return False
    if not hasattr(ctypes, "windll"):
        return False
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    data = text.encode("utf-16-le") + b"\x00\x00"
    for _ in range(5):  # another app may hold the clipboard for a moment
        if user32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        return False
    try:
        user32.EmptyClipboard()
        h = kernel32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
        ptr = kernel32.GlobalLock(h)
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(h)
        return bool(user32.SetClipboardData(13, h))  # CF_UNICODETEXT; clipboard owns h now
    finally:
        user32.CloseClipboard()
