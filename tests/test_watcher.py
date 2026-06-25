import json
import time
from pathlib import Path
from claudetray.data.watcher import StatuslineParser, StatuslineWatcher
from claudetray.data.models import AppState

SAMPLE_JSON = {
    "session_id": "317f713a-2b33-4b86-82d5-58392a51fef0",
    "cwd": "C:\\Projects\\ClaudeTray",
    "model": {"id": "claude-opus-4-6[1m]", "display_name": "Opus 4.6 (1M context)"},
    "workspace": {"current_dir": "C:\\Projects\\ClaudeTray"},
    "cost": {"total_cost_usd": 0.365, "total_duration_ms": 265896},
    "context_window": {
        "used_percentage": 4,
        "current_usage": {
            "input_tokens": 1,
            "output_tokens": 98,
            "cache_creation_input_tokens": 813,
            "cache_read_input_tokens": 34209,
        },
    },
    "rate_limits": {
        "five_hour": {"used_percentage": 41, "resets_at": 1782336600},
        "seven_day": {"used_percentage": 37, "resets_at": 1782367200},
    },
}


def test_parser_extracts_rate_limits():
    state, snapshot, session = StatuslineParser.parse(SAMPLE_JSON)
    assert state.five_hour_pct == 41
    assert state.seven_day_pct == 37
    assert state.context_pct == 4


def test_parser_extracts_session_info():
    state, snapshot, session = StatuslineParser.parse(SAMPLE_JSON)
    assert state.session_id == "317f713a-2b33-4b86-82d5-58392a51fef0"
    assert state.model == "Opus 4.6 (1M context)"
    assert state.project_dir == "C:\\Projects\\ClaudeTray"
    assert state.total_cost == 0.365


def test_parser_creates_snapshot():
    state, snapshot, session = StatuslineParser.parse(SAMPLE_JSON)
    assert snapshot.five_hour_pct == 41
    assert snapshot.seven_day_pct == 37
    assert snapshot.context_pct == 4


def test_parser_creates_session():
    state, snapshot, session = StatuslineParser.parse(SAMPLE_JSON)
    assert session is not None
    assert session.session_id == "317f713a-2b33-4b86-82d5-58392a51fef0"
    assert session.tokens_in == 34210  # input_tokens + cache_read
    assert session.tokens_out == 98


def test_parser_handles_missing_fields():
    minimal = {"rate_limits": {}, "context_window": {}}
    state, snapshot, session = StatuslineParser.parse(minimal)
    assert state.five_hour_pct == 0
    assert state.seven_day_pct == 0
    assert session is None


def test_parser_extracts_reset_times():
    state, snapshot, session = StatuslineParser.parse(SAMPLE_JSON)
    assert state.five_hour_resets_at == 1782336600
    assert state.seven_day_resets_at == 1782367200


def test_parser_extracts_duration():
    state, snapshot, session = StatuslineParser.parse(SAMPLE_JSON)
    assert state.total_duration_ms == 265896


def test_watcher_reads_file(tmp_path):
    json_file = tmp_path / "statusline_debug.json"
    json_file.write_text(json.dumps(SAMPLE_JSON))

    updates = []
    watcher = StatuslineWatcher(
        file_path=json_file,
        on_update=lambda s: updates.append(s),
    )
    watcher._read_file()
    assert len(updates) == 1
    assert updates[0].five_hour_pct == 41


def test_watcher_ignores_missing_file(tmp_path):
    json_file = tmp_path / "nonexistent.json"
    updates = []
    watcher = StatuslineWatcher(
        file_path=json_file,
        on_update=lambda s: updates.append(s),
    )
    watcher._read_file()
    assert len(updates) == 0
