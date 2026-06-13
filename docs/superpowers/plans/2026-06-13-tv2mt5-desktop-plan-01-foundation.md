# TV2MT5 Desktop — Plan 1: Foundation (Infra Collapse) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing TradingView→MT5 copier run as a single Python process with no Docker, no PostgreSQL, and no Redis — using an embedded SQLite database and an in-process `asyncio` queue — while preserving all trade-copying behaviour.

**Architecture:** Replace the PostgreSQL connection with a local SQLite file (SQLAlchemy keeps the same `Trade` model and `DatabaseHandler` API). Replace the Redis pub/sub `RedisQueue` with an `InProcQueue` that exposes the same methods but moves messages over an `asyncio.Queue` on the shared event loop. Embed mitmproxy (`DumpMaster`) and the MT5 worker consumer in one `asyncio` loop launched by a new `app/engine.py` supervisor and a `python -m app` entrypoint.

**Tech Stack:** Python 3.11, SQLAlchemy 2.0 (SQLite), mitmproxy 11 (embedded `DumpMaster`), MetaTrader5 API, `asyncio`, pytest.

---

## File Structure

**Create:**
- `app/__init__.py` — marks the new single-process application package.
- `app/__main__.py` — entrypoint: `python -m app` launches the unified engine.
- `app/engine.py` — supervisor that builds + runs mitmproxy and the worker on one loop.
- `app/queue/__init__.py`
- `app/queue/inproc_queue.py` — `InProcQueue`, drop-in replacement for `RedisQueue`.
- `app/paths.py` — resolves the app data directory + SQLite file path.
- `tests/unit/__init__.py`
- `tests/unit/test_inproc_queue.py`
- `tests/unit/test_sqlite_store.py`
- `tests/unit/test_engine_factory.py`
- `tests/conftest.py` — shared pytest fixtures (temp SQLite DB).
- `requirements-dev.txt` — dev/test dependencies.

**Modify:**
- `src/config/database.py` — produce a SQLite `DATABASE_URL` + shared engine/session factory.
- `src/models/database.py` — use the shared engine; drop Postgres pool/retry.
- `src/utils/database_handler.py` — use the shared SQLite session factory (no Postgres URL).
- `src/core/interceptor.py` — accept an injected `TradeHandler` (no behaviour change to parsing).
- `src/core/trade_handler.py` — accept injected `queue` and `db` (default preserves current behaviour).
- `src/workers/mt5_worker.py` — add an in-process init path that reuses an external loop + injected `queue`/`db`.
- `requirements.txt` — remove `psycopg2-binary` and `redis`.

**Delete (in the cleanup task):**
- `docker-compose.yml`
- `src/scripts/clean_redis.py`
- `tests/infrastructure/test_redis.py`

---

## Task 1: Dev dependencies and test scaffolding

**Files:**
- Create: `requirements-dev.txt`
- Create: `tests/unit/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create the dev requirements file**

Create `requirements-dev.txt`:

```text
# Test/dev dependencies for TV2MT5
pytest==8.2.0
pytest-asyncio==0.23.7
```

- [ ] **Step 2: Install dev dependencies**

Run: `pip install -r requirements-dev.txt`
Expected: `pytest` and `pytest-asyncio` install successfully.

- [ ] **Step 3: Create the unit test package marker**

Create `tests/unit/__init__.py` as an empty file (one blank line is fine).

- [ ] **Step 4: Create shared pytest fixtures**

Create `tests/conftest.py`:

```python
"""Shared pytest fixtures for TV2MT5 tests."""
import asyncio
import os
from pathlib import Path

import pytest


@pytest.fixture
def temp_db_path(tmp_path, monkeypatch):
    """Point the app at a throwaway SQLite file for the duration of a test."""
    db_file = tmp_path / "test_tv2mt5.db"
    monkeypatch.setenv("TV2MT5_DB_PATH", str(db_file))
    return db_file


