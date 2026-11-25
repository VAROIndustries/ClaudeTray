"""Which browser profile is which, for the Claude in Chrome extension.

Claude lists connected browsers as "Browser 1", "Browser 2", ... in connection
order, which changes between sessions. Each profile's extension keeps a stable
device ID in its own extension storage, a LevelDB database inside the profile:

    <User Data>/<profile>/Local Extension Settings/<extension id>

This module has a small read-only LevelDB reader (table files, write-ahead log,
Snappy) and reads only keys starting with "bridge". Nothing is ever written.
Ported from ClaudeBrowserTray (github.com/VAROIndustries/ClaudeBrowserTray).
"""
import json
import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

EXTENSION_ID = "fcoeoabgfenejglbffodgkkbkcdhcgfn"


def browser_roots() -> Dict[str, Path]:
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    return {
        "Chrome": local / "Google" / "Chrome" / "User Data",
        "Chrome Beta": local / "Google" / "Chrome Beta" / "User Data",
        "Edge": local / "Microsoft" / "Edge" / "User Data",
        "Brave": local / "BraveSoftware" / "Brave-Browser" / "User Data",
        "Island": local / "Island" / "Island" / "User Data",
    }


# ---------------------------------------------------------------- LevelDB ---

def _varint(b: bytes, p: int) -> Tuple[int, int]:
    r = s = 0
    while True:
        c = b[p]
        p += 1
        r |= (c & 0x7F) << s
        if not c & 0x80:
            return r, p
        s += 7


def unsnappy(src: bytes) -> bytes:
    """Decompress a raw Snappy block."""
    ulen, p = _varint(src, 0)
    dst = bytearray()
    end = len(src)
    while p < end:
        tag = src[p]
        p += 1
        kind = tag & 3
        if kind == 0:  # literal
            ln = tag >> 2
            if ln >= 60:
                nb = ln - 59
                ln = int.from_bytes(src[p:p + nb], "little")
                p += nb
            ln += 1
            dst += src[p:p + ln]
            p += ln
            continue
        if kind == 1:
            ln = ((tag >> 2) & 7) + 4
            off = ((tag >> 5) << 8) | src[p]
            p += 1
        elif kind == 2:
            ln = (tag >> 2) + 1
            off = src[p] | (src[p + 1] << 8)
            p += 2
        else:
            ln = (tag >> 2) + 1
            off = int.from_bytes(src[p:p + 4], "little")
            p += 4
        start = len(dst) - off
        for i in range(ln):  # byte by byte: copies may overlap themselves
            dst.append(dst[start + i])
    return bytes(dst[:ulen])


def _block(f: bytes, off: int, size: int) -> bytes:
    data = f[off:off + size]
    return unsnappy(data) if f[off + size] == 1 else data


def _entries(b: bytes) -> List[Tuple[bytes, bytes]]:
    n = struct.unpack_from("<i", b, len(b) - 4)[0]
    end = len(b) - 4 - 4 * n
    out, p, key = [], 0, b""
    while p < end:
        shared, p = _varint(b, p)
        non, p = _varint(b, p)
        vl, p = _varint(b, p)
        key = key[:shared] + b[p:p + non]
        p += non
        out.append((key, b[p:p + vl]))
        p += vl
    return out


class _Store:
    def __init__(self, prefix: bytes):
        self.prefix = prefix
        self.items: Dict[bytes, Tuple[int, Optional[bytes]]] = {}

    def put(self, key: bytes, seq: int, deleted: bool, value: bytes):
        if not key.startswith(self.prefix):
            return
        old = self.items.get(key)
        if old and old[0] > seq:
            return
        self.items[key] = (seq, None if deleted else value)


def _read_table(f: bytes, st: _Store):
    p = len(f) - 48  # footer: metaindex handle, index handle, padding, magic
    _, p = _varint(f, p)
    _, p = _varint(f, p)
    io, p = _varint(f, p)
    isz, p = _varint(f, p)
    for _, handle in _entries(_block(f, io, isz)):
        try:
            bo, q = _varint(handle, 0)
            bs, q = _varint(handle, q)
            for k, v in _entries(_block(f, bo, bs)):
                if len(k) < 8:
                    continue
                tag = int.from_bytes(k[-8:], "little")
                st.put(k[:-8], tag >> 8, (tag & 0xFF) == 0, v)
        except Exception:
            pass


