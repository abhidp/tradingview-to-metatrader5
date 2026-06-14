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
    if account is None and os.getenv("MT5_ACCOUNT"):
        account = int(os.getenv("MT5_ACCOUNT"))
    return {
        "account": account,
        "password": s.get_secret("mt5.password") or os.getenv("MT5_PASSWORD"),
        "server": s.get("mt5.server") or os.getenv("MT5_SERVER"),
        "terminal_path": s.get("mt5.terminal_path") or os.getenv("MT5_TERMINAL_PATH"),
    }


def get_tv_target() -> Tuple[Optional[str], Optional[str]]:
    """Return (broker_url, account_id) for the TradingView broker panel."""
    s = _store()
    broker = s.get("tv.broker_url") or os.getenv("TV_BROKER_URL")
    account = s.get("tv.account_id") or os.getenv("TV_ACCOUNT_ID")
    return broker, account


def get_symbol_settings() -> Tuple[str, dict]:
    """Return (default_suffix, symbol_map)."""
    s = _store()
    suffix = s.get("symbols.default_suffix") or os.getenv("MT5_DEFAULT_SUFFIX", ".a")
    raw_map = s.get("symbols.map")
    if raw_map is None:
        raw_map = os.getenv("MT5_SYMBOL_MAP", "{}")
    try:
        mapping = json.loads(raw_map)
    except (ValueError, TypeError):
        mapping = {}
    return suffix, mapping
