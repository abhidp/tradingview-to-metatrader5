"""Onboarding wizard state: the first-run completion flag + resume step.

Stored in the SQLite settings store alongside the rest of the app config.
Step data itself (MT5 creds, symbols, TV target) is persisted through the
existing config accessors as each step completes; this module only tracks
*whether* onboarding is done and *where* the user left off.
"""
import logging
from typing import Optional

from app.storage.settings_store import SettingsStore

logger = logging.getLogger("wizard.state")

ONBOARDING_COMPLETE_KEY = "onboarding.complete"
ONBOARDING_STEP_KEY = "onboarding.step"


def is_onboarding_complete(store: Optional[SettingsStore] = None) -> bool:
    s = store or SettingsStore()
    return s.get_bool(ONBOARDING_COMPLETE_KEY, False)


def set_onboarding_complete(value: bool = True, store: Optional[SettingsStore] = None) -> None:
    s = store or SettingsStore()
    s.set(ONBOARDING_COMPLETE_KEY, "1" if value else "0")


def get_step(store: Optional[SettingsStore] = None) -> int:
    s = store or SettingsStore()
    return s.get_int(ONBOARDING_STEP_KEY, 1)


def set_step(step: int, store: Optional[SettingsStore] = None) -> None:
    s = store or SettingsStore()
    s.set(ONBOARDING_STEP_KEY, str(int(step)))


def complete_onboarding(store: Optional[SettingsStore] = None) -> None:
    """Mark onboarding complete and seed a 'Default' broker profile if none exist.

    Onboarding completion is the contract; Default-profile seeding is best-effort —
    a seeding failure is logged but does not fail completion.
    """
    from app.config_accessors import get_mt5_config, get_symbol_settings
    from app.storage import profiles
    s = store or SettingsStore()
    set_onboarding_complete(True, store=s)
    if profiles.list_profiles(store=s)["profiles"]:
        return
    try:
        cfg = get_mt5_config()
        suffix, mapping = get_symbol_settings()
        created = profiles.create_profile({
            "name": "Default",
            "mt5": {"terminal_path": cfg.get("terminal_path") or "",
                    "account": cfg.get("account") or "",
                    "server": cfg.get("server") or "",
                    "password": cfg.get("password") or ""},
            "symbols": {"default_suffix": suffix or "", "map": mapping or {}},
        }, store=s)
        profiles.activate_profile(created["id"], store=s)
    except Exception:
        logger.exception("Failed to seed Default broker profile on onboarding completion")
