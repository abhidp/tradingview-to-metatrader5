# TV2MT5 Desktop — Plan 3a: App Shell Foundation (UI + Tray) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap the proven engine in a single-process Windows desktop app — a WebView2 window + tray icon that Start/Stops the engine and shows live status and logs — with single-instance and proxy-port guards, without changing the trade interception/execution logic.

**Architecture:** One background asyncio loop hosts uvicorn (FastAPI: JSON API + static UI) and the engine as a cancellable task managed by an `EngineController`. pywebview owns the main thread (the window points at the local FastAPI port); pystray runs on its own thread. The engine wiring from Plan 1/2 is refactored into a `MitmEngineRunner` (serve/shutdown) that the controller drives. The app's single FastAPI port doubles as the single-instance guard; the engine's proxy port (8080) is checked free before Start.

**Tech Stack:** Python 3.11, FastAPI + uvicorn, pywebview (WebView2), pystray + Pillow, mitmproxy 11, asyncio, vanilla HTML/CSS/JS, pytest + pytest-asyncio + FastAPI TestClient.

---

## File Structure

**Create:**
- `app/engine_controller.py` — `EngineState`, `Status`, `EngineController` (state machine + start/stop/status; drives a runner).
- `app/singleton.py` — control host/port constants + single-instance guard (bind socket / detect in-use / focus URL).
- `app/api/__init__.py`
- `app/api/logs.py` — cursor-based log tailer over the rotating log file.
- `app/api/trades.py` — recent-trades query over the `trades` table.
- `app/api/server.py` — `create_app(controller)` FastAPI factory + routes + static UI mount.
- `app/ui/index.html`, `app/ui/styles.css`, `app/ui/app.js` — sidebar nav + Dashboard (layout A) + Logs; future tabs greyed.
- `app/tray.py` — pystray icon + menu (Start/Stop/Open/Quit + status) that call the local API.
- `app/desktop.py` — desktop entrypoint: singleton → API thread → tray thread → webview (main thread) → Quit handling.
- `tests/unit/test_engine_controller.py`
- `tests/unit/test_singleton.py`
- `tests/unit/test_api_logs.py`
- `tests/unit/test_api_server.py`

**Modify:**
- `app/engine.py` — add `MitmEngineRunner` (serve/shutdown/status bits); refactor `run_engine` to delegate to it (headless unchanged).
- `src/services/mt5_service.py` — add an explicit `connected` flag for status reporting.
- `requirements.txt` — add `fastapi`, `uvicorn`, `pywebview`, `pystray`, `pillow`.
- `run.py` — add a `desktop` command that launches `app/desktop.py`.

**Unchanged (explicitly):** `src/core/trade_handler.py`, `src/core/interceptor.py` (beyond Plan 2), `src/workers/mt5_worker.py`, the queue/store/adapter modules.

---

## Task 1: Desktop/UI dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add the dependencies**

Append these lines to `requirements.txt` (keep existing entries):

```text
fastapi==0.111.0
uvicorn==0.30.1
pywebview==5.1
pystray==0.19.5
pillow==10.3.0
```

- [ ] **Step 2: Install them**

Run: `pip install -r requirements.txt`
Expected: all install successfully (FastAPI, uvicorn, pywebview, pystray, pillow).

- [ ] **Step 3: Verify imports**

Run: `python -c "import fastapi, uvicorn, webview, pystray, PIL; print('ui deps ok')"`
Expected: prints `ui deps ok`.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "build: add fastapi/uvicorn/pywebview/pystray/pillow for app shell"
```

---

## Task 2: MT5Service connection flag

**Files:**
- Modify: `src/services/mt5_service.py`
- Test: (covered by `test_engine_controller.py` status tests; this task adds a tiny attribute)

The status panel needs to know whether MT5 is connected. `MT5Service` already tracks `self.initialized`; add an explicit, unambiguous `connected` flag set on successful connect and cleared on failure/cleanup.

- [ ] **Step 1: Initialise the flag in `__init__`**

In `src/services/mt5_service.py`, in `MT5Service.__init__`, add right after `self.terminal_path = ...` line (around original line 43) the line:

```python
        self.connected = False
```

- [ ] **Step 2: Set the flag on successful connect**

In the synchronous `initialize()` method, locate the success path that logs `✅ MT5 Connected:` and `return True` (around original lines 108–109). Immediately before that `return True`, add:

```python
            self.connected = True
```

And on each failure `return False` in `initialize()` (the `mt5.initialize` failure, the `mt5.login` failure, and the account-info failure — around original lines 89, 95, 102), add immediately before each `return False`:

```python
            self.connected = False
```

- [ ] **Step 3: Verify it imports and defaults False**

Run: `python -c "import inspect, src.services.mt5_service as m; src='self.connected = False' in inspect.getsource(m.MT5Service.__init__); print('flag present:', src)"`
Expected: prints `flag present: True`.

- [ ] **Step 4: Commit**

```bash
git add src/services/mt5_service.py
git commit -m "feat: add MT5Service.connected flag for status reporting"
```

---

## Task 3: EngineController — state, Status, idle snapshot

**Files:**
- Create: `app/engine_controller.py`
- Test: `tests/unit/test_engine_controller.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_engine_controller.py`:

```python
from app.engine_controller import EngineController, EngineState


def test_initial_status_is_stopped(temp_db_path):
    c = EngineController()
    s = c.status()
    assert s.engine == EngineState.STOPPED
    assert s.proxy["listening"] is False
    assert s.proxy["port"] == 8080
    assert s.mt5["connected"] is False
    assert s.tv["connected"] is False
    # config-derived fields are present even when stopped
    assert "account" in s.mt5
    assert "broker_url" in s.tv


