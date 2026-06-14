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
        if runner_factory is None:
            from app.engine import MitmEngineRunner
            runner_factory = MitmEngineRunner
        self._runner_factory = runner_factory
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

    async def start(self) -> Status:
        if self._state in (EngineState.STARTING, EngineState.RUNNING):
            return self.status()
        if self.listen_port != 0 and not _port_free(self.listen_host, self.listen_port):
            self._error = (
                f"Proxy port {self.listen_port} is in use — another copier may be running."
            )
            self._state = EngineState.STOPPED
            raise ProxyPortInUseError(self._error)

        self._error = None
        self._state = EngineState.STARTING
        self._runner = self._runner_factory(
            listen_host=self.listen_host, listen_port=self.listen_port
        )
        self._task = asyncio.create_task(self._serve())

        # Let wiring begin; catch an immediate failure before reporting RUNNING.
        await asyncio.sleep(0.1)
        if self._task.done():
            # The task finished during startup. If _serve() already recorded an
            # ERROR with a specific reason, keep it; otherwise report a generic
            # early-exit. (start() can be called again to retry from ERROR — it
            # replaces the runner/task, since ERROR is not in the no-op guard.)
            if self._state != EngineState.ERROR:
                exc = self._task.exception()
                self._state = EngineState.ERROR
                self._error = str(exc) if exc else "engine exited during startup"
        else:
            self._state = EngineState.RUNNING
        return self.status()

    async def _serve(self) -> None:
        try:
            await self._runner.serve()
        except Exception as e:  # noqa: BLE001 - surfaced via status().error
            logger.error("Engine runner failed: %s", e)
            self._error = str(e)
            self._state = EngineState.ERROR
        finally:
            if self._state != EngineState.ERROR:
                self._state = EngineState.STOPPED

    async def stop(self) -> Status:
        if self._state not in (EngineState.RUNNING, EngineState.STARTING):
            return self.status()
        self._state = EngineState.STOPPING
        if self._runner is not None:
            self._runner.shutdown()
        if self._task is not None:
            await self._task
        self._runner = None
        self._task = None
        if self._error is None:
            self._state = EngineState.STOPPED
        return self.status()

    async def restart(self) -> Status:
        """Stop (if running) then start — used to apply settings changes.

        stop() fully releases the proxy port before start() re-checks it, so this
        avoids a client-side stop/start race.
        """
        await self.stop()
        return await self.start()
