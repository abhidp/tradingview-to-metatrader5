from app.config_accessors import (get_mt5_config, get_symbol_settings,
                                   get_tv_target)
from app.storage.settings_store import SettingsStore


def test_get_mt5_config_prefers_store(temp_db_path, monkeypatch):
    monkeypatch.delenv("MT5_ACCOUNT", raising=False)
    store = SettingsStore()
    store.set("mt5.account", "555")
    store.set_secret("mt5.password", "pw")
    store.set("mt5.server", "Demo")
    store.set("mt5.terminal_path", "C:/t.exe")

    cfg = get_mt5_config()
    assert cfg["account"] == 555
    assert cfg["password"] == "pw"
    assert cfg["server"] == "Demo"
    assert cfg["terminal_path"] == "C:/t.exe"


def test_get_mt5_config_falls_back_to_env_pre_seed(temp_db_path, monkeypatch):
    monkeypatch.setenv("MT5_ACCOUNT", "777")
    monkeypatch.setenv("MT5_PASSWORD", "envpw")
    monkeypatch.setenv("MT5_SERVER", "EnvServer")
    cfg = get_mt5_config()
    assert cfg["account"] == 777
    assert cfg["password"] == "envpw"
    assert cfg["server"] == "EnvServer"


def test_get_tv_target_from_store(temp_db_path, monkeypatch):
    monkeypatch.delenv("TV_BROKER_URL", raising=False)
    monkeypatch.delenv("TV_ACCOUNT_ID", raising=False)
    store = SettingsStore()
    store.set("tv.broker_url", "broker.example.com")
    store.set("tv.account_id", "999")
    assert get_tv_target() == ("broker.example.com", "999")


def test_get_symbol_settings_defaults(temp_db_path, monkeypatch):
    monkeypatch.delenv("MT5_DEFAULT_SUFFIX", raising=False)
    monkeypatch.delenv("MT5_SYMBOL_MAP", raising=False)
    suffix, mapping = get_symbol_settings()
    assert suffix == ".a"
    assert mapping == {}