def test_status_to_dict_is_json_friendly(temp_db_path):
    c = EngineController()
    d = c.status().to_dict()
    assert d["engine"] == "stopped"
    assert set(d.keys()) == {"engine", "tv", "mt5", "proxy", "error"}
```

- [ ] **Step 2: Run it (fails)**

Run: `pytest tests/unit/test_engine_controller.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.engine_controller'`.

- [ ] **Step 3: Implement state + Status + idle status()**

Create `app/engine_controller.py`:

```python
"""Engine lifecycle controller: start/stop the engine task and report status.

The controller owns the engine's run state. The actual proxy+worker work is a
"runner" (see app.engine.MitmEngineRunner) so the controller stays unit-testable
with a fake runner.
"""
import asyncio
import logging
import socket
from dataclasses import dataclass, field
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
        self._runner_factory = runner_factory  # set in Task 6 default; injected in tests
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
```

- [ ] **Step 4: Run it (passes)**

Run: `pytest tests/unit/test_engine_controller.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/engine_controller.py tests/unit/test_engine_controller.py
git commit -m "feat: add EngineController state + Status snapshot"
```

---

## Task 4: Proxy-port guard

**Files:**
- Modify: `app/engine_controller.py` (already has `_port_free`)
- Test: `tests/unit/test_engine_controller.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_engine_controller.py`:

```python
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
```

- [ ] **Step 2: Run it**

Run: `pytest tests/unit/test_engine_controller.py::test_port_free_detects_busy_port -q`
Expected: PASS (the helper from Task 3 already implements this).

> If it fails, ensure `_port_free` sets `SO_REUSEADDR` to `0` (Task 3) so a busy
> listening port is correctly reported as not bindable.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_engine_controller.py
git commit -m "test: cover proxy-port free/busy detection"
```

---

## Task 5: EngineController start/stop (with injectable runner)

**Files:**
- Modify: `app/engine_controller.py`
- Test: `tests/unit/test_engine_controller.py` (append)

- [ ] **Step 1: Write the failing tests using a fake runner**

Append to `tests/unit/test_engine_controller.py`:

```python
import asyncio

import pytest

from app.engine_controller import EngineState, ProxyPortInUseError


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
```

> `listen_port=0` skips a real bind conflict in the happy-path tests: `_port_free`
> returns True for port 0, and the fake runner never binds.

- [ ] **Step 2: Run them (fail)**

Run: `pytest tests/unit/test_engine_controller.py -q`
Expected: FAIL — `EngineController` has no `start`/`stop`.

- [ ] **Step 3: Implement start/stop**

In `app/engine_controller.py`, add these methods to `EngineController` (after `status`):

```python
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
```

- [ ] **Step 4: Run them (pass)**

Run: `pytest tests/unit/test_engine_controller.py -q`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add app/engine_controller.py tests/unit/test_engine_controller.py
git commit -m "feat: EngineController start/stop with injectable runner + port guard"
```

---

## Task 6: MitmEngineRunner (real runner) + run_engine delegation

**Files:**
- Modify: `app/engine.py`
- Modify: `app/engine_controller.py` (default runner factory)

- [ ] **Step 1: Add `MitmEngineRunner` to `app/engine.py`**

In `app/engine.py`, after `build_master` (before `run_engine`), add:

```python
class MitmEngineRunner:
    """The proxy + MT5 worker wiring as a start/stoppable unit.

    serve() blocks until shutdown() is called (it awaits mitmproxy's master).
    This is the production runner injected into EngineController; tests inject a fake.
    """

    def __init__(self, listen_host: str = "127.0.0.1", listen_port: int = 8080) -> None:
        self.listen_host = listen_host
        self.listen_port = listen_port
        self._master = None
        self._worker = None
        self._worker_task = None
        self._queue = None
        self._db = None

    async def serve(self) -> None:
        from src.models.database import init_db
        from src.utils.database_handler import DatabaseHandler
        from src.core.trade_handler import TradeHandler
        from src.core.interceptor import TradingViewInterceptor
        from src.workers.mt5_worker import MT5Worker
        from app.queue.inproc_queue import InProcQueue
        from app.storage.settings_store import SettingsStore
        from app.adapters.fusion_markets import FusionMarketsAdapter

        quiet_proxy_noise()
        init_db()

        store = SettingsStore()
        store.seed_from_env_once()

        loop = asyncio.get_running_loop()
        self._queue = InProcQueue()
        self._db = DatabaseHandler()

        trade_handler = TradeHandler(queue=self._queue, db=self._db)

        self._worker = MT5Worker()
        self._worker.init_inproc(loop=loop, queue=self._queue, db=self._db)
        self._queue.subscribe(self._worker.handle_message)

        adapter = FusionMarketsAdapter(store=store)

        TradingViewInterceptor._instance = None
        TradingViewInterceptor._initialized = False
        interceptor = TradingViewInterceptor(
            trade_handler=trade_handler, adapter=adapter, sync_instruments=False
        )

        self._master = build_master(
            interceptor, listen_host=self.listen_host, listen_port=self.listen_port
        )

        self._worker_task = asyncio.create_task(self._worker.run_async())
        try:
            logger.info("Engine starting: proxy on %s:%s", self.listen_host, self.listen_port)
            await self._master.run()
        finally:
            self._worker.running = False
            self._worker_task.cancel()
            await asyncio.gather(self._worker_task, return_exceptions=True)
            self._queue.cleanup()
            self._db.cleanup()
            logger.info("Engine stopped")

    def shutdown(self) -> None:
        if self._master is not None:
            self._master.shutdown()

    def mt5_connected(self) -> bool:
        return bool(self._worker is not None and getattr(self._worker, "mt5", None) is not None
                    and getattr(self._worker.mt5, "connected", False))

    def tv_connected(self) -> bool:
        from src.utils.token_manager import GLOBAL_TOKEN_MANAGER
        try:
            return bool(GLOBAL_TOKEN_MANAGER.get_token())
        except Exception:
            return False
```