@pytest.fixture
def event_loop():
    """Provide a fresh asyncio event loop per test (pytest-asyncio)."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
```

- [ ] **Step 5: Add pytest configuration**

Create `pytest.ini` in the project root:

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 6: Verify pytest collects with no errors**

Run: `pytest tests/unit -q`
Expected: `no tests ran` (collection succeeds, zero tests yet).

- [ ] **Step 7: Commit**

```bash
git add requirements-dev.txt tests/unit/__init__.py tests/conftest.py pytest.ini
git commit -m "test: add pytest scaffolding and dev requirements"
```

---

## Task 2: App data path resolver

**Files:**
- Create: `app/__init__.py`
- Create: `app/paths.py`
- Test: `tests/unit/test_sqlite_store.py` (path portion)

- [ ] **Step 1: Create the app package marker**

Create `app/__init__.py`:

```python
"""TV2MT5 single-process desktop application package."""
```

- [ ] **Step 2: Write the failing test for the path resolver**

Create `tests/unit/test_sqlite_store.py`:

```python
import os
from pathlib import Path

from app.paths import get_db_path, get_data_dir


def test_db_path_honours_env_override(monkeypatch, tmp_path):
    target = tmp_path / "custom.db"
    monkeypatch.setenv("TV2MT5_DB_PATH", str(target))
    assert get_db_path() == target


def test_data_dir_is_created(monkeypatch, tmp_path):
    monkeypatch.setenv("TV2MT5_DB_PATH", str(tmp_path / "sub" / "db.sqlite"))
    data_dir = get_data_dir()
    assert data_dir.exists()
    assert data_dir == (tmp_path / "sub")
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `pytest tests/unit/test_sqlite_store.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.paths'`.

- [ ] **Step 4: Implement the path resolver**

Create `app/paths.py`:

```python
"""Resolve where TV2MT5 stores its data (SQLite DB, logs)."""
import os
from pathlib import Path

APP_DIR_NAME = "TV2MT5"


def get_db_path() -> Path:
    """Return the SQLite database file path.

    Honours the TV2MT5_DB_PATH env override (used by tests and packaging).
    Defaults to %APPDATA%\\TV2MT5\\tv2mt5.db on Windows, else ~/.tv2mt5/tv2mt5.db.
    """
    override = os.getenv("TV2MT5_DB_PATH")
    if override:
        return Path(override)
    base = os.getenv("APPDATA") or str(Path.home())
    return Path(base) / APP_DIR_NAME / "tv2mt5.db"


def get_data_dir() -> Path:
    """Return (and create) the directory that holds the SQLite DB."""
    data_dir = get_db_path().parent
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/unit/test_sqlite_store.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add app/__init__.py app/paths.py tests/unit/test_sqlite_store.py
git commit -m "feat: add app data path resolver"
```

---

## Task 3: SQLite database config + shared engine

**Files:**
- Modify: `src/config/database.py`
- Test: `tests/unit/test_sqlite_store.py` (engine portion)

- [ ] **Step 1: Write the failing test for the SQLite engine factory**

Append to `tests/unit/test_sqlite_store.py`:

```python
from sqlalchemy import text

from app.paths import get_db_path  # noqa: E402


def test_get_engine_creates_sqlite_file(temp_db_path):
    from src.config.database import get_engine, get_session_factory

    engine = get_engine()
    assert engine.url.get_backend_name() == "sqlite"

    Session = get_session_factory()
    session = Session()
    try:
        assert session.execute(text("SELECT 1")).scalar() == 1
    finally:
        session.close()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/test_sqlite_store.py::test_get_engine_creates_sqlite_file -q`
Expected: FAIL — `src.config.database` currently builds a PostgreSQL URL from `DB_*` env vars and has no `get_engine`/`get_session_factory`.

- [ ] **Step 3: Replace `src/config/database.py` with SQLite config**

Replace the entire contents of `src/config/database.py` with:

```python
"""SQLite database configuration and shared engine/session factory.

This module replaces the previous PostgreSQL configuration. A single SQLite
file (see app.paths.get_db_path) backs the whole application. The engine is
created lazily so tests can point TV2MT5_DB_PATH at a temp file first.
"""
import logging

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.paths import get_data_dir, get_db_path

logger = logging.getLogger(__name__)

_engine: Engine | None = None
_SessionFactory: sessionmaker | None = None


def _build_url() -> str:
    get_data_dir()  # ensure parent directory exists
    db_path = get_db_path().as_posix()
    return f"sqlite:///{db_path}"


def get_engine() -> Engine:
    """Return the process-wide SQLite engine, creating it on first use."""
    global _engine
    if _engine is None:
        url = _build_url()
        logger.info("Opening SQLite database at %s", url)
        _engine = create_engine(
            url,
            future=True,
            # SQLite + our threadpool executor: connections cross threads.
            connect_args={"check_same_thread": False},
        )
    return _engine


def get_session_factory() -> sessionmaker:
    """Return a sessionmaker bound to the shared SQLite engine."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(
            autocommit=False, autoflush=False, bind=get_engine(), future=True
        )
    return _SessionFactory


