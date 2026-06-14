"""Read/write helpers for the Settings and Symbols tabs (Plan 3b).

All values live in the SQLite settings store. The TV target (broker_url/
account_id) is auto-detected from live traffic, so it is exposed read-only here.
The MT5 password is never returned; it is updated only when a new value is given.
"""
import json

from app.storage.settings_store import SettingsStore


class SettingsValidationError(ValueError):
    """Raised on invalid settings/symbols input (maps to HTTP 400)."""


def get_settings() -> dict:
    s = SettingsStore()
    return {
        "mt5": {
            "account": s.get_int("mt5.account"),
            "server": s.get("mt5.server"),
            "terminal_path": s.get("mt5.terminal_path"),
            "password_set": bool(s.get("mt5.password")),
        },
        "tv": {  # read-only — auto-detected from live traffic
            "broker_url": s.get("tv.broker_url"),
            "account_id": s.get("tv.account_id"),
        },
    }


def update_settings(data: dict) -> None:
    """Apply editable MT5 settings. Ignores the (read-only) TV target.

    Password is updated only when a non-empty value is supplied (blank = keep).
    Raises SettingsValidationError on invalid input.
    """
    s = SettingsStore()
    mt5 = data.get("mt5", {}) or {}

    if "account" in mt5 and mt5["account"] not in (None, ""):
        try:
            account = int(mt5["account"])
        except (TypeError, ValueError):
            raise SettingsValidationError("MT5 account must be an integer")
        s.set("mt5.account", str(account))

    if mt5.get("server") is not None:
        s.set("mt5.server", mt5["server"])

    if mt5.get("terminal_path") is not None:
        s.set("mt5.terminal_path", mt5["terminal_path"])

    password = mt5.get("password")
    if password:
        s.set_secret("mt5.password", password)


def get_symbols() -> dict:
    s = SettingsStore()
    suffix = s.get("symbols.default_suffix")
    mapping = s.get_json("symbols.map", {}) or {}
    return {"default_suffix": suffix if suffix is not None else "", "map": mapping}


def update_symbols(data: dict) -> None:
    """Write the default suffix + the TV->MT5 symbol map. Raises on a bad map."""
    s = SettingsStore()
    mapping = data.get("map", {})
    if not isinstance(mapping, dict):
        raise SettingsValidationError("Symbol map must be an object of TV->MT5 pairs")
    clean = {str(k): str(v) for k, v in mapping.items()}
    s.set("symbols.default_suffix", data.get("default_suffix", "") or "")
    s.set("symbols.map", json.dumps(clean))
