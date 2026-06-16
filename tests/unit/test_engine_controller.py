import asyncio

import pytest

from app.engine_controller import EngineController, EngineState, ProxyPortInUseError


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


class _FakeRunner:
    """Simulates the engine: serve() blocks until shutdown() is called."""

    def __init__(self, listen_host="127.0.0.1", listen_port=8080):
        self._stop = asyncio.Event()
        self.served = False
        self.shut = False

    async def serve(self):
        self.served = True
        await self._stop.wait()

    def shutdown(self):
        self.shut = True
        self._stop.set()

    def mt5_connected(self):
        return True

    def tv_connected(self):
        return True


async def test_start_then_stop_transitions(temp_db_path):
    c = EngineController(runner_factory=_FakeRunner, listen_port=0)
    s = await c.start()
    assert s.engine == EngineState.RUNNING
    assert s.proxy["listening"] is True
    assert s.mt5["connected"] is True

    s = await c.stop()
    assert s.engine == EngineState.STOPPED
    assert s.proxy["listening"] is False


async def test_start_is_idempotent_when_running(temp_db_path):
    c = EngineController(runner_factory=_FakeRunner, listen_port=0)
    await c.start()
    s = await c.start()  # second call is a no-op
    assert s.engine == EngineState.RUNNING
    await c.stop()


async def test_start_raises_when_proxy_port_busy(temp_db_path):
    import socket as sock
    s = sock.socket(sock.AF_INET, sock.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    busy = s.getsockname()[1]
    try:
        c = EngineController(runner_factory=_FakeRunner, listen_port=busy)
        with pytest.raises(ProxyPortInUseError):
            await c.start()
        assert c.status().engine == EngineState.STOPPED
    finally:
        s.close()


async def test_error_is_reported_and_can_restart(temp_db_path):
    class _FailingRunner:
        def __init__(self, listen_host="127.0.0.1", listen_port=8080):
            pass
        async def serve(self):
            raise RuntimeError("MT5 connection refused")
        def shutdown(self):
            pass
        def mt5_connected(self):
            return False
        def tv_connected(self):
            return False

    seq = [_FailingRunner, _FakeRunner]

    def factory(**kwargs):
        return seq.pop(0)(**kwargs)

    c = EngineController(runner_factory=factory, listen_port=0)
    s = await c.start()
    assert s.engine == EngineState.ERROR
    assert s.error and "MT5 connection refused" in s.error  # specific reason preserved

    # ERROR is recoverable: a second start() retries with a healthy runner.
    s = await c.start()
    assert s.engine == EngineState.RUNNING
    await c.stop()


async def test_restart_cycles_to_running(temp_db_path):
    c = EngineController(runner_factory=_FakeRunner, listen_port=0)
    await c.start()
    s = await c.restart()
    assert s.engine == EngineState.RUNNING
    await c.stop()


async def test_restart_from_stopped_just_starts(temp_db_path):
    c = EngineController(runner_factory=_FakeRunner, listen_port=0)
    s = await c.restart()
    assert s.engine == EngineState.RUNNING
    await c.stop()


async def test_wait_for_port_free_returns_immediately_at_port_zero(temp_db_path):
    c = EngineController(runner_factory=_FakeRunner, listen_port=0)
    await c._wait_for_port_free(timeout=0.5)  # port 0 sentinel -> no-op, must not hang


async def test_wait_for_port_free_blocks_until_timeout_when_busy(temp_db_path):
    s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    busy_port = s.getsockname()[1]
    c = EngineController(runner_factory=_FakeRunner, listen_port=busy_port)
    try:
        loop = asyncio.get_event_loop()
        t0 = loop.time()
        await c._wait_for_port_free(timeout=0.3)  # never frees -> returns after ~timeout
        assert loop.time() - t0 >= 0.3
    finally:
        s.close()


class _ReconnectRunner(_FakeRunner):
    def __init__(self, listen_host="127.0.0.1", listen_port=8080):
        super().__init__(listen_host, listen_port)
        self.reconnects = 0

    async def reconnect_mt5(self):
        self.reconnects += 1


async def test_apply_mt5_settings_reconnects_when_running(temp_db_path):
    c = EngineController(runner_factory=_ReconnectRunner, listen_port=0)
    await c.start()
    await c.apply_mt5_settings()
    assert c._runner.reconnects == 1  # reconnected in place, no restart
    await c.stop()


async def test_apply_mt5_settings_is_noop_when_stopped(temp_db_path):
    c = EngineController(runner_factory=_ReconnectRunner, listen_port=0)
    s = await c.apply_mt5_settings()  # never started
    assert s.engine == EngineState.STOPPED
