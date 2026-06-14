import asyncio

from fastapi.testclient import TestClient

from app.engine_controller import EngineController, EngineState


def test_query_trades_paging_filter_and_total(temp_db_path):
    from datetime import datetime, timedelta
    from src.models.database import init_db
    from src.utils.database_handler import DatabaseHandler
    from app.api.trades import query_trades

    init_db()
    db = DatabaseHandler()
    base = datetime(2026, 6, 14, 12, 0, 0)
    for i in range(5):
        db.save_trade({
            "trade_id": f"T{i}",
            "order_id": f"O{i}",
            "instrument": "EURUSD",
            "side": "buy",
            "quantity": "0.10",
            "type": "market",
            "ask_price": "1.1000",
            "bid_price": "1.0998",
            "tv_request": "{}",
            "tv_response": "{}",
            "status": "completed" if i % 2 == 0 else "failed",
            "created_at": base + timedelta(minutes=i),
        })

    rows, total = query_trades(limit=2, offset=0)
    assert total == 5
    assert [r["trade_id"] for r in rows] == ["T4", "T3"]  # newest first

    rows, total = query_trades(limit=2, offset=2)
    assert [r["trade_id"] for r in rows] == ["T2", "T1"]

    rows, total = query_trades(limit=10, offset=0, status="failed")
    assert total == 2
    assert {r["trade_id"] for r in rows} == {"T1", "T3"}
    db.cleanup()


class _FakeRunner:
    def __init__(self, listen_host="127.0.0.1", listen_port=8080):
        self._stop = asyncio.Event()
    async def serve(self):
        await self._stop.wait()
    def shutdown(self):
        self._stop.set()
    def mt5_connected(self):
        return True
    def tv_connected(self):
        return True


def _client(temp_db_path):
    from app.api.server import create_app
    controller = EngineController(runner_factory=_FakeRunner, listen_port=0)
    app = create_app(controller, focus_callback=lambda: None)
    return TestClient(app), controller


def test_status_endpoint(temp_db_path):
    client, _ = _client(temp_db_path)
    r = client.get("/api/status")
    assert r.status_code == 200
    assert r.json()["engine"] == "stopped"


def test_start_then_stop_endpoints(temp_db_path):
    client, _ = _client(temp_db_path)
    r = client.post("/api/engine/start")
    assert r.status_code == 200
    assert r.json()["engine"] == "running"
    r = client.post("/api/engine/stop")
    assert r.status_code == 200
    assert r.json()["engine"] == "stopped"


def test_start_returns_409_when_proxy_busy(temp_db_path):
    import socket
    from app.api.server import create_app
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0)); s.listen(1)
    busy = s.getsockname()[1]
    try:
        controller = EngineController(runner_factory=_FakeRunner, listen_port=busy)
        client = TestClient(create_app(controller, focus_callback=lambda: None))
        r = client.post("/api/engine/start")
        assert r.status_code == 409
        assert "in use" in r.json()["detail"]
    finally:
        s.close()


def test_focus_endpoint_invokes_callback(temp_db_path):
    from app.api.server import create_app
    hits = []
    controller = EngineController(runner_factory=_FakeRunner, listen_port=0)
    client = TestClient(create_app(controller, focus_callback=lambda: hits.append(1)))
    r = client.post("/api/focus")
    assert r.status_code == 200
    assert hits == [1]


def test_index_is_served(temp_db_path):
    client, _ = _client(temp_db_path)
    r = client.get("/")
    assert r.status_code == 200
    assert "TV2MT5" in r.text
    assert "Dashboard" in r.text


def test_settings_get_redacts_and_put_writes(temp_db_path):
    from app.storage.settings_store import SettingsStore
    client, _ = _client(temp_db_path)
    SettingsStore().set_secret("mt5.password", "secret")

    r = client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    assert body["mt5"]["password_set"] is True
    assert "secret" not in r.text

    r = client.put("/api/settings", json={"mt5": {"account": "777", "server": "Live"}})
    assert r.status_code == 200
    assert SettingsStore().get_int("mt5.account") == 777


def test_settings_put_rejects_bad_account(temp_db_path):
    client, _ = _client(temp_db_path)
    r = client.put("/api/settings", json={"mt5": {"account": "abc"}})
    assert r.status_code == 400


def test_symbols_get_put(temp_db_path):
    client, _ = _client(temp_db_path)
    r = client.put("/api/symbols", json={"default_suffix": ".r", "map": {"USTEC": "NAS100"}})
    assert r.status_code == 200
    r = client.get("/api/symbols")
    assert r.json() == {"default_suffix": ".r", "map": {"USTEC": "NAS100"}}


def test_symbols_put_rejects_bad_map(temp_db_path):
    client, _ = _client(temp_db_path)
    r = client.put("/api/symbols", json={"default_suffix": ".r", "map": [1, 2]})
    assert r.status_code == 400


def test_restart_endpoint(temp_db_path):
    client, _ = _client(temp_db_path)
    client.post("/api/engine/start")
    r = client.post("/api/engine/restart")
    assert r.status_code == 200
    assert r.json()["engine"] == "running"
    client.post("/api/engine/stop")


def test_index_has_all_tabs(temp_db_path):
    client, _ = _client(temp_db_path)
    html = client.get("/").text
    for view in ("view-trades", "view-symbols", "view-settings"):
        assert view in html
    assert "soon" not in html  # future-tab placeholders removed


def test_dashboard_logos_referenced_and_served(temp_db_path):
    client, _ = _client(temp_db_path)
    html = client.get("/").text
    assert "/static/img/tradingview.svg" in html
    assert "/static/img/mt5.png" in html
    assert client.get("/static/img/tradingview.svg").status_code == 200
    assert client.get("/static/img/mt5.png").status_code == 200