- [ ] **Step 2: Refactor `run_engine` to delegate to the runner**

In `app/engine.py`, replace the entire body of `run_engine` (original lines 49–102, everything after the docstring) with:

```python
    runner = MitmEngineRunner(listen_host=listen_host, listen_port=listen_port)
    await runner.serve()
```

Leave the `run_engine` signature and docstring intact.

- [ ] **Step 3: Wire the default runner factory into the controller**

In `app/engine_controller.py`, change `EngineController.__init__` so the default
`runner_factory` is `MitmEngineRunner`. Replace the line:

```python
        self._runner_factory = runner_factory  # set in Task 6 default; injected in tests
```

with:

```python
        if runner_factory is None:
            from app.engine import MitmEngineRunner
            runner_factory = MitmEngineRunner
        self._runner_factory = runner_factory
```

- [ ] **Step 4: Verify imports + existing engine tests still pass**

Run: `python -c "import app.engine, app.engine_controller; print('ok')"`
Expected: prints `ok`.

Run: `pytest tests/unit -q`
Expected: PASS (all unit tests, including the Plan 1 `test_engine_factory.py` and the controller tests).

- [ ] **Step 5: Commit**

```bash
git add app/engine.py app/engine_controller.py
git commit -m "refactor: extract MitmEngineRunner; run_engine + controller delegate to it"
```

---

## Task 7: Single-instance guard

**Files:**
- Create: `app/singleton.py`
- Test: `tests/unit/test_singleton.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_singleton.py`:

```python
from app.singleton import CONTROL_HOST, acquire_single_instance, is_another_instance_running


def test_acquire_returns_socket_then_blocks_second():
    sock = acquire_single_instance(port=0)
    assert sock is not None
    port = sock.getsockname()[1]
    try:
        # while held, another instance on the same port is detected
        assert is_another_instance_running(host=CONTROL_HOST, port=port) is True
        # and acquiring the same port again fails
        assert acquire_single_instance(port=port) is None
    finally:
        sock.close()


def test_no_instance_when_port_free():
    # an almost-certainly-free ephemeral port reports no running instance
    assert is_another_instance_running(host=CONTROL_HOST, port=0) is False
```

> Port 0 lets the OS pick a free port for the held socket; `is_another_instance_running`
> on port 0 connects nowhere, so it returns False.

- [ ] **Step 2: Run them (fail)**

Run: `pytest tests/unit/test_singleton.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.singleton'`.

- [ ] **Step 3: Implement the guard**

Create `app/singleton.py`:

```python
"""Single-instance guard for the desktop app.

The app binds one TCP port (CONTROL_PORT) that serves the UI + JSON API. That
bind is also the single-instance lock: if the port is already bound, another
instance is running. A second instance pings /api/focus on the first, then exits.
"""
import logging
import socket
from typing import Optional

logger = logging.getLogger("Singleton")

CONTROL_HOST = "127.0.0.1"
CONTROL_PORT = 8420


def acquire_single_instance(host: str = CONTROL_HOST, port: int = CONTROL_PORT) -> Optional[socket.socket]:
    """Bind and return the control socket, or None if already bound (another instance)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        s.bind((host, port))
        s.listen(128)
        s.setblocking(False)
        return s
    except OSError:
        s.close()
        return None


def is_another_instance_running(host: str = CONTROL_HOST, port: int = CONTROL_PORT) -> bool:
    """True if something is already accepting connections on the control port."""
    if port == 0:
        return False
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.3)
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def focus_running_instance(host: str = CONTROL_HOST, port: int = CONTROL_PORT) -> bool:
    """Best-effort: ask the running instance to raise its window via POST /api/focus."""
    try:
        import urllib.request

        req = urllib.request.Request(f"http://{host}:{port}/api/focus", method="POST")
        urllib.request.urlopen(req, timeout=1.0).close()
        return True
    except Exception as e:  # noqa: BLE001
        logger.info("focus request failed: %s", e)
        return False
```

- [ ] **Step 4: Run them (pass)**

Run: `pytest tests/unit/test_singleton.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/singleton.py tests/unit/test_singleton.py
git commit -m "feat: add single-instance guard (control-port bind + focus ping)"
```

---

## Task 8: Log tailer

**Files:**
- Create: `app/api/__init__.py`
- Create: `app/api/logs.py`
- Test: `tests/unit/test_api_logs.py`

- [ ] **Step 1: Create the package marker**

Create `app/api/__init__.py`:

```python
"""Local FastAPI server: JSON API + static UI for the desktop app."""
```

- [ ] **Step 2: Write the failing tests**

Create `tests/unit/test_api_logs.py`:

```python
from app.api.logs import read_log_tail


def test_read_from_start_returns_all_then_advances(tmp_path):
    f = tmp_path / "app.log"
    f.write_text("line1\nline2\n", encoding="utf-8")

    lines, cursor = read_log_tail(f, after=0)
    assert lines == ["line1", "line2"]
    assert cursor == f.stat().st_size

    # nothing new yet
    lines2, cursor2 = read_log_tail(f, after=cursor)
    assert lines2 == []
    assert cursor2 == cursor

    # append, then only the new line comes back
    with f.open("a", encoding="utf-8") as fh:
        fh.write("line3\n")
    lines3, cursor3 = read_log_tail(f, after=cursor)
    assert lines3 == ["line3"]
    assert cursor3 == f.stat().st_size


def test_missing_file_is_empty(tmp_path):
    lines, cursor = read_log_tail(tmp_path / "nope.log", after=0)
    assert lines == []
    assert cursor == 0
```

