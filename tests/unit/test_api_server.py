import asyncio
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.engine_controller import EngineController, EngineState


def test_recent_trades_newest_first_and_limited(temp_db_path):
    from src.models.database import init_db
    from src.utils.database_handler import DatabaseHandler
    from app.api.trades import recent_trades

    init_db()
    db = DatabaseHandler()
    base = datetime(2026, 6, 14, 12, 0, 0)
    for i in range(3):
        db.save_trade({
            "trade_id": f"T{i}",
            "order_id": f"O{i}",
            "instrument": "EURUSD",
            "side": "buy",
            "quantity": "0.10",
            "type": "market",
            "ask_price": "1.1000",
            "bid_price": "1.0998",
            "status": "completed",
            "tv_request": "{}",
            "tv_response": "{}",
            "created_at": base + timedelta(minutes=i),
        })

    rows = recent_trades(limit=2)
    assert len(rows) == 2
    assert rows[0]["trade_id"] == "T2"  # newest first
    assert rows[1]["trade_id"] == "T1"
    assert rows[0]["instrument"] == "EURUSD"
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