def _read_batch(r: bytes, st: _Store):
    if len(r) < 12:
        return
    seq, cnt = struct.unpack_from("<Qi", r, 0)
    p = 12
    for i in range(cnt):
        if p >= len(r):
            break
        t = r[p]
        p += 1
        kl, p = _varint(r, p)
        k = r[p:p + kl]
        p += kl
        v = b""
        if t == 1:
            vl, p = _varint(r, p)
            v = r[p:p + vl]
            p += vl
        st.put(k, seq + i, t == 0, v)


def _read_log(f: bytes, st: _Store):
    rec = bytearray()
    p = 0
    while p + 7 <= len(f):
        left = 32768 - (p % 32768)
        if left < 7:
            p += left
            continue
        ln = f[p + 4] | (f[p + 5] << 8)
        typ = f[p + 6]
        if typ == 0 and ln == 0:
            p += left
            continue
        p += 7
        if p + ln > len(f):
            break
        if typ in (1, 2):  # FULL or FIRST starts a record
            rec.clear()
        rec += f[p:p + ln]
        p += ln
        if typ in (1, 4):  # FULL or LAST ends it
            try:
                _read_batch(bytes(rec), st)
            except Exception:
                pass
            rec.clear()


def read_leveldb(directory: Path, prefix: str) -> Dict[str, str]:
    """Return {key: value} for live keys starting with `prefix`. Read-only."""
    st = _Store(prefix.encode("utf-8"))
    for f in sorted(Path(directory).iterdir()):
        ext = f.suffix.lower()
        if ext not in (".ldb", ".sst", ".log"):
            continue
        try:
            data = f.read_bytes()  # Python opens with sharing, so a running browser is fine
            if ext == ".log":
                _read_log(data, st)
            else:
                _read_table(data, st)
        except Exception:
            pass
    return {k.decode("utf-8", "replace"): v.decode("utf-8", "replace")
            for k, (_, v) in st.items.items() if v is not None}


# --------------------------------------------------------------- browsers ---

@dataclass
class ClaudeBrowser:
    claude_name: str
    browser: str
    profile: str
    profile_dir: str
    account: str
    device_id: str
    duplicate: bool = False

    @property
    def paste_line(self) -> str:
        return (f'Use the Claude in Chrome browser with deviceId {self.device_id} '
                f'("{self.claude_name}" - {self.browser} profile "{self.profile}")')

    @property
    def menu_text(self) -> str:
        warn = "   [!] duplicate ID" if self.duplicate else ""
        return f"{self.claude_name}  |  {self.browser}: {self.profile}  |  {self.device_id}{warn}"


def _unquote(v: Optional[str]) -> str:
    if not v:
        return ""
    try:
        return str(json.loads(v))
    except Exception:
        return v.strip('"')


def get_claude_browsers(roots: Optional[Dict[str, Path]] = None) -> List[ClaudeBrowser]:
    out: List[ClaudeBrowser] = []
    for browser, root in (roots or browser_roots()).items():
        if not root.is_dir():
            continue
        info = {}
        try:
            with open(root / "Local State", encoding="utf-8") as fh:
                info = json.load(fh).get("profile", {}).get("info_cache", {}) or {}
        except Exception:
            pass
        for d in sorted(root.iterdir()):
            store = d / "Local Extension Settings" / EXTENSION_ID
            if not store.is_dir():
                continue
            kv = read_leveldb(store, "bridge")
            if "bridgeDeviceId" not in kv:
                continue
            pi = info.get(d.name, {}) or {}
            name = _unquote(kv.get("bridgeDisplayName")) or _unquote(kv.get("bridgeDefaultDisplayName"))
            out.append(ClaudeBrowser(
                claude_name=name,
                browser=browser,
                profile=pi.get("name") or d.name,
                profile_dir=d.name,
                account=pi.get("user_name") or "",
                device_id=_unquote(kv["bridgeDeviceId"]),
            ))
    counts: Dict[str, int] = {}
    for b in out:
        counts[b.device_id] = counts.get(b.device_id, 0) + 1
    for b in out:
        b.duplicate = counts[b.device_id] > 1
    return sorted(out, key=lambda b: (b.browser, b.profile.lower()))
