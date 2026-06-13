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
