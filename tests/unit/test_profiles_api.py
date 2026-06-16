from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.profiles_api as papi


class FakeController:
    def __init__(self, running):
        self._running = running
        self.applied = False

    def status(self):
        class S:
            def to_dict(self_inner):
                return {"engine": "running" if self._running else "stopped"}
        return S()

    async def apply_mt5_settings(self):
        self.applied = True


def _client(controller, monkeypatch, store):
    monkeypatch.setattr(papi.profiles, "SettingsStore", lambda: store)
    app = FastAPI()
    papi.add_profile_routes(app, controller)
    return TestClient(app)


def test_create_list_activate_applies_when_running(temp_db_path, monkeypatch):
    from app.storage.settings_store import SettingsStore
    store = SettingsStore()

    ctrl = FakeController(running=True)
    c = _client(ctrl, monkeypatch, store)

    r = c.post("/api/profiles", json={"name": "A", "mt5": {"account": "1", "server": "S",
               "password": "pw", "terminal_path": "C:/t.exe"}, "symbols": {"default_suffix": ".r"}})
    assert r.status_code == 200
    pid = r.json()["id"]

    assert c.get("/api/profiles").json()["profiles"][0]["name"] == "A"

    r = c.post(f"/api/profiles/{pid}/activate")
    assert r.status_code == 200
    # activation reconnects MT5 in place (no proxy restart)
    assert ctrl.applied is True
    assert c.get("/api/profiles").json()["active"] == pid


def test_activate_unknown_404(temp_db_path, monkeypatch):
    from app.storage.settings_store import SettingsStore
    store = SettingsStore()
    ctrl = FakeController(running=False)
    c = _client(ctrl, monkeypatch, store)
    assert c.post("/api/profiles/nope/activate").status_code == 404


def test_update_and_update_unknown_404(temp_db_path, monkeypatch):
    from app.storage.settings_store import SettingsStore
    store = SettingsStore()
    ctrl = FakeController(running=False)
    c = _client(ctrl, monkeypatch, store)

    pid = c.post("/api/profiles", json={"name": "A", "mt5": {"account": "1", "server": "S",
                 "terminal_path": "C:/t.exe"}, "symbols": {}}).json()["id"]

    r = c.put(f"/api/profiles/{pid}", json={"name": "Renamed"})
    assert r.status_code == 200
    assert c.get("/api/profiles").json()["profiles"][0]["name"] == "Renamed"

    assert c.put("/api/profiles/nope", json={"name": "X"}).status_code == 404


def test_activate_does_not_apply_when_engine_stopped(temp_db_path, monkeypatch):
    from app.storage.settings_store import SettingsStore
    store = SettingsStore()
    ctrl = FakeController(running=False)
    c = _client(ctrl, monkeypatch, store)
    pid = c.post("/api/profiles", json={"name": "A", "mt5": {"account": "1", "server": "S",
                 "terminal_path": "C:/t.exe"}, "symbols": {}}).json()["id"]
    # apply_mt5_settings is still called; the controller decides it's a no-op when
    # stopped. The route must succeed and mark the profile active regardless.
    assert c.post(f"/api/profiles/{pid}/activate").status_code == 200
    assert c.get("/api/profiles").json()["active"] == pid


def test_create_duplicate_returns_409(temp_db_path, monkeypatch):
    from app.storage.settings_store import SettingsStore
    store = SettingsStore()
    ctrl = FakeController(running=False)
    c = _client(ctrl, monkeypatch, store)
    body = {"name": "A", "mt5": {"account": "1", "server": "S", "terminal_path": "C:/t.exe"}, "symbols": {}}
    assert c.post("/api/profiles", json=body).status_code == 200
    assert c.post("/api/profiles", json=body).status_code == 409
