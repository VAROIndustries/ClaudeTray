import sys
import winreg
import pytest
from claudetray import startup

TEST_KEY = r"Software\ClaudeTrayTest\Run"


@pytest.fixture
def test_key():
    yield TEST_KEY
    for key in (TEST_KEY, r"Software\ClaudeTrayTest"):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
        except OSError:
            pass


def test_enable_registers_command(test_key):
    startup.set_run_on_startup(True, key_path=test_key)
    assert startup.is_registered(key_path=test_key)
    assert sys.executable in startup.get_registered_command(key_path=test_key)


def test_disable_removes_entry(test_key):
    startup.set_run_on_startup(True, key_path=test_key)
    startup.set_run_on_startup(False, key_path=test_key)
    assert not startup.is_registered(key_path=test_key)


def test_disable_when_not_registered_is_noop(test_key):
    startup.set_run_on_startup(False, key_path=test_key)  # must not raise
    assert not startup.is_registered(key_path=test_key)


def test_enable_removes_legacy_shortcut(test_key, tmp_path):
    legacy = tmp_path / "ClaudeTray.lnk"
    legacy.write_text("stub")
    startup.set_run_on_startup(True, key_path=test_key, legacy_dir=tmp_path)
    assert not legacy.exists()


def test_disable_removes_legacy_shortcut(test_key, tmp_path):
    legacy = tmp_path / "ClaudeTray.lnk"
    legacy.write_text("stub")
    startup.set_run_on_startup(False, key_path=test_key, legacy_dir=tmp_path)
    assert not legacy.exists()
