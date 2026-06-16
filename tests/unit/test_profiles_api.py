from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.profiles_api as papi


class FakeController:
    def __init__(self, running):
        self._running = running
        self.restarted = False

    def status(self):
        class S:
            def to_dict(self_inner):
                return {"engine": "running" if self._running else "stopped"}
        return S()

    async def restart(self):
        self.restarted = True


def _client(controller, monkeypatch, store):
    monkeypatch.setattr(papi.profiles, "SettingsStore", lambda: store)
    app = FastAPI()
    papi.add_profile_routes(app, controller)
    return TestClient(app)


def test_create_list_activate_restarts_when_running(temp_db_path, monkeypatch):
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
    assert ctrl.restarted is True
    assert c.get("/api/profiles").json()["active"] == pid


def test_activate_unknown_404(temp_db_path, monkeypatch):
    from app.storage.settings_store import SettingsStore
    store = SettingsStore()
    ctrl = FakeController(running=False)
    c = _client(ctrl, monkeypatch, store)
    assert c.post("/api/profiles/nope/activate").status_code == 404
