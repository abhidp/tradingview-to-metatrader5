"""Tests for the broker-profile hot-swap path in MT5Worker.reconnect_mt5.

The real risk these guard: reconnect tears down and rebuilds the process-global
MT5 connection, so it must never interleave (across an await) with trade
processing or the position-check loop. We assert the shared _mt5_lock serialises
them, and that reconnect rebuilds the service + resets positions.
"""
import asyncio
import types

import pytest

import src.workers.mt5_worker as mod
from src.workers.mt5_worker import MT5Worker


class _FakeMT5Service:
    """Stand-in for MT5Service: connects instantly, no real terminal."""
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.initialized = True
        self.connected = True
        self.cleaned = False
        _FakeMT5Service.instances.append(self)

    def set_loop(self, loop):
        self.loop = loop

    def cleanup(self):
        self.cleaned = True
        self.initialized = False

    async def async_initialize(self):
        return True

    async def monitor_trailing_stops(self):
        while True:
            await asyncio.sleep(3600)


def _make_worker(monkeypatch):
    _FakeMT5Service.instances = []
    monkeypatch.setattr(mod, "MT5Service", _FakeMT5Service)
    monkeypatch.setattr(mod, "get_mt5_config",
                        lambda: {"account": "1", "password": "p", "server": "S", "terminal_path": ""})
    # The global `mt5` module is only used for positions_get in _initialize_positions.
    monkeypatch.setattr(mod, "mt5", types.SimpleNamespace(positions_get=lambda: []))
    w = MT5Worker()
    w.loop = asyncio.get_event_loop()
    w.mt5 = _FakeMT5Service()
    return w


async def test_reconnect_rebuilds_service_and_resets_positions(temp_db_path, monkeypatch):
    w = _make_worker(monkeypatch)
    w.open_positions = {"999"}
    old = w.mt5
    await w.reconnect_mt5()
    assert old.cleaned is True            # previous connection closed
    assert w.mt5 is not old               # a fresh service was built
    assert w.open_positions == set()      # positions reset for the new broker
    # clean up the trailing monitor task the reconnect started
    await w._stop_trailing_monitor()


async def test_reconnect_waits_for_in_flight_trade(temp_db_path, monkeypatch):
    w = _make_worker(monkeypatch)
    order = []

    async def fake_trade():
        # Mimic process_trade holding the shared lock across an await.
        async with w._mt5_lock:
            order.append("trade-start")
            await asyncio.sleep(0.15)
            order.append("trade-end")

    trade = asyncio.create_task(fake_trade())
    await asyncio.sleep(0.02)             # let the trade acquire the lock first
    await w.reconnect_mt5()               # must block until the trade releases
    order.append("reconnect-done")
    await trade
    await w._stop_trailing_monitor()

    # reconnect's swap must not begin until the in-flight trade finished
    assert order == ["trade-start", "trade-end", "reconnect-done"]
