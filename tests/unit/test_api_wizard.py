from fastapi.testclient import TestClient

from app.engine_controller import EngineController


class _FakeRunner:
    def __init__(self, listen_host="127.0.0.1", listen_port=8080):
        pass
    async def serve(self):
        pass
    def shutdown(self):
        pass
    def mt5_connected(self):
        return False
    def tv_connected(self):
        return False


def _client():
    from app.api.server import create_app
    return TestClient(create_app(EngineController(runner_factory=_FakeRunner, listen_port=0)))


def test_wizard_state_default(temp_db_path):
    r = _client().get("/api/wizard/state")
    assert r.status_code == 200
    assert r.json() == {"onboarding_complete": False, "step": 1}


def test_wizard_complete_sets_flag(temp_db_path):
    c = _client()
    assert c.post("/api/wizard/complete").json() == {"ok": True}
    assert c.get("/api/wizard/state").json()["onboarding_complete"] is True


def test_wizard_set_step(temp_db_path):
    c = _client()
    assert c.post("/api/wizard/step", json={"step": 4}).json() == {"ok": True}
    assert c.get("/api/wizard/state").json()["step"] == 4


def test_wizard_cert_status(temp_db_path, monkeypatch):
    from app.wizard import cert
    monkeypatch.setattr(cert, "is_cert_trusted", lambda: True)
    assert _client().get("/api/wizard/cert/status").json() == {"trusted": True}


def test_wizard_cert_install_pending(temp_db_path, monkeypatch):
    from app.wizard import cert
    monkeypatch.setattr(cert, "is_cert_trusted", lambda: False)
    monkeypatch.setattr(cert, "_launch_elevated_cert_install", lambda: 42)
    assert _client().post("/api/wizard/cert/install").json() == {"ok": False, "pending": True}


def test_wizard_mt5_detect(temp_db_path, monkeypatch):
    from app.wizard import detect
    monkeypatch.setattr(detect, "detect_mt5_terminals", lambda: ["C:/a/terminal64.exe"])
    body = _client().get("/api/wizard/mt5/detect").json()
    assert body["terminals"] == ["C:/a/terminal64.exe"]
    assert body["current"] is None


def test_wizard_mt5_test_success_persists(temp_db_path, monkeypatch):
    from app.wizard import detect
    monkeypatch.setattr(
        detect, "check_mt5_connection",
        lambda account, password, server, terminal_path=None: {
            "ok": True, "account": 1, "balance": 0.0, "server": server, "currency": "USD"},
    )
    r = _client().post("/api/wizard/mt5/test",
                       json={"mt5": {"account": "777", "password": "pw", "server": "Live"}})
    assert r.json()["ok"] is True
    from app.storage.settings_store import SettingsStore
    assert SettingsStore().get_int("mt5.account") == 777
    assert SettingsStore().get_secret("mt5.password") == "pw"


def test_wizard_mt5_test_failure_does_not_persist(temp_db_path, monkeypatch):
    from app.wizard import detect
    monkeypatch.setattr(detect, "check_mt5_connection",
                        lambda *a, **k: {"ok": False, "error": "bad creds"})
    r = _client().post("/api/wizard/mt5/test",
                       json={"mt5": {"account": "777", "password": "pw", "server": "Live"}})
    assert r.json() == {"ok": False, "error": "bad creds"}
    from app.storage.settings_store import SettingsStore
    assert SettingsStore().get_int("mt5.account") is None


def test_wizard_tv_detection(temp_db_path):
    from app.storage.settings_store import SettingsStore
    s = SettingsStore()
    s.set("tv.broker_url", "broker.x")
    s.set("tv.account_id", "42")
    r = _client().get("/api/wizard/tv/detection").json()
    assert r == {"detected": True, "broker_url": "broker.x", "account_id": "42"}


def test_wizard_symbols_suggest(temp_db_path):
    assert _client().get("/api/wizard/symbols/suggest").json() == {"suffix": ".r"}


def test_index_contains_wizard_markup(temp_db_path):
    html = _client().get("/").text
    assert "view-wizard" in html
    assert "wiz-rail" in html
