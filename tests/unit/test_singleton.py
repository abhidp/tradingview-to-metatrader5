from app.singleton import CONTROL_HOST, acquire_single_instance, is_another_instance_running


def test_acquire_returns_socket_then_blocks_second():
    sock = acquire_single_instance(port=0)
    assert sock is not None
    port = sock.getsockname()[1]
    try:
        assert is_another_instance_running(host=CONTROL_HOST, port=port) is True
        assert acquire_single_instance(port=port) is None
    finally:
        sock.close()


def test_no_instance_when_port_free():
    assert is_another_instance_running(host=CONTROL_HOST, port=0) is False
