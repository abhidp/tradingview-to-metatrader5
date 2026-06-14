from app.engine_controller import EngineController, EngineState


def test_initial_status_is_stopped(temp_db_path):
    c = EngineController()
    s = c.status()
    assert s.engine == EngineState.STOPPED
    assert s.proxy["listening"] is False
    assert s.proxy["port"] == 8080
    assert s.mt5["connected"] is False
    assert s.tv["connected"] is False
    assert "account" in s.mt5
    assert "broker_url" in s.tv


def test_status_to_dict_is_json_friendly(temp_db_path):
    c = EngineController()
    d = c.status().to_dict()
    assert d["engine"] == "stopped"
    assert set(d.keys()) == {"engine", "tv", "mt5", "proxy", "error"}


import socket as _socket


def test_port_free_detects_busy_port(temp_db_path):
    from app.engine_controller import _port_free

    s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    busy_port = s.getsockname()[1]
    try:
        assert _port_free("127.0.0.1", busy_port) is False
    finally:
        s.close()
    # after close, the port is free again
    assert _port_free("127.0.0.1", busy_port) is True
