# tests/unit/test_mt5_terminal_path.py
import src.services.mt5_service as mod


def test_terminal_path_resolved_from_config_not_env(monkeypatch):
    # Frozen scenario: no env var, but the settings store (via get_mt5_config)
    # supplies the terminal path. MT5Service must pick it up.
    monkeypatch.delenv("MT5_TERMINAL_PATH", raising=False)
    # Stub heavy collaborators so __init__ doesn't touch MT5 / DB / filesystem.
    monkeypatch.setattr(mod, "SymbolMapper", lambda *a, **k: object())
    monkeypatch.setattr(mod, "InstrumentManager", lambda *a, **k: object())
    monkeypatch.setattr(
        mod, "get_mt5_config",
        lambda: {"account": 1, "password": "x", "server": "s",
                 "terminal_path": r"C:\Fusion\terminal64.exe"},
    )
    svc = mod.MT5Service(account=1, password="x", server="s")
    assert svc.terminal_path == r"C:\Fusion\terminal64.exe"