# Backwards-compatible name used by src/models/database.py.
DATABASE_URL = _build_url()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/unit/test_sqlite_store.py::test_get_engine_creates_sqlite_file -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/config/database.py tests/unit/test_sqlite_store.py
git commit -m "feat: replace postgres config with sqlite engine factory"
```

---

## Task 4: Trade model on the shared SQLite engine

**Files:**
- Modify: `src/models/database.py`
- Test: `tests/unit/test_sqlite_store.py` (model portion)

- [ ] **Step 1: Write the failing test for table creation**

Append to `tests/unit/test_sqlite_store.py`:

```python
def test_init_db_creates_trades_table(temp_db_path):
    from sqlalchemy import inspect

    from src.config.database import get_engine
    from src.models.database import init_db

    init_db()
    inspector = inspect(get_engine())
    assert "trades" in inspector.get_table_names()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/test_sqlite_store.py::test_init_db_creates_trades_table -q`
Expected: FAIL — `src/models/database.py` builds its own PostgreSQL engine at import time (`create_db_engine()`), which raises against SQLite settings.

- [ ] **Step 3: Update `src/models/database.py` to use the shared engine**

Replace the top of `src/models/database.py` (the imports through the `engine`/`SessionLocal`/`Base` setup, i.e. original lines 1–45) with:

```python
import logging
from datetime import datetime

from sqlalchemy import (JSON, Boolean, Column, DateTime, Integer, Numeric,
                        String, Text)
from sqlalchemy.orm import declarative_base

from src.config.database import get_engine, get_session_factory

logger = logging.getLogger(__name__)

# Shared SQLite engine + session factory (see src/config/database.py).
engine = get_engine()
SessionLocal = get_session_factory()

# Create base class for declarative models
Base = declarative_base()
```

Leave the `class Trade(Base):` definition (original lines 47–94) **unchanged** —
SQLAlchemy's `JSON`, `Numeric`, `Boolean`, and `DateTime` column types all work
on SQLite.

- [ ] **Step 4: Confirm `init_db()` still references the shared engine**

The existing `init_db()` body (`Base.metadata.create_all(bind=engine)`) is correct
as-is because `engine` is now the shared SQLite engine. No change needed.

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/unit/test_sqlite_store.py::test_init_db_creates_trades_table -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/models/database.py tests/unit/test_sqlite_store.py
git commit -m "feat: bind Trade model to shared sqlite engine"
```

---

## Task 5: DatabaseHandler on SQLite (round-trip)

**Files:**
- Modify: `src/utils/database_handler.py`
- Test: `tests/unit/test_sqlite_store.py` (handler portion)

- [ ] **Step 1: Write the failing async round-trip test**

Append to `tests/unit/test_sqlite_store.py`:

```python
import asyncio  # noqa: E402
from datetime import datetime  # noqa: E402


async def test_database_handler_save_and_get(temp_db_path):
    from src.models.database import init_db
    from src.utils.database_handler import DatabaseHandler

    init_db()
    db = DatabaseHandler()

    trade_data = {
        "trade_id": "TV_TEST_1",
        "order_id": "O1",
        "instrument": "EURUSD",
        "side": "buy",
        "quantity": "0.10",
        "type": "market",
        "ask_price": "1.1000",
        "bid_price": "1.0999",
        "take_profit": None,
        "stop_loss": None,
        "status": "pending",
        "tv_request": {"raw": "req"},
        "tv_response": {"raw": "resp"},
        "created_at": datetime.utcnow(),
    }

    await db.async_save_trade(trade_data)
    fetched = await db.async_get_trade("TV_TEST_1")

    assert fetched is not None
    assert fetched["instrument"] == "EURUSD"
    assert fetched["side"] == "buy"
    db.cleanup()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/test_sqlite_store.py::test_database_handler_save_and_get -q`
Expected: FAIL — `DatabaseHandler.__init__` builds a PostgreSQL URL and creates a `QueuePool` engine.

- [ ] **Step 3: Update `DatabaseHandler.__init__` to use the shared factory**

In `src/utils/database_handler.py`, replace the imports block (original lines 1–18)
with:

```python
# utils/database_handler.py

import asyncio
import logging
import traceback
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import text, update

from src.config.database import get_session_factory
from src.models.database import Trade

logger = logging.getLogger('DatabaseHandler')
```

Then replace the `__init__` method (original lines 21–61) with:

```python
    def __init__(self):
        try:
            # Shared SQLite session factory (see src/config/database.py).
            self.SessionLocal = get_session_factory()

            # Event loop for run_in_executor-based async wrappers.
            self.loop = asyncio.get_event_loop()

            # Test connection
            self._test_connection()

        except Exception as e:
            logger.error(f"Error initializing DatabaseHandler: {e}")
            logger.error(traceback.format_exc())
            raise
```

