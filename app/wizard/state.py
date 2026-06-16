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
    from app.storage import profiles
    s = store or SettingsStore()
    set_onboarding_complete(True, store=s)
    if profiles.list_profiles(store=s)["profiles"]:
        return
    try:
        # Read live config from the SAME injected store (not config_accessors,
        # which would construct its own SettingsStore and ignore `store`).
        created = profiles.create_profile({
            "name": "Default",
            "mt5": {"terminal_path": s.get("mt5.terminal_path") or "",
                    "account": s.get("mt5.account") or "",
                    "server": s.get("mt5.server") or "",
                    "password": s.get_secret("mt5.password") or ""},
            "symbols": {"default_suffix": s.get("symbols.default_suffix") or "",
                        "map": s.get_json("symbols.map", {}) or {}},
        }, store=s)
        profiles.activate_profile(created["id"], store=s)
    except Exception:
        logger.exception("Failed to seed Default broker profile on onboarding completion")
