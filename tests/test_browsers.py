"""Tests for the read-only LevelDB reader behind browser identification."""
import json
import struct

from claudetray.browsers import EXTENSION_ID, get_claude_browsers, read_leveldb, unsnappy


def _varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _batch(seq, ops):
    """ops: list of (key, value-or-None)."""
    body = bytearray(struct.pack("<Qi", seq, len(ops)))
    for k, v in ops:
        k = k.encode()
        if v is None:
            body += b"\x00" + _varint(len(k)) + k
        else:
            v = v.encode()
            body += b"\x01" + _varint(len(k)) + k + _varint(len(v)) + v
    return bytes(body)


def _log(*batches):
    out = bytearray()
    for b in batches:  # one FULL record per batch; the reader ignores the CRC
        out += b"\x00\x00\x00\x00" + struct.pack("<H", len(b)) + b"\x01" + b
    return bytes(out)


def test_unsnappy_literal_and_overlapping_copy():
    # "abcd" literal, then copy offset 4 length 8 (overlaps itself) -> "abcdabcdabcd"
    src = _varint(12) + bytes([(4 - 1) << 2]) + b"abcd" + bytes([((8 - 4) << 2) | 1, 4])
    assert unsnappy(src) == b"abcdabcdabcd"


def test_log_reader_keeps_latest_and_honours_deletes(tmp_path):
    (tmp_path / "000003.log").write_bytes(_log(
        _batch(1, [("bridgeDeviceId", '"old"'), ("bridgeX", '"gone"'), ("other", '"skip"')]),
        _batch(5, [("bridgeDeviceId", '"new"'), ("bridgeX", None)]),
    ))
    assert read_leveldb(tmp_path, "bridge") == {"bridgeDeviceId": '"new"'}


def test_finds_profiles_and_flags_duplicate_ids(tmp_path):
    root = tmp_path / "Chrome"
    for prof, dev, name in (("Default", "id-1", "Personal"), ("Profile 2", "id-1", ""), ("Profile 3", "id-3", "Work")):
        store = root / prof / "Local Extension Settings" / EXTENSION_ID
        store.mkdir(parents=True)
        ops = [("bridgeDeviceId", json.dumps(dev)), ("bridgeDefaultDisplayName", '"SLAB"')]
        if name:
            ops.append(("bridgeDisplayName", json.dumps(name)))
        (store / "000003.log").write_bytes(_log(_batch(1, ops)))
    (root / "Local State").write_text(json.dumps({"profile": {"info_cache": {
        "Default": {"name": "Me", "user_name": "me@example.com"}, "Profile 3": {"name": "Job"}}}}))
    (root / "Profile 9").mkdir()  # no extension: skipped

    found = get_claude_browsers({"Chrome": root})
    assert [(b.claude_name, b.profile, b.device_id, b.duplicate) for b in found] == [
        ("Work", "Job", "id-3", False),
        ("Personal", "Me", "id-1", True),
        ("SLAB", "Profile 2", "id-1", True),
    ]
    assert found[1].paste_line == 'Use the Claude in Chrome browser with deviceId id-1 ("Personal" - Chrome profile "Me")'
