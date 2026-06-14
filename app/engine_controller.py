"""Engine lifecycle controller: start/stop the engine task and report status.

The controller owns the engine's run state. The actual proxy+worker work is a
"runner" (see app.engine.MitmEngineRunner) so the controller stays unit-testable
with a fake runner.
"""
import asyncio
import logging
import socket
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger("EngineController")


class EngineState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class Status:
    engine: EngineState
    tv: dict
    mt5: dict
    proxy: dict
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "engine": self.engine.value,
            "tv": self.tv,
            "mt5": self.mt5,
            "proxy": self.proxy,
            "error": self.error,
        }


class ProxyPortInUseError(RuntimeError):
    """Raised by start() when the engine proxy port is already bound."""


def _port_free(host: str, port: int) -> bool:
    """True if (host, port) can be bound right now."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        s.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


class EngineController:
    def __init__(
        self,
        runner_factory: Optional[Callable] = None,
        listen_host: str = "127.0.0.1",
        listen_port: int = 8080,
    ) -> None:
        self.listen_host = listen_host
        self.listen_port = listen_port
        self._runner_factory = runner_factory  # default wired in a later task; injected in tests
        self._state = EngineState.STOPPED
        self._error: Optional[str] = None
        self._runner = None
        self._task: Optional[asyncio.Task] = None

    def status(self) -> Status:
        from app.config_accessors import get_mt5_config, get_tv_target

        running = self._state == EngineState.RUNNING
        mt5_cfg = get_mt5_config()
        broker_url, account_id = get_tv_target()

        mt5_connected = bool(running and self._runner and self._runner.mt5_connected())
        tv_connected = bool(running and self._runner and self._runner.tv_connected())

        return Status(
            engine=self._state,
            tv={"connected": tv_connected, "account": account_id, "broker_url": broker_url},
            mt5={"connected": mt5_connected, "account": mt5_cfg["account"], "server": mt5_cfg["server"]},
            proxy={"listening": running, "port": self.listen_port},
            error=self._error,
        )
