class _StubHandler:
    pass


def test_interceptor_accepts_injected_handler(monkeypatch):
    # Avoid the network instrument-sync on construction.
    monkeypatch.setenv("TV_BROKER_URL", "broker.example.com")
    monkeypatch.setenv("TV_ACCOUNT_ID", "999")

    from src.core.interceptor import TradingViewInterceptor

    # Reset the singleton so the test controls construction.
    TradingViewInterceptor._instance = None
    TradingViewInterceptor._initialized = False

    stub = _StubHandler()
    interceptor = TradingViewInterceptor(trade_handler=stub, sync_instruments=False)
    assert interceptor.trade_handler is stub


async def test_build_master_configures_listen_options(monkeypatch):
    monkeypatch.setenv("TV_BROKER_URL", "broker.example.com")
    monkeypatch.setenv("TV_ACCOUNT_ID", "999")

    from app.engine import build_master

    class _Addon:
        pass

    master = build_master(_Addon(), listen_host="127.0.0.1", listen_port=8081)
    assert master.options.listen_host == "127.0.0.1"
    assert master.options.listen_port == 8081
    assert master.options.ssl_insecure is True


import asyncio  # noqa: E402


async def test_worker_inproc_init_uses_injected_queue_and_db(temp_db_path, monkeypatch):
    monkeypatch.setenv("MT5_ACCOUNT", "123")
    monkeypatch.setenv("MT5_PASSWORD", "pw")
    monkeypatch.setenv("MT5_SERVER", "Demo")

    from src.models.database import init_db
    from src.utils.database_handler import DatabaseHandler
    from app.queue.inproc_queue import InProcQueue
    from src.workers.mt5_worker import MT5Worker

    init_db()
    queue = InProcQueue()
    db = DatabaseHandler()

    worker = MT5Worker()
    worker.init_inproc(loop=asyncio.get_event_loop(), queue=queue, db=db)

    assert worker.queue is queue
    assert worker.db is db
    assert worker.loop is asyncio.get_event_loop()
    queue.cleanup()
    db.cleanup()