- [ ] **Step 3: Run them (fail)**

Run: `pytest tests/unit/test_api_logs.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.api.logs'`.

- [ ] **Step 4: Implement the tailer**

Create `app/api/logs.py`:

```python
"""Cursor-based tail of the rotating log file for the Logs view."""
from pathlib import Path
from typing import List, Tuple


def read_log_tail(path: Path, after: int = 0) -> Tuple[List[str], int]:
    """Return (new_lines, new_cursor) for bytes after the given offset.

    `after` is a byte offset into the file. If the file shrank (rotation), we
    restart from 0. Missing file returns ([], 0).
    """
    path = Path(path)
    if not path.exists():
        return [], 0
    size = path.stat().st_size
    if after > size:  # rotated/truncated
        after = 0
    if after == size:
        return [], size
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        fh.seek(after)
        text = fh.read()
    cursor = size
    lines = [ln for ln in text.splitlines() if ln != ""]
    return lines, cursor
```

- [ ] **Step 5: Run them (pass)**

Run: `pytest tests/unit/test_api_logs.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add app/api/__init__.py app/api/logs.py tests/unit/test_api_logs.py
git commit -m "feat: add cursor-based log tailer for the Logs view"
```

---

## Task 9: Recent-trades query

**Files:**
- Create: `app/api/trades.py`
- Test: `tests/unit/test_api_server.py` (created here; reused in Task 10–11)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_api_server.py`:

```python
from datetime import datetime, timedelta


def test_recent_trades_newest_first_and_limited(temp_db_path):
    from src.models.database import init_db
    from src.utils.database_handler import DatabaseHandler
    from app.api.trades import recent_trades

    init_db()
    db = DatabaseHandler()
    base = datetime(2026, 6, 14, 12, 0, 0)
    for i in range(3):
        db.save_trade({
            "trade_id": f"T{i}",
            "instrument": "EURUSD",
            "side": "buy",
            "quantity": "0.10",
            "type": "market",
            "status": "completed",
            "created_at": base + timedelta(minutes=i),
        })

    rows = recent_trades(limit=2)
    assert len(rows) == 2
    assert rows[0]["trade_id"] == "T2"  # newest first
    assert rows[1]["trade_id"] == "T1"
    assert rows[0]["instrument"] == "EURUSD"
    db.cleanup()
```

> `DatabaseHandler.save_trade` is the existing synchronous save used by the worker;
> it accepts the trade dict shown above.

- [ ] **Step 2: Run it (fails)**

Run: `pytest tests/unit/test_api_server.py::test_recent_trades_newest_first_and_limited -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.api.trades'`.

- [ ] **Step 3: Implement the query**

Create `app/api/trades.py`:

```python
"""Recent-trades read for the Dashboard preview (full history is Plan 3b)."""
from typing import List

from src.config.database import get_session_factory
from src.models.database import Trade


def recent_trades(limit: int = 10) -> List[dict]:
    """Most recent trades, newest first, as JSON-friendly dicts."""
    Session = get_session_factory()
    session = Session()
    try:
        rows = (
            session.query(Trade)
            .order_by(Trade.created_at.desc())
            .limit(limit)
            .all()
        )
        out = []
        for t in rows:
            created = getattr(t, "created_at", None)
            out.append({
                "trade_id": getattr(t, "trade_id", None),
                "instrument": getattr(t, "instrument", None),
                "side": getattr(t, "side", None),
                "quantity": str(getattr(t, "quantity", "")),
                "status": getattr(t, "status", None),
                "created_at": created.isoformat() if created else None,
            })
        return out
    finally:
        session.close()
```

- [ ] **Step 4: Run it (passes)**

Run: `pytest tests/unit/test_api_server.py::test_recent_trades_newest_first_and_limited -q`
Expected: PASS.

> If `save_trade` signature differs, adapt the test's dict to the fields the
> handler requires; the production caller is `MT5Worker`, which already populates
> these fields.

- [ ] **Step 5: Commit**

```bash
git add app/api/trades.py tests/unit/test_api_server.py
git commit -m "feat: add recent-trades query for dashboard preview"
```

---

## Task 10: FastAPI app — status/start/stop/logs/trades/focus + static

**Files:**
- Create: `app/api/server.py`
- Test: `tests/unit/test_api_server.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_api_server.py`:

```python
import asyncio

from fastapi.testclient import TestClient

from app.engine_controller import EngineController, EngineState


class _FakeRunner:
    def __init__(self, listen_host="127.0.0.1", listen_port=8080):
        self._stop = asyncio.Event()
    async def serve(self):
        await self._stop.wait()
    def shutdown(self):
        self._stop.set()
    def mt5_connected(self):
        return True
    def tv_connected(self):
        return True


def _client(temp_db_path):
    from app.api.server import create_app
    controller = EngineController(runner_factory=_FakeRunner, listen_port=0)
    app = create_app(controller, focus_callback=lambda: None)
    return TestClient(app), controller


def test_status_endpoint(temp_db_path):
    client, _ = _client(temp_db_path)
    r = client.get("/api/status")
    assert r.status_code == 200
    assert r.json()["engine"] == "stopped"


def test_start_then_stop_endpoints(temp_db_path):
    client, _ = _client(temp_db_path)
    r = client.post("/api/engine/start")
    assert r.status_code == 200
    assert r.json()["engine"] == "running"
    r = client.post("/api/engine/stop")
    assert r.status_code == 200
    assert r.json()["engine"] == "stopped"


def test_start_returns_409_when_proxy_busy(temp_db_path):
    import socket
    from app.api.server import create_app
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0)); s.listen(1)
    busy = s.getsockname()[1]
    try:
        controller = EngineController(runner_factory=_FakeRunner, listen_port=busy)
        client = TestClient(create_app(controller, focus_callback=lambda: None))
        r = client.post("/api/engine/start")
        assert r.status_code == 409
        assert "in use" in r.json()["detail"]
    finally:
        s.close()


def test_focus_endpoint_invokes_callback(temp_db_path):
    from app.api.server import create_app
    hits = []
    controller = EngineController(runner_factory=_FakeRunner, listen_port=0)
    client = TestClient(create_app(controller, focus_callback=lambda: hits.append(1)))
    r = client.post("/api/focus")
    assert r.status_code == 200
    assert hits == [1]
```