- [ ] **Step 4: Update `cleanup()` to not dispose a shared engine it no longer owns**

Replace the `cleanup` method (original lines 198–206) with:

```python
    def cleanup(self):
        """Release this handler's scoped session; the engine is process-shared."""
        try:
            self.SessionLocal.remove()
        except Exception:
            # remove() only exists on scoped_session; plain sessionmaker has no-op.
            pass
        logger.info("DatabaseHandler cleaned up")
```

Leave every other method (`get_db`, `save_trade`, `update_trade_status`, `get_trade`,
and all `async_*` methods) unchanged — they only use `self.SessionLocal` and the
`Trade` model, both of which now point at SQLite.

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/unit/test_sqlite_store.py::test_database_handler_save_and_get -q`
Expected: PASS.

- [ ] **Step 6: Run the whole SQLite test file**

Run: `pytest tests/unit/test_sqlite_store.py -q`
Expected: PASS (all tests in the file).

- [ ] **Step 7: Commit**

```bash
git add src/utils/database_handler.py tests/unit/test_sqlite_store.py
git commit -m "feat: run DatabaseHandler on shared sqlite session factory"
```

---

## Task 6: InProcQueue (drop-in for RedisQueue)

**Files:**
- Create: `app/queue/__init__.py`
- Create: `app/queue/inproc_queue.py`
- Test: `tests/unit/test_inproc_queue.py`

- [ ] **Step 1: Create the queue package marker**

Create `app/queue/__init__.py`:

```python
"""In-process message queue (replaces Redis pub/sub)."""
```

- [ ] **Step 2: Write the failing test for push→consume round-trip**

Create `tests/unit/test_inproc_queue.py`:

```python
import asyncio

from app.queue.inproc_queue import InProcQueue


async def test_push_then_consume_delivers_trade():
    queue = InProcQueue()
    received = []

    async def callback(msg_type, message):
        received.append((msg_type, message))

    queue.subscribe(callback)
    trade_id = await queue.async_push_trade({"trade_id": "T1", "instrument": "EURUSD"})

    # let the consumer task run
    await asyncio.sleep(0.05)

    assert trade_id == "T1"
    assert len(received) == 1
    msg_type, message = received[0]
    assert msg_type == "trade"
    assert message["data"]["instrument"] == "EURUSD"
    queue.cleanup()


async def test_push_generates_trade_id_when_missing():
    queue = InProcQueue()
    trade_id = await queue.async_push_trade({"instrument": "XAUUSD"})
    assert trade_id.startswith("trade_")
    queue.cleanup()


async def test_get_queue_status_reports_pending_count():
    queue = InProcQueue()
    await queue.async_push_trade({"trade_id": "T2"})
    status = queue.get_queue_status()
    assert status["pending"] >= 0
    queue.cleanup()
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `pytest tests/unit/test_inproc_queue.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.queue.inproc_queue'`.

- [ ] **Step 4: Implement `InProcQueue`**

Create `app/queue/inproc_queue.py`:

```python
"""In-process asyncio queue that mirrors the RedisQueue public API.

RedisQueue delivered messages to a callback as (msg_type, message) where, for
trades, message == {"id", "data": <trade_data>, "timestamp"}. InProcQueue keeps
that exact shape so TradeHandler and MT5Worker need no changes beyond which
queue object they are handed.
"""
import asyncio
import logging
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional, Union

logger = logging.getLogger('InProcQueue')


class InProcQueue:
    def __init__(self) -> None:
        self.logger = logging.getLogger('InProcQueue')
        self._queue: asyncio.Queue = asyncio.Queue()
        self._callback: Optional[Union[Callable, Awaitable]] = None
        self._consumer_task: Optional[asyncio.Task] = None

    async def async_push_trade(self, trade_data: Dict[str, Any]) -> str:
        """Enqueue a trade for the worker. Returns the trade id."""
        trade_id = trade_data.get('trade_id') or f"trade_{datetime.now().timestamp()}"
        if isinstance(trade_data, dict) and 'trade_id' not in trade_data:
            trade_data['trade_id'] = trade_id
        message = {
            'id': trade_id,
            'data': trade_data,
            'timestamp': datetime.now().isoformat(),
        }
        await self._queue.put(('trade', message))
        self.logger.info(f"Trade {trade_id} enqueued")
        return trade_id

    def push_trade(self, trade_data: Dict[str, Any]) -> str:
        """Synchronous enqueue helper (schedules onto the running loop)."""
        trade_id = trade_data.get('trade_id') or f"trade_{datetime.now().timestamp()}"
        if isinstance(trade_data, dict) and 'trade_id' not in trade_data:
            trade_data['trade_id'] = trade_id
        message = {
            'id': trade_id,
            'data': trade_data,
            'timestamp': datetime.now().isoformat(),
        }
        self._queue.put_nowait(('trade', message))
        return trade_id

    def subscribe(self, callback: Union[Callable, Awaitable]) -> None:
        """Register the message handler and start the consumer task."""
        self._callback = callback
        self._consumer_task = asyncio.ensure_future(self._consume())

    async def _consume(self) -> None:
        while True:
            msg_type, message = await self._queue.get()
            try:
                if self._callback is None:
                    continue
                if asyncio.iscoroutinefunction(self._callback):
                    await self._callback(msg_type, message)
                else:
                    self._callback(msg_type, message)
            except Exception as e:
                self.logger.error(f"Error handling {msg_type} message: {e}")
            finally:
                self._queue.task_done()

    # --- API-compatibility shims (RedisQueue had these) ---

    def publish_status(self, message: str) -> None:
        self.logger.info(f"Status: {message.strip()}")

    async def async_publish_status(self, message: str) -> None:
        self.publish_status(message)

    def get_queue_status(self) -> Dict[str, int]:
        return {'pending': self._queue.qsize()}

    async def async_get_queue_status(self) -> Dict[str, int]:
        return self.get_queue_status()

    def cleanup(self) -> None:
        """Cancel the consumer task."""
        if self._consumer_task is not None:
            self._consumer_task.cancel()
            self._consumer_task = None
        self.logger.info("InProcQueue cleaned up")
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/unit/test_inproc_queue.py -q`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add app/queue/__init__.py app/queue/inproc_queue.py tests/unit/test_inproc_queue.py
git commit -m "feat: add in-process queue replacing redis pub/sub"
```

---

## Task 7: Inject queue + db into TradeHandler

**Files:**
- Modify: `src/core/trade_handler.py`
- Test: `tests/unit/test_inproc_queue.py` (handler-injection portion)

- [ ] **Step 1: Write the failing test for dependency injection**

Append to `tests/unit/test_inproc_queue.py`:

```python
async def test_trade_handler_accepts_injected_queue(temp_db_path):
    from src.models.database import init_db
    from src.utils.database_handler import DatabaseHandler
    from src.core.trade_handler import TradeHandler

    init_db()
    queue = InProcQueue()
    db = DatabaseHandler()

    handler = TradeHandler(queue=queue, db=db)
    assert handler.queue is queue
    assert handler.db is db
    queue.cleanup()
    db.cleanup()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/test_inproc_queue.py::test_trade_handler_accepts_injected_queue -q`
Expected: FAIL — `TradeHandler.__init__` takes no arguments and constructs `RedisQueue()` itself.

- [ ] **Step 3: Update `TradeHandler.__init__` for injection**

In `src/core/trade_handler.py`, replace the import line
`from src.utils.queue_handler import RedisQueue` (original line 9) with:

```python
from app.queue.inproc_queue import InProcQueue
```

Then replace `__init__` (original lines 19–23) with:

```python
    def __init__(self, queue=None, db=None):
        self.db = db if db is not None else DatabaseHandler()
        self.queue = queue if queue is not None else InProcQueue()
        self.pending_orders = {}  # Track order->execution mapping
        self.loop = asyncio.get_event_loop()
```

No other lines change — every `await self.queue.async_push_trade(...)` and
`await self.db.async_*` call already matches the `InProcQueue`/`DatabaseHandler` APIs.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/unit/test_inproc_queue.py::test_trade_handler_accepts_injected_queue -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/core/trade_handler.py tests/unit/test_inproc_queue.py
git commit -m "refactor: inject queue and db into TradeHandler"
```

---

## Task 8: Inject TradeHandler into the interceptor

**Files:**
- Modify: `src/core/interceptor.py`
- Test: `tests/unit/test_engine_factory.py` (interceptor portion)

- [ ] **Step 1: Create the engine-factory test file with the interceptor test**

Create `tests/unit/test_engine_factory.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/test_engine_factory.py::test_interceptor_accepts_injected_handler -q`
Expected: FAIL — `TradingViewInterceptor.__init__` takes no arguments and always builds its own `TradeHandler` + runs instrument sync.

- [ ] **Step 3: Update the interceptor constructor for injection**

In `src/core/interceptor.py`, replace `__new__`/`__init__` (original lines 31–51) with:

```python
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(TradingViewInterceptor, cls).__new__(cls)
        return cls._instance

    def __init__(self, trade_handler=None, sync_instruments=True):
        if not self._initialized:  # Only initialize once
            self.base_path = f"{TV_BROKER_URL}/accounts/{TV_ACCOUNT_ID}"
            self.trade_handler = trade_handler if trade_handler is not None else TradeHandler()
            self.token_manager = GLOBAL_TOKEN_MANAGER
            if sync_instruments:
                self._sync_instruments_sync()

            broker_url = os.getenv('TV_BROKER_URL', 'Unknown Broker')
            account_id = os.getenv('TV_ACCOUNT_ID', 'Unknown Account')

            print("\n🚀 Trade interceptor initialized")
            print("👀 Watching for trades...\n")
            print(f"✅ TradingView Connected: {account_id} ({broker_url})")

            self._initialized = True
```

Leave the module-level `addons = [TradingViewInterceptor()]` line (original line 258)
unchanged for now — the embedded engine (Task 9) constructs its own instance and
does not import this module as a mitmproxy script.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/unit/test_engine_factory.py::test_interceptor_accepts_injected_handler -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/core/interceptor.py tests/unit/test_engine_factory.py
git commit -m "refactor: allow injecting TradeHandler into interceptor"
```

---

## Task 9: mitmproxy master factory (embeddable, testable)

**Files:**
- Create: `app/engine.py`
- Test: `tests/unit/test_engine_factory.py` (master-factory portion)

- [ ] **Step 1: Write the failing test for the master factory**

Append to `tests/unit/test_engine_factory.py`. NOTE: the test is `async` because
mitmproxy 11's `Master.__init__` calls `asyncio.get_running_loop()` (and creates an
`asyncio.Event`) at construction time, so a `DumpMaster` can only be built inside a
running event loop. This matches production: Task 11 calls `build_master` from inside
the already-running loop of `run_engine`. `build_master` itself stays synchronous.

```python
async def test_build_master_configures_listen_options(monkeypatch):
    monkeypatch.setenv("TV_BROKER_URL", "broker.example.com")
    monkeypatch.setenv("TV_ACCOUNT_ID", "999")

    from app.engine import build_master

    class _Addon:
        pass

    master = build_master(_Addon(), listen_host="127.0.0.1", listen_port=8081)
    assert master.options.listen_host == "127.0.0.1"
    assert master.options.listen_port == 8081
    assert master.options.ssl_insecure is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/test_engine_factory.py::test_build_master_configures_listen_options -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.engine'`.

- [ ] **Step 3: Implement `build_master` in `app/engine.py`**

Create `app/engine.py`:

```python
"""Single-process supervisor: embeds mitmproxy + the MT5 worker on one loop."""
import asyncio
import logging

from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster

logger = logging.getLogger('Engine')


def build_master(addon, listen_host: str = "127.0.0.1", listen_port: int = 8080) -> DumpMaster:
    """Build an embedded mitmproxy DumpMaster with our interceptor addon.

    Returns the configured master without running it, so it is unit-testable.
    MUST be called from within a running asyncio event loop: mitmproxy 11's
    Master.__init__ calls asyncio.get_running_loop() at construction. Task 11's
    run_engine() satisfies this (it is async); the unit test is async for the
    same reason.
    """
    opts = Options(
        listen_host=listen_host,
        listen_port=listen_port,
        ssl_insecure=True,
        mode=["regular"],
    )
    master = DumpMaster(opts, with_termlog=False, with_dumper=False)
    master.addons.add(addon)
    return master
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/unit/test_engine_factory.py::test_build_master_configures_listen_options -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/engine.py tests/unit/test_engine_factory.py
git commit -m "feat: add embeddable mitmproxy master factory"
```

---

## Task 10: Worker in-process init path

**Files:**
- Modify: `src/workers/mt5_worker.py`
- Test: `tests/unit/test_engine_factory.py` (worker-init portion)

- [ ] **Step 1: Write the failing test for in-process worker init**

Append to `tests/unit/test_engine_factory.py`:

