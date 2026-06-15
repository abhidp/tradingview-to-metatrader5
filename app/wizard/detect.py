"""Wizard detection helpers: MT5 terminals, MT5 test-connection, symbol suffix.

Heavy imports (the MetaTrader5 package, the engine's MT5 service) are done
lazily inside functions so importing this module — and therefore the API
server — stays cheap and these functions stay easy to mock in tests.
"""
import os
from typing import Optional


def detect_mt5_terminals() -> list:
    """Installed MT5 terminal paths (reuses the engine's discovery)."""
    from src.services.mt5_service import find_mt5_terminals
    return find_mt5_terminals()


def check_mt5_connection(account, password: str, server: str,
                         terminal_path: Optional[str] = None) -> dict:
    """Try to connect to MT5 with the given credentials.

    Returns {"ok": True, "account", "balance", "server", "currency"} or
    {"ok": False, "error": "..."}. Named check_* (not test_*) so pytest does
    not collect it when it is imported into a test module.
    """
    try:
        account = int(account)
    except (TypeError, ValueError):
        return {"ok": False, "error": "MT5 account must be a number."}

    import MetaTrader5 as mt5

    init_params = {"login": account, "password": password, "server": server}
    if terminal_path and os.path.exists(terminal_path):
        init_params["path"] = terminal_path
    try:
        if not mt5.initialize(**init_params):
            return {"ok": False, "error": f"Could not connect to MT5: {mt5.last_error()}"}
        if not mt5.login(account, password=password, server=server):
            return {"ok": False, "error": f"Login failed: {mt5.last_error()}"}
        info = mt5.account_info()
        if info is None:
            return {"ok": False, "error": "Connected, but could not read account info."}
        return {
            "ok": True, "account": info.login, "balance": info.balance,
            "server": info.server, "currency": info.currency,
        }
    except Exception as e:  # noqa: BLE001 - surfaced to the wizard banner
        return {"ok": False, "error": str(e)}
    finally:
        try:
            mt5.shutdown()
        except Exception:
            pass


def suggest_symbol_suffix() -> str:
    """Suggest a default broker symbol suffix.

    Prefers any suffix already stored; otherwise the common Fusion Markets ".r".
    """
    from app.storage.settings_store import SettingsStore
    existing = SettingsStore().get("symbols.default_suffix")
    return existing if existing else ".r"
