import MetaTrader5  # imported so monkeypatch targets resolve

from app.wizard import detect


def test_detect_mt5_terminals_reuses_finder(monkeypatch):
    monkeypatch.setattr(
        "src.services.mt5_service.find_mt5_terminals",
        lambda: ["C:/x/terminal64.exe"],
    )
    assert detect.detect_mt5_terminals() == ["C:/x/terminal64.exe"]


def test_suggest_suffix_default(temp_db_path):
    assert detect.suggest_symbol_suffix() == ".r"


def test_suggest_suffix_uses_stored(temp_db_path):
    from app.storage.settings_store import SettingsStore
    SettingsStore().set("symbols.default_suffix", ".pro")
    assert detect.suggest_symbol_suffix() == ".pro"


class _Acct:
    login = 12345
    balance = 1000.0
    server = "Demo"
    currency = "USD"


def test_check_mt5_connection_success(monkeypatch):
    monkeypatch.setattr(MetaTrader5, "initialize", lambda **k: True)
    monkeypatch.setattr(MetaTrader5, "login", lambda *a, **k: True)
    monkeypatch.setattr(MetaTrader5, "account_info", lambda: _Acct())
    monkeypatch.setattr(MetaTrader5, "shutdown", lambda: None)
    r = detect.check_mt5_connection("12345", "pw", "Demo")
    assert r == {
        "ok": True, "account": 12345, "balance": 1000.0,
        "server": "Demo", "currency": "USD",
    }


def test_check_mt5_connection_init_fails(monkeypatch):
    monkeypatch.setattr(MetaTrader5, "initialize", lambda **k: False)
    monkeypatch.setattr(MetaTrader5, "last_error", lambda: (1, "no terminal"))
    monkeypatch.setattr(MetaTrader5, "shutdown", lambda: None)
    r = detect.check_mt5_connection("12345", "pw", "Demo")
    assert r["ok"] is False
    assert "Could not connect" in r["error"]


def test_check_mt5_connection_bad_account():
    r = detect.check_mt5_connection("abc", "pw", "Demo")
    assert r["ok"] is False
    assert "number" in r["error"]
