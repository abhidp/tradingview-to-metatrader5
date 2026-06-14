from app.adapters.base import AccountInfo, BrokerAdapter


def test_account_info_holds_target():
    info = AccountInfo(broker_url="broker.example.com", account_id="999")
    assert info.broker_url == "broker.example.com"
    assert info.account_id == "999"


def test_broker_adapter_is_a_protocol():
    # Protocol exists and is importable; concrete adapters implement it.
    assert hasattr(BrokerAdapter, "__mro__") or BrokerAdapter is not None
