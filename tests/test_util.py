from claudetray.util import format_reset_countdown


def test_no_reset_time():
    assert format_reset_countdown(None) == ""
    assert format_reset_countdown(0) == ""


def test_already_passed():
    assert format_reset_countdown(100, now=200) == "now"
    assert format_reset_countdown(100, now=100) == "now"


def test_minutes_only():
    assert format_reset_countdown(100 + 15 * 60, now=100) == "15m"


def test_hours_and_minutes():
    assert format_reset_countdown(100 + 2 * 3600 + 15 * 60, now=100) == "2h 15m"


def test_days_and_hours():
    assert format_reset_countdown(100 + 3 * 86400 + 2 * 3600, now=100) == "3d 2h"
