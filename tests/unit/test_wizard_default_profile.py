import app.wizard.state as state
import app.storage.profiles as profiles


def test_complete_creates_default_profile_when_none(temp_db_path):
    from app.storage.settings_store import SettingsStore
    s = SettingsStore()
    s.set("mt5.account", "111"); s.set("mt5.server", "Srv")
    s.set("mt5.terminal_path", "C:/t.exe"); s.set("symbols.default_suffix", ".r")

    state.complete_onboarding()  # the new helper called by the API route

    out = profiles.list_profiles(store=s)
    assert len(out["profiles"]) == 1
    assert out["profiles"][0]["name"] == "Default"
    assert out["active"] == out["profiles"][0]["id"]


def test_complete_does_not_duplicate_default(temp_db_path):
    from app.storage.settings_store import SettingsStore
    s = SettingsStore()
    profiles.create_profile({"name": "Existing", "mt5": {}, "symbols": {}}, store=s)
    state.complete_onboarding()
    assert len(profiles.list_profiles(store=s)["profiles"]) == 1  # no Default added
