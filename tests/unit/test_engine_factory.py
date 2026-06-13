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