- [ ] **Step 2: Run them (fail)**

Run: `pytest tests/unit/test_api_server.py -q`
Expected: FAIL — `app.api.server` / `create_app` missing.

- [ ] **Step 3: Implement the app factory**

Create `app/api/server.py`:

```python
"""FastAPI app: JSON API + static UI for the desktop shell."""
import logging
from pathlib import Path
from typing import Callable, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.engine_controller import EngineController, ProxyPortInUseError
from app.api.logs import read_log_tail
from app.api.trades import recent_trades
from app.paths import get_data_dir

logger = logging.getLogger("ApiServer")

UI_DIR = Path(__file__).parent.parent / "ui"


def _log_path() -> Path:
    return get_data_dir() / "logs" / "tv2mt5.log"


def create_app(controller: EngineController, focus_callback: Optional[Callable] = None) -> FastAPI:
    app = FastAPI(title="TV2MT5 Desktop")

    @app.get("/api/status")
    def get_status():
        return controller.status().to_dict()

    @app.post("/api/engine/start")
    async def start_engine():
        try:
            status = await controller.start()
        except ProxyPortInUseError as e:
            raise HTTPException(status_code=409, detail=str(e))
        return status.to_dict()

    @app.post("/api/engine/stop")
    async def stop_engine():
        return (await controller.stop()).to_dict()

    @app.get("/api/logs")
    def get_logs(after: int = Query(0, ge=0)):
        lines, cursor = read_log_tail(_log_path(), after=after)
        return {"lines": lines, "cursor": cursor}

    @app.get("/api/trades")
    def get_trades(limit: int = Query(10, ge=1, le=200)):
        return {"trades": recent_trades(limit=limit)}

    @app.post("/api/focus")
    def focus():
        if focus_callback is not None:
            focus_callback()
        return {"ok": True}

    @app.get("/")
    def index():
        return FileResponse(UI_DIR / "index.html")

    if UI_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")

    return app
```

- [ ] **Step 4: Run them (pass)**

Run: `pytest tests/unit/test_api_server.py -q`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Commit**

```bash
git add app/api/server.py tests/unit/test_api_server.py
git commit -m "feat: add FastAPI app (status/start/stop/logs/trades/focus + static)"
```

---

## Task 11: UI (Dashboard layout A + Logs + greyed tabs)

**Files:**
- Create: `app/ui/index.html`, `app/ui/styles.css`, `app/ui/app.js`
- Test: `tests/unit/test_api_server.py` (append a serve-index test)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_api_server.py`:

```python
def test_index_is_served(temp_db_path):
    client, _ = _client(temp_db_path)
    r = client.get("/")
    assert r.status_code == 200
    assert "TV2MT5" in r.text
    assert "Dashboard" in r.text
```

- [ ] **Step 2: Run it (fails)**

Run: `pytest tests/unit/test_api_server.py::test_index_is_served -q`
Expected: FAIL — `app/ui/index.html` does not exist yet (FileResponse 404/error).

- [ ] **Step 3: Create `app/ui/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TV2MT5 Desktop</title>
  <link rel="stylesheet" href="/static/styles.css" />
</head>
<body>
  <div class="app">
    <nav class="sidebar">
      <div class="brand">TV2MT5</div>
      <a class="nav-item active" data-view="dashboard">Dashboard</a>
      <a class="nav-item soon">Trades <span>soon</span></a>
      <a class="nav-item soon">Symbols <span>soon</span></a>
      <a class="nav-item soon">Settings <span>soon</span></a>
      <a class="nav-item" data-view="logs">Logs</a>
    </nav>

    <main class="content">
      <section id="view-dashboard" class="view">
        <div class="topbar">
          <span id="state-pill" class="pill stop">● Stopped</span>
          <button id="toggle-btn" class="btn start">▶ Start Copying</button>
        </div>
        <div id="banner" class="banner hidden"></div>
        <div class="cards">
          <div class="card"><div class="lab">TradingView</div><div id="tv-val" class="val">—</div></div>
          <div class="card"><div class="lab">MT5</div><div id="mt5-val" class="val">—</div></div>
          <div class="card"><div class="lab">Proxy</div><div id="proxy-val" class="val">—</div></div>
        </div>
        <div class="panel">
          <div class="lab">RECENT ACTIVITY</div>
          <ul id="recent" class="recent"></ul>
        </div>
      </section>

      <section id="view-logs" class="view hidden">
        <div class="lab">LOGS</div>
        <pre id="logbox" class="logbox"></pre>
      </section>
    </main>
  </div>
  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 4: Create `app/ui/styles.css`**

