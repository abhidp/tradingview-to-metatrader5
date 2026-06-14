import pytest

from app.api.config_api import (SettingsValidationError, get_settings,
                                update_settings)
from app.storage.settings_store import SettingsStore


def test_get_settings_redacts_password_and_marks_set(temp_db_path):
    s = SettingsStore()
    s.set("mt5.account", "123456")
    s.set("mt5.server", "Demo")
    s.set("mt5.terminal_path", "C:/t.exe")
    s.set_secret("mt5.password", "hunter2")
    s.set("tv.broker_url", "broker.example.com")
    s.set("tv.account_id", "999")

    out = get_settings()
    assert out["mt5"]["account"] == 123456
    assert out["mt5"]["server"] == "Demo"
    assert out["mt5"]["terminal_path"] == "C:/t.exe"
    assert out["mt5"]["password_set"] is True
    assert out["tv"] == {"broker_url": "broker.example.com", "account_id": "999"}
    import json
    assert "hunter2" not in json.dumps(out)
    assert out["mt5"].get("password") is None


def test_update_settings_writes_mt5_fields(temp_db_path):
    update_settings({"mt5": {"account": "555", "server": "Live", "terminal_path": "C:/x.exe"}})
    s = SettingsStore()
    assert s.get_int("mt5.account") == 555
    assert s.get("mt5.server") == "Live"
    assert s.get("mt5.terminal_path") == "C:/x.exe"


def test_update_settings_password_only_when_provided(temp_db_path):
    s = SettingsStore()
    s.set_secret("mt5.password", "original")
    update_settings({"mt5": {"server": "X"}})
    assert s.get_secret("mt5.password") == "original"
    update_settings({"mt5": {"password": ""}})
    assert s.get_secret("mt5.password") == "original"
    update_settings({"mt5": {"password": "newpw"}})
    assert s.get_secret("mt5.password") == "newpw"


def test_update_settings_rejects_non_integer_account(temp_db_path):
    with pytest.raises(SettingsValidationError):
        update_settings({"mt5": {"account": "abc"}})


def test_update_settings_ignores_tv_target(temp_db_path):
    update_settings({"tv": {"broker_url": "evil", "account_id": "0"}, "mt5": {"server": "S"}})
    s = SettingsStore()
    assert s.get("tv.broker_url") is None