```python
import asyncio  # noqa: E402


async def test_worker_inproc_init_uses_injected_queue_and_db(temp_db_path, monkeypatch):
    monkeypatch.setenv("MT5_ACCOUNT", "123")
    monkeypatch.setenv("MT5_PASSWORD", "pw")
    monkeypatch.setenv("MT5_SERVER", "Demo")

    from src.models.database import init_db
    from src.utils.database_handler import DatabaseHandler
    from app.queue.inproc_queue import InProcQueue
    from src.workers.mt5_worker import MT5Worker

    init_db()
    queue = InProcQueue()
    db = DatabaseHandler()

    worker = MT5Worker()
    worker.init_inproc(loop=asyncio.get_event_loop(), queue=queue, db=db)

    assert worker.queue is queue
    assert worker.db is db
    assert worker.loop is asyncio.get_event_loop()
    queue.cleanup()
    db.cleanup()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/test_engine_factory.py::test_worker_inproc_init_uses_injected_queue_and_db -q`
Expected: FAIL — `MT5Worker` has no `init_inproc` method.

- [ ] **Step 3: Add `init_inproc` to `MT5Worker`**

In `src/workers/mt5_worker.py`, replace the import line
`from src.utils.queue_handler import RedisQueue` (original line 15) with:

```python
from app.queue.inproc_queue import InProcQueue
```

Then add this method immediately after the existing `initialize` method (i.e. after
original line 62, before `_initialize_positions`):

```python
    def init_inproc(self, loop, queue, db):
        """Initialize the worker to share an existing event loop, queue, and db.

        Used by app/engine.py so the proxy and worker run on one loop. Unlike
        initialize(), this does NOT create a new event loop or its own queue/db.
        """
        self.loop = loop
        self.queue = queue
        self.queue.loop = loop
        self.db = db

        self.mt5 = MT5Service(
            account=MT5_CONFIG['account'],
            password=MT5_CONFIG['password'],
            server=MT5_CONFIG['server'],
            db_handler=self.db,
        )
        self.mt5.set_loop(self.loop)

        self.tv_service = TradingViewService(
            token_manager=GLOBAL_TOKEN_MANAGER
        )
```

Leave the existing `initialize`, `handle_message`, `process_trade`, and all `_handle_*`
methods unchanged — `handle_message` already reads `data['data']`, which matches the
`InProcQueue` message shape.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/unit/test_engine_factory.py::test_worker_inproc_init_uses_injected_queue_and_db -q`
Expected: PASS.

> Note: this test does not connect to MT5; it only verifies wiring. `MT5Service`
> construction does not open the terminal (that happens in `async_initialize`).

- [ ] **Step 5: Commit**

```bash
git add src/workers/mt5_worker.py tests/unit/test_engine_factory.py
git commit -m "feat: add in-process init path to MT5Worker"
```

---

## Task 11: Unified engine entrypoint

**Files:**
- Modify: `app/engine.py`
- Create: `app/__main__.py`

- [ ] **Step 1: Add the `run_engine` coroutine to `app/engine.py`**

Append to `app/engine.py`:

```python
async def run_engine(listen_host: str = "127.0.0.1", listen_port: int = 8080) -> None:
    """Wire SQLite + queue + worker + interceptor onto one loop and run.

    This is the single-process replacement for the old two-terminal
    (start_proxy.py + start_worker.py) setup. No Docker, Redis, or Postgres.
    """
    # Local imports so unit tests can import build_master without these deps.
    from src.models.database import init_db
    from src.utils.database_handler import DatabaseHandler
    from src.core.trade_handler import TradeHandler
    from src.core.interceptor import TradingViewInterceptor
    from src.workers.mt5_worker import MT5Worker
    from app.queue.inproc_queue import InProcQueue

    init_db()

    loop = asyncio.get_event_loop()
    queue = InProcQueue()
    db = DatabaseHandler()

    # Shared trade handler used by the interceptor; pushes onto the queue.
    trade_handler = TradeHandler(queue=queue, db=db)

    # Worker consumes from the same queue on the same loop.
    worker = MT5Worker()
    worker.init_inproc(loop=loop, queue=queue, db=db)
    queue.subscribe(worker.handle_message)

    # Interceptor addon shares the trade handler.
    TradingViewInterceptor._instance = None
    TradingViewInterceptor._initialized = False
    interceptor = TradingViewInterceptor(trade_handler=trade_handler)

    master = build_master(interceptor, listen_host=listen_host, listen_port=listen_port)

    # Worker's MT5 position-monitor loop + the proxy run concurrently.
    worker_task = asyncio.create_task(worker.run_async())
    try:
        logger.info("Engine starting: proxy on %s:%s", listen_host, listen_port)
        await master.run()
    finally:
        worker.running = False
        worker_task.cancel()
        queue.cleanup()
        db.cleanup()
        logger.info("Engine stopped")
```

- [ ] **Step 2: Create the module entrypoint**

Create `app/__main__.py`:

```python
"""`python -m app` — launch the single-process TV2MT5 engine."""
import asyncio
import logging

