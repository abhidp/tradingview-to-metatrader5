"""Broker profiles: named MT5-connection + symbols presets in the settings store.

A profile is saved config. Activating it COPIES its values into the live keys the
engine already reads (mt5.*, symbols.*) — so the engine needs no knowledge of
profiles. Passwords are stored via the store's secret mechanism, never in the
plaintext profiles.list JSON.
"""
import json
import uuid
from typing import Optional

from app.storage.settings_store import SettingsStore

LIST_KEY = "profiles.list"
ACTIVE_KEY = "profiles.active"


class DuplicateProfileError(ValueError):
    """Raised when a profile would duplicate an existing name or broker account."""


def _pw_key(pid: str) -> str:
    return f"profiles.{pid}.password"


def _load(store: SettingsStore) -> list:
    return store.get_json(LIST_KEY, []) or []


def _save(store: SettingsStore, items: list) -> None:
    store.set(LIST_KEY, json.dumps(items))


def _shape(data: dict) -> dict:
    mt5 = data.get("mt5") or {}
    sym = data.get("symbols") or {}
    return {
        "name": data.get("name") or "Unnamed",
        "mt5": {
            "terminal_path": mt5.get("terminal_path", "") or "",
            "account": str(mt5.get("account", "") or ""),
            "server": mt5.get("server", "") or "",
        },
        "symbols": {
            "default_suffix": sym.get("default_suffix", "") or "",
            "map": sym.get("map", {}) or {},
        },
    }


def _assert_unique(items: list, profile: dict, exclude_id: Optional[str] = None) -> None:
    """Enforce unique profile name and one profile per (account, server).

    Uses defensive .get lookups so a hand-edited/garbled stored row yields a
    clean DuplicateProfileError path rather than a KeyError 500.
    """
    name = (profile.get("name") or "").strip().lower()
    acct = str((profile.get("mt5") or {}).get("account") or "").strip()
    srv = str((profile.get("mt5") or {}).get("server") or "").strip().lower()
    for p in items:
        if exclude_id is not None and p.get("id") == exclude_id:
            continue
        pm = p.get("mt5") or {}
        if (p.get("name") or "").strip().lower() == name:
            raise DuplicateProfileError(f"A profile named '{profile.get('name')}' already exists.")
        if acct and str(pm.get("account") or "").strip() == acct \
                and str(pm.get("server") or "").strip().lower() == srv:
            raise DuplicateProfileError("A profile for this broker account already exists.")


def list_profiles(store: Optional[SettingsStore] = None) -> dict:
    store = store or SettingsStore()
    items = _load(store)
    # One bulk read instead of a get_secret() round-trip per profile.
    rows = store.all(redact_secrets=False)
    out = [{**p, "password_set": bool(rows.get(_pw_key(p["id"])))} for p in items]
    return {"profiles": out, "active": rows.get(ACTIVE_KEY) or ""}


def create_profile(data: dict, store: Optional[SettingsStore] = None) -> dict:
    store = store or SettingsStore()
    items = _load(store)
    profile = {"id": uuid.uuid4().hex[:8], **_shape(data)}
    _assert_unique(items, profile)
    pid = profile["id"]
    password = (data.get("mt5") or {}).get("password")
    if password:
        store.set_secret(_pw_key(pid), password)
    items.append(profile)
    _save(store, items)
    return {**profile, "password_set": bool(password)}


def update_profile(pid: str, data: dict, store: Optional[SettingsStore] = None) -> dict:
    store = store or SettingsStore()
    items = _load(store)
    for i, p in enumerate(items):
        if p["id"] == pid:
            shaped = _shape({**p, **data,
                             "mt5": {**p["mt5"], **(data.get("mt5") or {})},
                             "symbols": {**p["symbols"], **(data.get("symbols") or {})}})
            merged = {"id": pid, **shaped}
            # Same uniqueness invariant create_profile enforces, ignoring self.
            _assert_unique(items, merged, exclude_id=pid)
            items[i] = merged
            password = (data.get("mt5") or {}).get("password")
            if password:
                store.set_secret(_pw_key(pid), password)
            _save(store, items)
            return {**merged, "password_set": bool(store.get_secret(_pw_key(pid)))}
    raise KeyError(pid)


def delete_profile(pid: str, store: Optional[SettingsStore] = None) -> None:
    store = store or SettingsStore()
    items = [p for p in _load(store) if p["id"] != pid]
    _save(store, items)
    store.delete(_pw_key(pid))
    if store.get(ACTIVE_KEY) == pid:
        store.delete(ACTIVE_KEY)
        # The deleted profile was active — clear the live broker credential too so
        # the deleted account's password isn't left as the engine's live secret.
        store.delete("mt5.password")


def activate_profile(pid: str, store: Optional[SettingsStore] = None) -> dict:
    """Copy the profile's values into the live config keys and mark it active."""
    store = store or SettingsStore()
    profile = next((p for p in _load(store) if p["id"] == pid), None)
    if profile is None:
        raise KeyError(pid)
    mt5, sym = profile["mt5"], profile["symbols"]
    store.set("mt5.terminal_path", mt5.get("terminal_path", ""))
    store.set("mt5.account", mt5.get("account", ""))
    store.set("mt5.server", mt5.get("server", ""))
    pw = store.get_secret(_pw_key(pid))
    if pw:
        store.set_secret("mt5.password", pw)
    # Only apply symbol settings the profile actually carries — never clobber the
    # live suffix/map with empties, which would break symbol resolution (e.g. a
    # broker that needs a ".r" suffix). Profiles that DO carry them still switch.
    suffix = sym.get("default_suffix") or ""
    if suffix:
        store.set("symbols.default_suffix", suffix)
    sym_map = sym.get("map") or {}
    if sym_map:
        store.set("symbols.map", json.dumps(sym_map))
    store.set(ACTIVE_KEY, pid)
    return profile
