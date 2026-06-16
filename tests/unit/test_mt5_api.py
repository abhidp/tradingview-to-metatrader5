# tests/unit/test_mt5_api.py
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.mt5_api as mt5_api


def _client(pick_file=None, monkeypatch=None, terminals=None):
    if terminals is not None:
        monkeypatch.setattr(mt5_api, "discover_mt5_terminals", lambda: terminals)
    app = FastAPI()
    mt5_api.add_mt5_routes(app, pick_file=pick_file)
    return TestClient(app)


def test_terminals_endpoint_returns_list_and_current(monkeypatch):
    monkeypatch.setattr(mt5_api, "discover_mt5_terminals",
                        lambda: [{"path": "C:/x/terminal64.exe", "label": "X"}])
    monkeypatch.setattr(mt5_api, "_current_terminal", lambda: "C:/x/terminal64.exe")
    c = _client()
    r = c.get("/api/mt5/terminals")
    assert r.status_code == 200
    body = r.json()
    assert body["terminals"] == [{"path": "C:/x/terminal64.exe", "label": "X"}]
    assert body["current"] == "C:/x/terminal64.exe"


def test_browse_returns_picked_path(monkeypatch):
    c = _client(pick_file=lambda: "C:/picked/terminal64.exe")
    r = c.post("/api/mt5/browse-terminal")
    assert r.status_code == 200
    assert r.json() == {"path": "C:/picked/terminal64.exe"}


def test_browse_returns_null_when_no_picker():
    app = FastAPI()
    mt5_api.add_mt5_routes(app, pick_file=None)
    c = TestClient(app)
    r = c.post("/api/mt5/browse-terminal")
    assert r.status_code == 200
    assert r.json() == {"path": None}
