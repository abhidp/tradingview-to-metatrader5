from app.storage.settings_store import SettingsStore


def test_delete_removes_key(temp_db_path):
    s = SettingsStore()
    s.set("foo", "bar")
    assert s.get("foo") == "bar"
    s.delete("foo")
    assert s.get("foo") is None
    s.delete("foo")  # idempotent — no error on missing key
