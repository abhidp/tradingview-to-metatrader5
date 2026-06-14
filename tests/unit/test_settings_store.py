import json

from app.storage.settings_store import SettingsStore


def test_set_and_get_roundtrip(temp_db_path):
    store = SettingsStore()
    store.set("tv.broker_url", "broker.example.com")
    assert store.get("tv.broker_url") == "broker.example.com"


def test_get_returns_default_when_missing(temp_db_path):
    store = SettingsStore()
    assert store.get("nope", "fallback") == "fallback"


def test_get_int_parses_value(temp_db_path):
    store = SettingsStore()
    store.set("mt5.account", "123456")
    assert store.get_int("mt5.account") == 123456
    assert store.get_int("missing", 7) == 7


def test_get_bool_reads_one_zero(temp_db_path):
    store = SettingsStore()
    store.set("meta.seeded", "1")
    assert store.get_bool("meta.seeded") is True
    assert store.get_bool("absent") is False


def test_get_json_parses_and_falls_back(temp_db_path):
    store = SettingsStore()
    store.set("symbols.map", json.dumps({"BTCUSD": "BTCUSD.r"}))
    assert store.get_json("symbols.map") == {"BTCUSD": "BTCUSD.r"}
    store.set("symbols.bad", "{not json")
    assert store.get_json("symbols.bad", {}) == {}


def test_secret_roundtrip_uses_secret_box(temp_db_path):
    store = SettingsStore()
    store.set_secret("mt5.password", "hunter2")
    # Stored form is prefixed (plaintext box); reader returns plaintext.
    assert store.get("mt5.password") == "plain:hunter2"
    assert store.get_secret("mt5.password") == "hunter2"


def test_all_redacts_secret_keys(temp_db_path):
    store = SettingsStore()
    store.set("mt5.server", "Demo")
    store.set_secret("mt5.password", "hunter2")
    dumped = store.all(redact_secrets=True)
    assert dumped["mt5.server"] == "Demo"
    assert dumped["mt5.password"] == "***"


def test_get_int_falls_back_on_non_integer(temp_db_path):
    store = SettingsStore()
    store.set("mt5.account", "notanumber")
    assert store.get_int("mt5.account", 0) == 0


def test_seed_from_env_once_imports_keys(temp_db_path, monkeypatch):
    monkeypatch.setenv("TV_BROKER_URL", "broker.example.com")
    monkeypatch.setenv("TV_ACCOUNT_ID", "999")
    monkeypatch.setenv("MT5_ACCOUNT", "123456")
    monkeypatch.setenv("MT5_PASSWORD", "hunter2")
    monkeypatch.setenv("MT5_SERVER", "Demo-Server")
    monkeypatch.setenv("MT5_TERMINAL_PATH", "C:/mt5/terminal64.exe")
    monkeypatch.setenv("MT5_DEFAULT_SUFFIX", ".r")
    monkeypatch.setenv("MT5_SYMBOL_MAP", '{"BTCUSD": "BTCUSD.r"}')

    store = SettingsStore()
    seeded = store.seed_from_env_once()

    assert seeded is True
    assert store.get("tv.broker_url") == "broker.example.com"
    assert store.get("tv.account_id") == "999"
    assert store.get_int("mt5.account") == 123456
    assert store.get_secret("mt5.password") == "hunter2"
    assert store.get("symbols.default_suffix") == ".r"
    assert store.get_json("symbols.map") == {"BTCUSD": "BTCUSD.r"}
    assert store.get_bool("meta.seeded") is True


def test_seed_from_env_once_is_idempotent(temp_db_path, monkeypatch):
    monkeypatch.setenv("MT5_SERVER", "First")
    store = SettingsStore()
    assert store.seed_from_env_once() is True

    # A later run with a different env must NOT clobber stored/edited values.
    monkeypatch.setenv("MT5_SERVER", "Second")
    assert store.seed_from_env_once() is False
    assert store.get("mt5.server") == "First"
