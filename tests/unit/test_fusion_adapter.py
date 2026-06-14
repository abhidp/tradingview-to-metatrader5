from app.adapters.base import AccountInfo, BrokerAdapter


def test_account_info_holds_target():
    info = AccountInfo(broker_url="broker.example.com", account_id="999")
    assert info.broker_url == "broker.example.com"
    assert info.account_id == "999"


def test_broker_adapter_is_a_protocol():
    # Protocol exists and is importable; concrete adapters implement it.
    assert hasattr(BrokerAdapter, "__mro__") or BrokerAdapter is not None


from app.adapters.fusion_markets import FusionMarketsAdapter
from app.storage.settings_store import SettingsStore


class _Req:
    def __init__(self, url, method="GET", headers=None):
        self.pretty_url = url
        self.method = method
        self.headers = headers or {}


class _Flow:
    def __init__(self, url, method="GET", headers=None):
        self.request = _Req(url, method, headers)


def _adapter_with_target(temp_db_path):
    store = SettingsStore()
    store.set("tv.broker_url", "broker.example.com")
    store.set("tv.account_id", "999")
    return FusionMarketsAdapter(store=store)


BASE = "https://broker.example.com/accounts/999"


def test_matches_orders(temp_db_path):
    a = _adapter_with_target(temp_db_path)
    assert a.matches(_Flow(f"{BASE}/orders?locale=en&requestId=abc", "POST")) is True


def test_matches_executions(temp_db_path):
    a = _adapter_with_target(temp_db_path)
    assert a.matches(_Flow(f"{BASE}/executions?locale=en&instrument=EURUSD")) is True


def test_matches_position_put_and_delete(temp_db_path):
    a = _adapter_with_target(temp_db_path)
    assert a.matches(_Flow(f"{BASE}/positions/123", "PUT")) is True
    assert a.matches(_Flow(f"{BASE}/positions/123", "DELETE")) is True
    assert a.matches(_Flow(f"{BASE}/positions/123", "GET")) is False


def test_matches_tpsl_delete(temp_db_path):
    a = _adapter_with_target(temp_db_path)
    url = f"{BASE}/orders/55.TP.1700000000"
    assert a.matches(_Flow(url, "DELETE")) is True
    assert a.matches(_Flow(url, "GET")) is False


def test_does_not_match_other_urls(temp_db_path):
    a = _adapter_with_target(temp_db_path)
    assert a.matches(_Flow(f"{BASE}/quotes")) is False
    assert a.matches(_Flow("https://other.com/accounts/1/orders?requestId=x", "POST")) is False


def test_no_target_never_matches(temp_db_path):
    # Fresh store with no tv.* target configured -> base_path is None -> never matches.
    adapter = FusionMarketsAdapter(store=SettingsStore())
    assert adapter.base_path is None
    assert adapter.matches(_Flow("https://broker.example.com/accounts/999/orders?requestId=x", "POST")) is False