```css
* { box-sizing: border-box; }
body { margin: 0; font-family: "Segoe UI", system-ui, sans-serif; color: #1f2430; }
.app { display: flex; height: 100vh; }
.sidebar { width: 180px; background: #1f2430; color: #cfd6e4; padding: 14px 0; flex-shrink: 0; }
.brand { font-weight: 700; font-size: 18px; padding: 0 16px 14px; color: #fff; }
.nav-item { display: flex; justify-content: space-between; padding: 9px 16px; cursor: pointer; color: #cfd6e4; text-decoration: none; }
.nav-item.active { background: #2d6cdf; color: #fff; font-weight: 600; }
.nav-item.soon { color: #6b7484; cursor: default; }
.nav-item.soon span { font-size: 10px; text-transform: uppercase; opacity: .7; }
.content { flex: 1; background: #f5f7fa; padding: 18px; overflow: auto; }
.view.hidden, .banner.hidden { display: none; }
.topbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.pill { padding: 4px 12px; border-radius: 14px; font-weight: 600; }
.pill.run { background: #e6f4ea; color: #137333; }
.pill.stop { background: #fce8e6; color: #c5221f; }
.pill.busy { background: #fef7e0; color: #b06000; }
.btn { border: none; border-radius: 5px; padding: 8px 18px; font-weight: 600; color: #fff; cursor: pointer; }
.btn.start { background: #137333; }
.btn.stop { background: #c5221f; }
.banner { background: #fce8e6; color: #c5221f; border-radius: 6px; padding: 10px 12px; margin-bottom: 14px; }
.cards { display: flex; gap: 12px; margin-bottom: 14px; }
.card { flex: 1; background: #fff; border: 1px solid #e1e5ea; border-radius: 8px; padding: 12px; }
.lab { color: #6b7484; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; }
.val { font-weight: 600; margin-top: 4px; }
.dot-on { color: #137333; }
.dot-off { color: #c5221f; }
.panel { background: #fff; border: 1px solid #e1e5ea; border-radius: 8px; padding: 12px; }
.recent { list-style: none; margin: 8px 0 0; padding: 0; font-family: Consolas, monospace; font-size: 12px; }
.recent li { padding: 3px 0; border-bottom: 1px solid #f0f2f5; }
.logbox { background: #11151c; color: #d6dde8; font-family: Consolas, monospace; font-size: 12px; padding: 12px; border-radius: 8px; height: 70vh; overflow: auto; white-space: pre-wrap; }
```

- [ ] **Step 5: Create `app/ui/app.js`**

```javascript
const $ = (id) => document.getElementById(id);
let logCursor = 0;

function dot(on) { return on ? '<span class="dot-on">●</span>' : '<span class="dot-off">○</span>'; }

async function refreshStatus() {
  try {
    const s = await (await fetch('/api/status')).json();
    const pill = $('state-pill'), btn = $('toggle-btn'), banner = $('banner');
    pill.className = 'pill ' + (s.engine === 'running' ? 'run' : (s.engine === 'error' ? 'stop' : (s.engine === 'starting' || s.engine === 'stopping' ? 'busy' : 'stop')));
    pill.textContent = '● ' + s.engine.charAt(0).toUpperCase() + s.engine.slice(1);
    const running = s.engine === 'running';
    btn.textContent = running ? '■ Stop' : '▶ Start Copying';
    btn.className = 'btn ' + (running ? 'stop' : 'start');
    btn.disabled = (s.engine === 'starting' || s.engine === 'stopping');
    $('tv-val').innerHTML = dot(s.tv.connected) + ' ' + (s.tv.account || '—');
    $('mt5-val').innerHTML = dot(s.mt5.connected) + ' ' + (s.mt5.account || '—');
    $('proxy-val').innerHTML = dot(s.proxy.listening) + ' :' + s.proxy.port;
    if (s.error) { banner.textContent = s.error; banner.classList.remove('hidden'); }
    else { banner.classList.add('hidden'); }
  } catch (e) { /* server momentarily unavailable */ }
}

async function refreshTrades() {
  try {
    const d = await (await fetch('/api/trades?limit=10')).json();
    $('recent').innerHTML = (d.trades || []).map(t =>
      `<li>${t.created_at ? t.created_at.slice(11, 19) : ''} ${t.side || ''} ${t.instrument || ''} x${t.quantity || ''} — ${t.status || ''}</li>`
    ).join('') || '<li>No trades yet</li>';
  } catch (e) {}
}

async function refreshLogs() {
  try {
    const d = await (await fetch('/api/logs?after=' + logCursor)).json();
    if (d.lines && d.lines.length) {
      const box = $('logbox');
      box.textContent += (box.textContent ? '\n' : '') + d.lines.join('\n');
      box.scrollTop = box.scrollHeight;
    }
    logCursor = d.cursor;
  } catch (e) {}
}

$('toggle-btn').addEventListener('click', async () => {
  const running = $('toggle-btn').className.includes('stop');
  const url = running ? '/api/engine/stop' : '/api/engine/start';
  const r = await fetch(url, { method: 'POST' });
  if (!r.ok) {
    const j = await r.json().catch(() => ({}));
    const banner = $('banner');
    banner.textContent = j.detail || 'Action failed';
    banner.classList.remove('hidden');
  }
  refreshStatus();
});

document.querySelectorAll('.nav-item[data-view]').forEach(el => {
  el.addEventListener('click', () => {
    document.querySelectorAll('.nav-item[data-view]').forEach(n => n.classList.remove('active'));
    el.classList.add('active');
    const view = el.getAttribute('data-view');
    $('view-dashboard').classList.toggle('hidden', view !== 'dashboard');
    $('view-logs').classList.toggle('hidden', view !== 'logs');
  });
});

setInterval(refreshStatus, 1500);
setInterval(refreshTrades, 3000);
setInterval(refreshLogs, 1500);
refreshStatus(); refreshTrades(); refreshLogs();
```

