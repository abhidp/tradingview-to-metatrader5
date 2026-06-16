import json

from app.storage.settings_store import SettingsStore
import app.storage.profiles as profiles


def _data(name="Fusion"):
    return {
        "name": name,
        "mt5": {"terminal_path": r"C:\Fusion\terminal64.exe", "account": "384569",
                "server": "FusionMarketsAU-Demo", "password": "secret-pw"},
        "symbols": {"default_suffix": ".r", "map": {"USTEC": "NAS100"}},
    }


def test_create_stores_profile_and_secret_password(temp_db_path):
    s = SettingsStore()
    p = profiles.create_profile(_data(), store=s)
    assert p["id"] and p["name"] == "Fusion" and p["password_set"] is True
    raw_list = s.get("profiles.list")
    assert "secret-pw" not in raw_list
    assert s.get_secret(f"profiles.{p['id']}.password") == "secret-pw"


def test_list_redacts_passwords_and_flags_active(temp_db_path):
    s = SettingsStore()
    p = profiles.create_profile(_data(), store=s)
    profiles.activate_profile(p["id"], store=s)
    out = profiles.list_profiles(store=s)
    assert out["active"] == p["id"]
    assert out["profiles"][0]["password_set"] is True
    assert "password" not in out["profiles"][0]["mt5"]


def test_activate_copies_values_into_live_keys(temp_db_path):
    s = SettingsStore()
    p = profiles.create_profile(_data(), store=s)
    profiles.activate_profile(p["id"], store=s)
    assert s.get("mt5.terminal_path") == r"C:\Fusion\terminal64.exe"
    assert s.get("mt5.account") == "384569"
    assert s.get("mt5.server") == "FusionMarketsAU-Demo"
    assert s.get_secret("mt5.password") == "secret-pw"
    assert s.get("symbols.default_suffix") == ".r"
    assert json.loads(s.get("symbols.map")) == {"USTEC": "NAS100"}
    assert s.get("profiles.active") == p["id"]


def test_update_and_delete(temp_db_path):
    s = SettingsStore()
    p = profiles.create_profile(_data(), store=s)
    profiles.update_profile(p["id"], {"name": "Renamed"}, store=s)
    assert profiles.list_profiles(store=s)["profiles"][0]["name"] == "Renamed"
    profiles.delete_profile(p["id"], store=s)
    assert profiles.list_profiles(store=s)["profiles"] == []
    assert s.get_secret(f"profiles.{p['id']}.password") is None


def test_activate_unknown_raises(temp_db_path):
    s = SettingsStore()
    try:
        profiles.activate_profile("nope", store=s)
        assert False, "expected KeyError"
    except KeyError:
        pass