from app.engine import run_engine

logging.basicConfig(level=logging.INFO, format="%(message)s")


def main() -> None:
    try:
        asyncio.run(run_engine())
    except KeyboardInterrupt:
        print("\n⛔ Shutdown requested...")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Verify the engine module imports cleanly**

Run: `python -c "import app.engine; print('ok')"`
Expected: prints `ok` (no import errors).

- [ ] **Step 4: Verify the full unit suite still passes**

Run: `pytest tests/unit -q`
Expected: PASS (all tests across the three unit files).

- [ ] **Step 5: Commit**

```bash
git add app/engine.py app/__main__.py
git commit -m "feat: add unified single-process engine entrypoint"
```

---

## Task 12: Update run.py and remove Docker/Redis/Postgres artifacts

**Files:**
- Modify: `run.py`
- Modify: `requirements.txt`
- Delete: `docker-compose.yml`, `src/scripts/clean_redis.py`, `tests/infrastructure/test_redis.py`

- [ ] **Step 1: Add a `start` command to `run.py`**

In `run.py`, add this method to the `Runner` class (next to `run_proxy`/`run_worker`):

```python
    def run_app(self):
        """Start the unified single-process engine (no Docker/Redis/Postgres)."""
        subprocess.run([sys.executable, "-m", "app"])
```

Then register it in the argument parser where the existing commands are wired
(add alongside `proxy`/`worker`): map the CLI command `start` to `self.run_app()`.

- [ ] **Step 2: Verify the new command is recognised**

Run: `python run.py start --help` (or `python run.py --help`)
Expected: `start` appears in the available commands without error.

> Manual end-to-end (cannot be unit-tested here): with the MT5 terminal running
> and `.env` populated, `python run.py start` should print the interceptor and
> worker banners, and a trade placed in TradingView should appear in MT5 — exactly
> as the old two-terminal flow did, but from one process and with no Docker running.

- [ ] **Step 3: Remove Postgres + Redis from `requirements.txt`**

In `requirements.txt`, delete these two lines:

```text
psycopg2-binary==2.9.9
redis==5.0.1
```

Leave `sqlalchemy==2.0.27` and all other entries.

- [ ] **Step 4: Delete the obsolete infrastructure files**

```bash
git rm docker-compose.yml src/scripts/clean_redis.py tests/infrastructure/test_redis.py
```

- [ ] **Step 5: Confirm nothing still imports the removed modules**

Run: `grep -rn "import redis\|RedisQueue\|psycopg2\|docker-compose" src app run.py`
Expected: no matches in `src/`, `app/`, or `run.py` (matches only in docs are fine).

> If `RedisQueue` still appears in `src/utils/queue_handler.py`, that file is now
> dead code. Leave it for Plan 2's cleanup OR delete it now if `grep` shows nothing
> else imports it.

- [ ] **Step 6: Run the full unit suite one more time**

Run: `pytest tests/unit -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add run.py requirements.txt
git commit -m "chore: add start command, drop docker/redis/postgres deps"
```

---

## Self-Review (completed during planning)

**Spec coverage (Plan 1 scope only):**
- "PostgreSQL → SQLite" → Tasks 3–5. ✅
- "Redis pub/sub → in-process asyncio queue" → Tasks 6–7. ✅
- "Two terminals → one process" → Tasks 9–12. ✅
- "Cut Docker, docker-compose, PostgreSQL, Redis, 20-connection pool" → Task 12 + Task 3 (pool removed). ✅
- App data in `%APPDATA%\TV2MT5` → Task 2. ✅
- Settings UI, broker adapter, wizard, seams, packaging → **out of scope for Plan 1** (Plans 2–6 per roadmap). ✅

**Placeholder scan:** No TBD/TODO/"add error handling" placeholders; every code step shows full code. ✅

**Type/name consistency:**
- `InProcQueue` methods (`async_push_trade`, `subscribe`, `publish_status`,
  `get_queue_status`, `cleanup`) match the `RedisQueue` names that `TradeHandler`
  and `MT5Worker` call. ✅
- Message shape `{"id","data","timestamp"}` consumed by `MT5Worker.handle_message`
  (`data['data']`) matches what `InProcQueue` produces. ✅
- `get_engine`/`get_session_factory` defined in Task 3 and used in Tasks 4–5. ✅
- `init_inproc(loop, queue, db)` defined in Task 10 and called with the same
  signature in Task 11. ✅
- `build_master(addon, listen_host, listen_port)` defined in Task 9 and called the
  same way in Task 11. ✅