- [ ] **Step 6: Run the serve-index test (passes) + full suite**

Run: `pytest tests/unit/test_api_server.py -q`
Expected: PASS (including `test_index_is_served`).

Run: `pytest tests/unit -q`
Expected: PASS (all unit tests).

- [ ] **Step 7: Commit**

```bash
git add app/ui/index.html app/ui/styles.css app/ui/app.js tests/unit/test_api_server.py
git commit -m "feat: add desktop UI (dashboard layout A + logs + greyed tabs)"
```

---

## Task 12: Tray icon + menu

**Files:**
- Create: `app/tray.py`

The tray actions call the local API over HTTP (the tray runs on its own thread; the
controller lives in the API loop, so HTTP is the clean cross-thread path).

- [ ] **Step 1: Implement the tray module**

Create `app/tray.py`:

```python
"""System-tray icon (pystray): Start / Stop / Open / Quit. Talks to the local API."""
import logging
import urllib.request

from PIL import Image, ImageDraw
import pystray

from app.singleton import CONTROL_HOST, CONTROL_PORT

logger = logging.getLogger("Tray")


def _api(path: str, method: str = "POST") -> None:
    try:
        req = urllib.request.Request(
            f"http://{CONTROL_HOST}:{CONTROL_PORT}{path}", method=method
        )
        urllib.request.urlopen(req, timeout=2.0).close()
    except Exception as e:  # noqa: BLE001
        logger.info("tray api %s failed: %s", path, e)


def _icon_image() -> Image.Image:
    img = Image.new("RGB", (64, 64), "#1f2430")
    d = ImageDraw.Draw(img)
    d.rectangle([18, 18, 46, 46], fill="#2d6cdf")
    return img


def build_tray(on_open, on_quit) -> "pystray.Icon":
    """Build (but do not run) the tray icon. on_open/on_quit are callables."""
    menu = pystray.Menu(
        pystray.MenuItem("Open", lambda icon, item: on_open()),
        pystray.MenuItem("Start", lambda icon, item: _api("/api/engine/start")),
        pystray.MenuItem("Stop", lambda icon, item: _api("/api/engine/stop")),
        pystray.MenuItem("Quit", lambda icon, item: on_quit(icon)),
    )
    return pystray.Icon("tv2mt5", _icon_image(), "TV2MT5", menu)
```

- [ ] **Step 2: Verify it imports and builds a menu**

Run: `python -c "from app.tray import build_tray; t = build_tray(lambda: None, lambda i: None); print('menu items:', len(list(t.menu)))"`
Expected: prints `menu items: 4` (no window shown; we only build, not run).

- [ ] **Step 3: Commit**

```bash
git add app/tray.py
git commit -m "feat: add system-tray icon (Open/Start/Stop/Quit) wired to the API"
```

---

## Task 13: Desktop orchestration + run.py command

**Files:**
- Create: `app/desktop.py`
- Modify: `run.py`

- [ ] **Step 1: Implement the desktop entrypoint**

Create `app/desktop.py`:

```python
"""Desktop entrypoint: window (main thread) + API/engine loop (thread) + tray (thread).

Process model (Plan 3a):
- main thread runs the pywebview window (WebView2)
- a background thread runs one asyncio loop hosting uvicorn (FastAPI) + the engine
- a tray thread runs the pystray icon
Single-instance guard: bind the control port; if taken, focus the running app and exit.
"""
import logging
import threading

import uvicorn
import webview

from app.engine_controller import EngineController
from app.api.server import create_app
from app.logging_setup import setup_logging  # Plan 1 logging
from app.singleton import (CONTROL_HOST, CONTROL_PORT, acquire_single_instance,
                           focus_running_instance, is_another_instance_running)
from app.tray import build_tray

logger = logging.getLogger("Desktop")

_window = None


def _run_api(controller: EngineController) -> None:
    """Run uvicorn (FastAPI + engine loop) on this thread's own asyncio loop."""
    app = create_app(controller, focus_callback=_focus_window)
    config = uvicorn.Config(app, host=CONTROL_HOST, port=CONTROL_PORT, log_level="warning")
    server = uvicorn.Server(config)
    server.run()  # creates and runs its own asyncio loop on this thread


def _focus_window() -> None:
    if _window is not None:
        try:
            _window.show()
            _window.restore()
        except Exception as e:  # noqa: BLE001
            logger.info("focus window failed: %s", e)


def main() -> None:
    global _window
    setup_logging()

    # Single-instance guard.
    if is_another_instance_running():
        focus_running_instance()
        print("TV2MT5 is already running.")
        return
    lock = acquire_single_instance()
    if lock is None:
        focus_running_instance()
        print("TV2MT5 is already running.")
        return
    # Release the probe socket so uvicorn can bind the port; the window of overlap
    # is tiny and the is_another_instance_running check above already gated us.
    lock.close()

    controller = EngineController()

    api_thread = threading.Thread(target=_run_api, args=(controller,), daemon=True)
    api_thread.start()

    def on_quit(icon):
        try:
            icon.stop()
        finally:
            if _window is not None:
                _window.destroy()

    tray = build_tray(on_open=_focus_window, on_quit=on_quit)
    tray_thread = threading.Thread(target=tray.run, daemon=True)
    tray_thread.start()

    _window = webview.create_window(
        "TV2MT5 Desktop",
        f"http://{CONTROL_HOST}:{CONTROL_PORT}/",
        width=900,
        height=620,
    )

    # Closing the window hides to tray (engine keeps running); Quit (tray) exits.
    def _on_closing():
        _window.hide()
        return False  # veto destroy; just hide

    _window.events.closing += _on_closing
    webview.start()  # blocks on the main thread until the process exits


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add a `desktop` command to `run.py`**

In `run.py`, add this method to the `Runner` class (next to `run_app`):

```python
    def run_desktop(self):
        """Launch the desktop app (window + tray + engine Start/Stop)."""
        subprocess.run([sys.executable, "-m", "app.desktop"])
