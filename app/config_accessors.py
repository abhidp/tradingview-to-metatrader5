"""Store-backed configuration accessors (replace import-time os.getenv reads).

The SettingsStore is the source of truth. os.getenv is consulted only when the
store has no value for a key (pre-seed or in tests); after seed_from_env_once
the store holds every key, so the fallback never fires.
"""
import json
import os
from typing import Optional, Tuple

from app.storage.settings_store import SettingsStore


def _store() -> SettingsStore:
    return SettingsStore()


def get_mt5_config() -> dict:
    """Return MT5 connection config: account, password, server, terminal_path."""
    s = _store()
    account = s.get_int("mt5.account")
    if account is None:
        env_account = os.getenv("MT5_ACCOUNT")
        if env_account:
            account = int(env_account)
    password = s.get_secret("mt5.password")
    server = s.get("mt5.server")
    terminal_path = s.get("mt5.terminal_path")
    return {
        "account": account,
        "password": password if password is not None else os.getenv("MT5_PASSWORD"),
        "server": server if server is not None else os.getenv("MT5_SERVER"),
        "terminal_path": terminal_path if terminal_path is not None else os.getenv("MT5_TERMINAL_PATH"),
    }


def get_tv_target() -> Tuple[Optional[str], Optional[str]]:
    """Return (broker_url, account_id) for the TradingView broker panel."""
    s = _store()
    broker = s.get("tv.broker_url")
    account = s.get("tv.account_id")
    return (
        broker if broker is not None else os.getenv("TV_BROKER_URL"),
        account if account is not None else os.getenv("TV_ACCOUNT_ID"),
    )


def get_symbol_settings() -> Tuple[str, dict]:
    """Return (default_suffix, symbol_map)."""
    s = _store()
    suffix = s.get("symbols.default_suffix")
    if suffix is None:
        suffix = os.getenv("MT5_DEFAULT_SUFFIX", ".a")
    raw_map = s.get("symbols.map")
    if raw_map is None:
        raw_map = os.getenv("MT5_SYMBOL_MAP", "{}")
    try:
        mapping = json.loads(raw_map)
    except (ValueError, TypeError):
        mapping = {}
    return suffix, mapping