```

Then register it in the command map where `start` is wired (around original line 159),
adding alongside it:

```python
        'desktop': runner.run_desktop,
```

And add a help entry next to the `start` help line (around original line 89):

```python
            "desktop": "Launch the desktop app (window + tray + Start/Stop)",
```

Add an `app/desktop` module entrypoint shim so `python -m app.desktop` works — create
`app/desktop` invocation via the existing file (it already has `if __name__ == "__main__"`),
so `python -m app.desktop` runs `main()`.

- [ ] **Step 3: Verify the desktop module imports cleanly (no window shown)**

Run: `python -c "import app.desktop; print('desktop import ok')"`
Expected: prints `desktop import ok` (importing must not start the server or open a window).

- [ ] **Step 4: Verify the command is registered**

Run: `python run.py --help` (or `python run.py`)
Expected: `desktop` appears among the commands without error.

- [ ] **Step 5: Commit**

```bash
git add app/desktop.py run.py
git commit -m "feat: add desktop orchestration (window + api/engine thread + tray) and run.py desktop command"
```

- [ ] **Step 6: Manual end-to-end verification (cannot be unit-tested)**

> With the MT5 terminal available and the settings store seeded:
> 1. Run `python -m app.desktop`. A window opens (sidebar + Dashboard) and a tray icon appears.
> 2. Status shows **Stopped**; TV/MT5/Proxy dots reflect not-listening.
> 3. Click **Start Copying** → status flips to **Running**, Proxy dot turns on (:8080),
>    MT5 dot turns on after connect. Place a TradingView trade → it copies to MT5 and
>    appears in **Recent activity**; the **Logs** tab streams the engine log.
> 4. Click **Stop** → status returns to **Stopped**, proxy releases :8080.
> 5. Close the window → it hides to tray; the tray **Open** reopens it.
> 6. With the engine running, launch `python -m app.desktop` again → the second instance
>    focuses the first window and exits (no second engine; no MT5 IPC contention).
> 7. Tray **Quit** → window closes and the process exits cleanly.

---

## Self-Review (completed during planning)

**Spec coverage (Plan 3a):**
- Shared-loop process model (uvicorn + engine one loop; webview main thread; tray thread) → Tasks 10, 13. ✅
- In-loop Start/Stop via `EngineController` → Tasks 3–6. ✅
- `MitmEngineRunner` reuses Plan 1/2 wiring untouched; `run_engine` delegates → Task 6. ✅
- Vanilla HTML/CSS/JS UI, Dashboard layout A, Logs, greyed future tabs → Task 11. ✅
- Polling status/logs/trades → Task 11 (JS `setInterval`) against Task 10 endpoints. ✅
- Single-instance guard (control-port) + best-effort focus → Tasks 7, 13. ✅
- 8080 free-before-Start guard (Plan 2 carry-forward) → Tasks 3–5 (`_port_free`, `ProxyPortInUseError`), Task 10 (409). ✅
- Window close → hide to tray; Quit → exit → Task 13. ✅
- Status fields (engine/tv/mt5/proxy/error) → Task 3 `Status`; mt5/tv connected via runner (Task 6) + MT5Service flag (Task 2). ✅
- Recent-activity = last 10 trades from `trades` table → Tasks 9, 11. ✅
- Logs = tail rotating log → Tasks 8, 10, 11. ✅
- Trade interception/execution unchanged → no task edits `trade_handler`/`interceptor` logic/`mt5_worker` behavior. ✅
- Trades/Symbols/Settings tabs deferred (greyed) → Task 11; full views are Plan 3b. ✅

**Placeholder scan:** No TBD/TODO; every code step shows full code; commands have expected output. ✅

**Type/name consistency:**
- `EngineState`/`Status`/`Status.to_dict()` (Task 3) used identically in Tasks 5, 6, 10. ✅
- `EngineController(runner_factory=..., listen_host=..., listen_port=...)` signature (Task 3) matches the fake-runner injection in Tasks 5, 10 and the default `MitmEngineRunner` wiring (Task 6). ✅
- Runner duck-type `serve()/shutdown()/mt5_connected()/tv_connected()` defined on `MitmEngineRunner` (Task 6) and the test `_FakeRunner`s (Tasks 5, 10); consumed by `EngineController` (Task 5) and `status()` (Task 3). ✅
- `ProxyPortInUseError` raised in `start()` (Task 5) and mapped to 409 in `/api/engine/start` (Task 10). ✅
- `read_log_tail(path, after)->(lines,cursor)` (Task 8) consumed by `/api/logs` (Task 10) and the JS `logCursor` loop (Task 11). ✅
- `recent_trades(limit)` (Task 9) consumed by `/api/trades` (Task 10) and the JS recent loop (Task 11). ✅
- `create_app(controller, focus_callback)` (Task 10) called by `_run_api` (Task 13) and the API tests (Task 10). ✅
- `CONTROL_HOST`/`CONTROL_PORT`/`acquire_single_instance`/`is_another_instance_running`/`focus_running_instance` (Task 7) used by `app/desktop.py` (Task 13) and `app/tray.py` (Task 12). ✅
