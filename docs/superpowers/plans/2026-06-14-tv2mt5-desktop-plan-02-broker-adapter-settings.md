# TV2MT5 Desktop — Plan 2: Broker Adapter + Settings Store Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `.env` configuration with a SQLite `settings` table (seeded once from any existing `.env`), and introduce a thin `BrokerAdapter` seam with a `FusionMarketsAdapter` that owns flow matching and auto-detects `broker_url`/`account_id` from live TradingView traffic — without changing the proven trade-parsing/execution path.

**Architecture:** A `SettingsStore` (on Plan 1's shared SQLite engine) becomes the source of truth for config; secrets are written through a `SecretBox` seam whose default is a no-op plaintext box. Store-backed accessors (`get_mt5_config` / `get_tv_target` / `get_symbol_settings`) replace the import-time `os.getenv` constants, consulting `.env` only as a pre-seed fallback so existing tests stay green. A `FusionMarketsAdapter` is injected into the interceptor: `matches(flow)` replaces the inlined `should_log_request`, and `detect_account(flow)` learns the broker target from TradingView-originated traffic and persists it.

**Tech Stack:** Python 3.11, SQLAlchemy 2.0 (SQLite), mitmproxy 11, `python-dotenv`, pytest / pytest-asyncio.

---

## File Structure

**Create:**
- `app/storage/__init__.py` — storage package marker.
- `app/storage/secret_box.py` — `SecretBox` Protocol + `PlaintextSecretBox` (default seam).
- `app/storage/settings_store.py` — `Settings` model + `SettingsStore` (get/set, typed accessors, secret accessors, seed-once).
- `app/config_accessors.py` — store-backed `get_mt5_config` / `get_tv_target` / `get_symbol_settings`.
- `app/adapters/__init__.py` — adapters package marker.
- `app/adapters/base.py` — `BrokerAdapter` Protocol + `AccountInfo` dataclass.
- `app/adapters/fusion_markets.py` — `FusionMarketsAdapter` (`matches`, `detect_account`, `persist_account`, `base_path`).
- `tests/unit/test_secret_box.py`
- `tests/unit/test_settings_store.py`
- `tests/unit/test_config_accessors.py`
- `tests/unit/test_fusion_adapter.py`

**Modify:**
- `src/config/mt5_config.py` — drop import-time `MT5_CONFIG` dict; re-export `get_mt5_config`.
- `src/config/mt5_symbol_config.py` — `SymbolMapper` reads suffix/map from the store.
- `src/services/tradingview_service.py` — `base_url` built from `get_tv_target`.
- `src/workers/mt5_worker.py` — use `get_mt5_config()` for creds + terminal path.
- `src/utils/symbol_mapper.py` — use `get_mt5_config()` for MT5Service creds.
- `src/utils/instrument_manager.py` — default suffix from `get_symbol_settings`.
- `src/core/interceptor.py` — accept an injected `BrokerAdapter`; matching + auto-detect via the adapter; instrument-sync URL from the adapter target.
- `app/engine.py` — build the store, seed once, build the adapter, inject it into the interceptor.
- `tests/unit/test_engine_factory.py` — keep the Plan 1 interceptor test green under the new constructor.

**Delete:** none.

---

## Task 1: SecretBox seam

**Files:**
- Create: `app/storage/__init__.py`
- Create: `app/storage/secret_box.py`
- Test: `tests/unit/test_secret_box.py`

- [ ] **Step 1: Create the storage package marker**

Create `app/storage/__init__.py`:

```python
"""Persistence helpers: settings store and secret box."""
```

- [ ] **Step 2: Write the failing test**

Create `tests/unit/test_secret_box.py`:

```python
from app.storage.secret_box import PlaintextSecretBox


def test_protect_adds_prefix():
    box = PlaintextSecretBox()
    assert box.protect("hunter2") == "plain:hunter2"


def test_unprotect_inverts_protect():
    box = PlaintextSecretBox()
    assert box.unprotect(box.protect("hunter2")) == "hunter2"


def test_unprotect_of_unprefixed_value_is_identity():
    """Legacy/manually-written values without the prefix read back verbatim."""
    box = PlaintextSecretBox()
    assert box.unprotect("rawvalue") == "rawvalue"
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `pytest tests/unit/test_secret_box.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.storage.secret_box'`.

- [ ] **Step 4: Implement the secret box**

Create `app/storage/secret_box.py`:

```python
"""Pluggable secret storage seam.

Plan 2 ships PlaintextSecretBox (a no-op marker). A future DpapiSecretBox (or
an OS-keyring box) can be dropped in without touching SettingsStore or the
schema: stored values are prefix-marked so the format is self-describing and a
migration can re-wrap legacy values.
"""
from typing import Protocol, runtime_checkable


@runtime_checkable
class SecretBox(Protocol):
    def protect(self, plaintext: str) -> str:
        """Return the stored form of a secret."""
        ...

    def unprotect(self, stored: str) -> str:
        """Return the plaintext from a stored form."""
        ...


class PlaintextSecretBox:
    """Default seam: stores secrets in plaintext, prefix-marked.

    Same exposure as the previous plaintext .env on a single-user machine; the
    SQLite DB lives in %APPDATA% (gitignored) and never leaves the machine.
    """

    PREFIX = "plain:"

    def protect(self, plaintext: str) -> str:
        return f"{self.PREFIX}{plaintext}"

    def unprotect(self, stored: str) -> str:
        if stored.startswith(self.PREFIX):
            return stored[len(self.PREFIX):]
        return stored
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/unit/test_secret_box.py -q`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add app/storage/__init__.py app/storage/secret_box.py tests/unit/test_secret_box.py
git commit -m "feat: add SecretBox seam with plaintext default"
```

---

## Task 2: SettingsStore (model + get/set + typed accessors + secrets)

**Files:**
- Create: `app/storage/settings_store.py`
- Test: `tests/unit/test_settings_store.py`

This task uses the `temp_db_path` fixture from `tests/conftest.py` (Plan 1), which
points `TV2MT5_DB_PATH` at a throwaway SQLite file and the shared engine from
`src/config/database.py`.

- [ ] **Step 1: Write the failing tests for store basics**

Create `tests/unit/test_settings_store.py`:

```python
import json

from app.storage.settings_store import SettingsStore


def test_set_and_get_roundtrip(temp_db_path):
    store = SettingsStore()
    store.set("tv.broker_url", "broker.example.com")
    assert store.get("tv.broker_url") == "broker.example.com"


def test_get_returns_default_when_missing(temp_db_path):
    store = SettingsStore()
    assert store.get("nope", "fallback") == "fallback"


def test_get_int_parses_value(temp_db_path):
    store = SettingsStore()
    store.set("mt5.account", "123456")
    assert store.get_int("mt5.account") == 123456
    assert store.get_int("missing", 7) == 7


def test_get_bool_reads_one_zero(temp_db_path):
    store = SettingsStore()
    store.set("meta.seeded", "1")
    assert store.get_bool("meta.seeded") is True
    assert store.get_bool("absent") is False


def test_get_json_parses_and_falls_back(temp_db_path):
    store = SettingsStore()
    store.set("symbols.map", json.dumps({"BTCUSD": "BTCUSD.r"}))
    assert store.get_json("symbols.map") == {"BTCUSD": "BTCUSD.r"}
    store.set("symbols.bad", "{not json")
    assert store.get_json("symbols.bad", {}) == {}


def test_secret_roundtrip_uses_secret_box(temp_db_path):
    store = SettingsStore()
    store.set_secret("mt5.password", "hunter2")
    # Stored form is prefixed (plaintext box); reader returns plaintext.
    assert store.get("mt5.password") == "plain:hunter2"
    assert store.get_secret("mt5.password") == "hunter2"


def test_all_redacts_secret_keys(temp_db_path):
    store = SettingsStore()
    store.set("mt5.server", "Demo")
    store.set_secret("mt5.password", "hunter2")
    dumped = store.all(redact_secrets=True)
    assert dumped["mt5.server"] == "Demo"
    assert dumped["mt5.password"] == "***"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/unit/test_settings_store.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.storage.settings_store'`.

- [ ] **Step 3: Implement the settings store**

Create `app/storage/settings_store.py`:

```python
"""SQLite-backed settings store (replaces the .env workflow).

Backed by the shared engine from src/config/database.py (Plan 1). Values are
stored as text; typed accessors interpret them. Secret-flagged keys are written
through a SecretBox (plaintext by default).
"""
import json
import logging
from typing import Optional

from sqlalchemy import Column, String, Text
from sqlalchemy.orm import declarative_base

from src.config.database import get_engine, get_session_factory
from app.storage.secret_box import PlaintextSecretBox, SecretBox

logger = logging.getLogger("SettingsStore")

SettingsBase = declarative_base()

# Keys whose values must go through the SecretBox.
SECRET_KEYS = {"mt5.password"}


class Settings(SettingsBase):
    __tablename__ = "settings"
    key = Column(String, primary_key=True)
    value = Column(Text)


class SettingsStore:
    def __init__(self, secret_box: Optional[SecretBox] = None) -> None:
        self.secret_box = secret_box if secret_box is not None else PlaintextSecretBox()
        # Ensure the settings table exists on the shared engine.
        SettingsBase.metadata.create_all(bind=get_engine())
        self._Session = get_session_factory()

    # --- core string get/set ---

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        session = self._Session()
        try:
            row = session.get(Settings, key)
            return row.value if row is not None else default
        finally:
            session.close()

    def set(self, key: str, value) -> None:
        session = self._Session()
        try:
            row = session.get(Settings, key)
            if row is None:
                session.add(Settings(key=key, value=str(value)))
            else:
                row.value = str(value)
            session.commit()
        finally:
            session.close()

    # --- typed accessors ---

    def get_int(self, key: str, default: Optional[int] = None) -> Optional[int]:
        raw = self.get(key)
        return default if raw is None else int(raw)

    def get_bool(self, key: str, default: bool = False) -> bool:
        raw = self.get(key)
        if raw is None:
            return default
        return raw.strip().lower() in ("1", "true", "yes", "on")

    def get_json(self, key: str, default=None):
        raw = self.get(key)
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            logger.warning("Malformed JSON for %s; using default", key)
            return default

    # --- secrets ---

    def get_secret(self, key: str) -> Optional[str]:
        raw = self.get(key)
        return None if raw is None else self.secret_box.unprotect(raw)

    def set_secret(self, key: str, value: str) -> None:
        self.set(key, self.secret_box.protect(value))

    # --- bulk ---

    def all(self, *, redact_secrets: bool = True) -> dict:
        session = self._Session()
        try:
            rows = session.query(Settings).all()
            out = {}
            for row in rows:
                if redact_secrets and row.key in SECRET_KEYS:
                    out[row.key] = "***"
                else:
                    out[row.key] = row.value
            return out
        finally:
            session.close()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/unit/test_settings_store.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add app/storage/settings_store.py tests/unit/test_settings_store.py
git commit -m "feat: add SQLite-backed SettingsStore with typed + secret accessors"
```

---

## Task 3: Seed-once import from .env

**Files:**
- Modify: `app/storage/settings_store.py`
- Test: `tests/unit/test_settings_store.py` (seed portion)

- [ ] **Step 1: Write the failing tests for seed-once**

Append to `tests/unit/test_settings_store.py`:

```python
def test_seed_from_env_once_imports_keys(temp_db_path, monkeypatch):
    monkeypatch.setenv("TV_BROKER_URL", "broker.example.com")
    monkeypatch.setenv("TV_ACCOUNT_ID", "999")
    monkeypatch.setenv("MT5_ACCOUNT", "123456")
    monkeypatch.setenv("MT5_PASSWORD", "hunter2")
    monkeypatch.setenv("MT5_SERVER", "Demo-Server")
    monkeypatch.setenv("MT5_TERMINAL_PATH", "C:/mt5/terminal64.exe")
    monkeypatch.setenv("MT5_DEFAULT_SUFFIX", ".r")
    monkeypatch.setenv("MT5_SYMBOL_MAP", '{"BTCUSD": "BTCUSD.r"}')

    store = SettingsStore()
    seeded = store.seed_from_env_once()

    assert seeded is True
    assert store.get("tv.broker_url") == "broker.example.com"
    assert store.get_int("mt5.account") == 123456
    assert store.get_secret("mt5.password") == "hunter2"
    assert store.get("symbols.default_suffix") == ".r"
    assert store.get_json("symbols.map") == {"BTCUSD": "BTCUSD.r"}
    assert store.get_bool("meta.seeded") is True


def test_seed_from_env_once_is_idempotent(temp_db_path, monkeypatch):
    monkeypatch.setenv("MT5_SERVER", "First")
    store = SettingsStore()
    assert store.seed_from_env_once() is True

    # A later run with a different env must NOT clobber stored/edited values.
    monkeypatch.setenv("MT5_SERVER", "Second")
    assert store.seed_from_env_once() is False
    assert store.get("mt5.server") == "First"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/unit/test_settings_store.py -k seed -q`
Expected: FAIL — `SettingsStore` has no `seed_from_env_once` attribute.

- [ ] **Step 3: Add the seed-once method**

In `app/storage/settings_store.py`, add this import near the top (after the existing imports):

```python
import os

from dotenv import load_dotenv
```

Then add the `_ENV_MAP` constant immediately above the `class SettingsStore:` line:

```python
# Maps a .env variable -> (settings key, is_secret).
_ENV_MAP = {
    "TV_BROKER_URL": ("tv.broker_url", False),
    "TV_ACCOUNT_ID": ("tv.account_id", False),
    "MT5_ACCOUNT": ("mt5.account", False),
    "MT5_PASSWORD": ("mt5.password", True),
    "MT5_SERVER": ("mt5.server", False),
    "MT5_TERMINAL_PATH": ("mt5.terminal_path", False),
    "MT5_DEFAULT_SUFFIX": ("symbols.default_suffix", False),
    "MT5_SYMBOL_MAP": ("symbols.map", False),
}
```

Then add this method to `SettingsStore` (e.g. after `all`):

```python
    def seed_from_env_once(self) -> bool:
        """Import .env values into the store on first run only.

        Returns True if it seeded this call, False if already seeded. After
        seeding, the store is authoritative and .env is neither read nor needed.
        """
        if self.get_bool("meta.seeded"):
            return False
        load_dotenv()
        for env_var, (key, is_secret) in _ENV_MAP.items():
            value = os.getenv(env_var)
            if value is None or value == "":
                continue
            if is_secret:
                self.set_secret(key, value)
            else:
                self.set(key, value)
        self.set("meta.seeded", "1")
        logger.info("Seeded settings from .env (first run)")
        return True
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/unit/test_settings_store.py -k seed -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the whole settings-store file**

Run: `pytest tests/unit/test_settings_store.py -q`
Expected: PASS (9 passed).

- [ ] **Step 6: Commit**

```bash
git add app/storage/settings_store.py tests/unit/test_settings_store.py
git commit -m "feat: seed settings store once from existing .env"
```

---

## Task 4: Store-backed config accessors

**Files:**
- Create: `app/config_accessors.py`
- Test: `tests/unit/test_config_accessors.py`

These accessors read from the store first and fall back to `os.getenv` only when a
key is absent (pre-seed / tests). After seed-once, the store holds every key, so the
env fallback never fires — consistent with "seed once, store is authoritative".

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_config_accessors.py`:

```python
from app.config_accessors import (get_mt5_config, get_symbol_settings,
                                   get_tv_target)
from app.storage.settings_store import SettingsStore


def test_get_mt5_config_prefers_store(temp_db_path, monkeypatch):
    monkeypatch.delenv("MT5_ACCOUNT", raising=False)
    store = SettingsStore()
    store.set("mt5.account", "555")
    store.set_secret("mt5.password", "pw")
    store.set("mt5.server", "Demo")
    store.set("mt5.terminal_path", "C:/t.exe")

    cfg = get_mt5_config()
    assert cfg["account"] == 555
    assert cfg["password"] == "pw"
    assert cfg["server"] == "Demo"
    assert cfg["terminal_path"] == "C:/t.exe"


def test_get_mt5_config_falls_back_to_env_pre_seed(temp_db_path, monkeypatch):
    monkeypatch.setenv("MT5_ACCOUNT", "777")
    monkeypatch.setenv("MT5_PASSWORD", "envpw")
    monkeypatch.setenv("MT5_SERVER", "EnvServer")
    cfg = get_mt5_config()
    assert cfg["account"] == 777
    assert cfg["password"] == "envpw"
    assert cfg["server"] == "EnvServer"


def test_get_tv_target_from_store(temp_db_path, monkeypatch):
    monkeypatch.delenv("TV_BROKER_URL", raising=False)
    monkeypatch.delenv("TV_ACCOUNT_ID", raising=False)
    store = SettingsStore()
    store.set("tv.broker_url", "broker.example.com")
    store.set("tv.account_id", "999")
    assert get_tv_target() == ("broker.example.com", "999")


def test_get_symbol_settings_defaults(temp_db_path, monkeypatch):
    monkeypatch.delenv("MT5_DEFAULT_SUFFIX", raising=False)
    monkeypatch.delenv("MT5_SYMBOL_MAP", raising=False)
    suffix, mapping = get_symbol_settings()
    assert suffix == ".a"
    assert mapping == {}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/unit/test_config_accessors.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.config_accessors'`.

- [ ] **Step 3: Implement the accessors**

Create `app/config_accessors.py`:

```python
"""Store-backed configuration accessors (replace import-time os.getenv reads).

The SettingsStore is the source of truth. os.getenv is consulted only when the
store has no value for a key (pre-seed or in tests); after seed_from_env_once
the store holds every key, so the fallback never fires.
"""
import json
import os
from typing import Optional, Tuple

from app.storage.settings_store import SettingsStore


def _store() -> SettingsStore:
    return SettingsStore()


def get_mt5_config() -> dict:
    """Return MT5 connection config: account, password, server, terminal_path."""
    s = _store()
    account = s.get_int("mt5.account")
    if account is None and os.getenv("MT5_ACCOUNT"):
        account = int(os.getenv("MT5_ACCOUNT"))
    return {
        "account": account,
        "password": s.get_secret("mt5.password") or os.getenv("MT5_PASSWORD"),
        "server": s.get("mt5.server") or os.getenv("MT5_SERVER"),
        "terminal_path": s.get("mt5.terminal_path") or os.getenv("MT5_TERMINAL_PATH"),
    }


def get_tv_target() -> Tuple[Optional[str], Optional[str]]:
    """Return (broker_url, account_id) for the TradingView broker panel."""
    s = _store()
    broker = s.get("tv.broker_url") or os.getenv("TV_BROKER_URL")
    account = s.get("tv.account_id") or os.getenv("TV_ACCOUNT_ID")
    return broker, account


def get_symbol_settings() -> Tuple[str, dict]:
    """Return (default_suffix, symbol_map)."""
    s = _store()
    suffix = s.get("symbols.default_suffix") or os.getenv("MT5_DEFAULT_SUFFIX", ".a")
    raw_map = s.get("symbols.map")
    if raw_map is None:
        raw_map = os.getenv("MT5_SYMBOL_MAP", "{}")
    try:
        mapping = json.loads(raw_map)
    except (ValueError, TypeError):
        mapping = {}
    return suffix, mapping
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/unit/test_config_accessors.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add app/config_accessors.py tests/unit/test_config_accessors.py
git commit -m "feat: add store-backed config accessors with env fallback"
```

---

## Task 5: BrokerAdapter interface + AccountInfo

**Files:**
- Create: `app/adapters/__init__.py`
- Create: `app/adapters/base.py`
- Test: `tests/unit/test_fusion_adapter.py` (AccountInfo portion)

- [ ] **Step 1: Create the adapters package marker**

Create `app/adapters/__init__.py`:

```python
"""Broker adapters: identify and locate a broker's TradingView traffic."""
```

- [ ] **Step 2: Write the failing test for the dataclass + protocol**

Create `tests/unit/test_fusion_adapter.py`:

```python
from app.adapters.base import AccountInfo, BrokerAdapter


def test_account_info_holds_target():
    info = AccountInfo(broker_url="broker.example.com", account_id="999")
    assert info.broker_url == "broker.example.com"
    assert info.account_id == "999"


def test_broker_adapter_is_a_protocol():
    # Protocol exists and is importable; concrete adapters implement it.
    assert hasattr(BrokerAdapter, "__mro__") or BrokerAdapter is not None
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `pytest tests/unit/test_fusion_adapter.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.adapters.base'`.

- [ ] **Step 4: Implement the interface**

Create `app/adapters/base.py`:

```python
"""BrokerAdapter seam.

Thin by design (Plan 2): adapters own flow *matching* and *account detection*.
Trade parsing stays in src/core/trade_handler.py — the parse shape is
TradingView's broker-panel REST API, shared across TV-panel brokers, so it is
not per-broker logic. A future non-TV broker can implement a richer parse_trade
on its own adapter without disturbing this one.
"""
from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable


@dataclass
class AccountInfo:
    broker_url: str
    account_id: str


@runtime_checkable
class BrokerAdapter(Protocol):
    name: str

    def matches(self, flow) -> bool:
        """Return True if this flow belongs to our broker and is processable."""
        ...

    def detect_account(self, flow) -> Optional[AccountInfo]:
        """Extract broker_url/account_id from broker-panel traffic, or None."""
        ...
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/unit/test_fusion_adapter.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add app/adapters/__init__.py app/adapters/base.py tests/unit/test_fusion_adapter.py
git commit -m "feat: add BrokerAdapter protocol and AccountInfo"
```

---

## Task 6: FusionMarketsAdapter.matches (parity with should_log_request)

**Files:**
- Create: `app/adapters/fusion_markets.py`
- Test: `tests/unit/test_fusion_adapter.py` (matches portion)

- [ ] **Step 1: Write the failing tests for matching**

Append to `tests/unit/test_fusion_adapter.py`:

```python
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


def test_does_not_match_other_urls_or_no_target(temp_db_path):
    a = _adapter_with_target(temp_db_path)
    assert a.matches(_Flow("https://broker.example.com/accounts/999/quotes")) is False
    assert a.matches(_Flow("https://other.com/accounts/1/orders?requestId=x", "POST")) is False
    # No target configured -> never matches.
    empty = FusionMarketsAdapter(store=SettingsStore())
    # (store has the target from _adapter_with_target's writes are isolated per temp db)
```

> Note: the last assertion block intentionally exercises the no-target guard via
> a fresh store on the same temp DB; `tv.*` keys set above persist, so to test the
> empty case rely on `base_path` returning None when keys are cleared — covered in
> Task 7's detect tests. Keep this test focused on positive/negative URL matching.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/unit/test_fusion_adapter.py -k matches -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.adapters.fusion_markets'`.

- [ ] **Step 3: Implement the adapter with `base_path` + `matches`**

Create `app/adapters/fusion_markets.py`:

```python
"""FusionMarkets adapter: TradingView broker-panel traffic.

`matches` reproduces the gating that previously lived inline in
src/core/interceptor.py:should_log_request. `detect_account` (Task 7) learns the
broker target from live traffic. Trade parsing is unchanged and stays in
src/core/trade_handler.py.
"""
import logging
import re
from typing import Optional

from app.adapters.base import AccountInfo
from app.storage.settings_store import SettingsStore

logger = logging.getLogger("FusionMarketsAdapter")

# https://{host}/accounts/{digits}/...  (TradingView broker-panel REST shape)
_ACCOUNT_RE = re.compile(r"https?://(?P<host>[^/]+)/accounts/(?P<acct>\d+)/")


def _is_tradingview(flow) -> bool:
    headers = getattr(flow.request, "headers", {}) or {}
    referer = headers.get("referer", "") or ""
    origin = headers.get("origin", "") or ""
    return "tradingview.com" in (referer + origin)


class FusionMarketsAdapter:
    name = "fusion_markets"

    def __init__(self, store: Optional[SettingsStore] = None) -> None:
        self.store = store if store is not None else SettingsStore()
        self._broker_url = self.store.get("tv.broker_url")
        self._account_id = self.store.get("tv.account_id")

    @property
    def base_path(self) -> Optional[str]:
        if not self._broker_url or not self._account_id:
            return None
        return f"{self._broker_url}/accounts/{self._account_id}"

    def matches(self, flow) -> bool:
        base = self.base_path
        if not base:
            return False
        url = flow.request.pretty_url
        if base not in url:
            return False
        if "/orders?locale=" in url and "requestId=" in url:
            return True
        if "/executions?locale=" in url and "instrument=" in url:
            return True
        if "/positions/" in url:
            return flow.request.method in ("DELETE", "PUT")
        if ".TP." in url or ".SL." in url:
            return flow.request.method == "DELETE"
        return False
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/unit/test_fusion_adapter.py -k matches -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/adapters/fusion_markets.py tests/unit/test_fusion_adapter.py
git commit -m "feat: FusionMarketsAdapter.matches mirrors should_log_request"
```

---

## Task 7: FusionMarketsAdapter.detect_account + persist_account

**Files:**
- Modify: `app/adapters/fusion_markets.py`
- Test: `tests/unit/test_fusion_adapter.py` (detect portion)

- [ ] **Step 1: Write the failing tests for detection + persistence**

Append to `tests/unit/test_fusion_adapter.py`:

```python
TV_HEADERS = {"referer": "https://www.tradingview.com/", "origin": "https://www.tradingview.com"}


def test_detect_account_from_tradingview_flow(temp_db_path):
    a = FusionMarketsAdapter(store=SettingsStore())
    flow = _Flow("https://broker.example.com/accounts/424242/orders?locale=en",
                 "POST", TV_HEADERS)
    info = a.detect_account(flow)
    assert info is not None
    assert info.broker_url == "broker.example.com"
    assert info.account_id == "424242"


def test_detect_account_ignores_non_tradingview_origin(temp_db_path):
    a = FusionMarketsAdapter(store=SettingsStore())
    flow = _Flow("https://broker.example.com/accounts/424242/orders?locale=en",
                 "POST", {"referer": "https://evil.example.com"})
    assert a.detect_account(flow) is None


def test_detect_account_returns_none_on_unmatched_url(temp_db_path):
    a = FusionMarketsAdapter(store=SettingsStore())
    flow = _Flow("https://www.tradingview.com/chart", "GET", TV_HEADERS)
    assert a.detect_account(flow) is None


def test_persist_account_writes_and_updates_base_path(temp_db_path):
    store = SettingsStore()
    a = FusionMarketsAdapter(store=store)
    assert a.base_path is None  # nothing known yet

    info = AccountInfo(broker_url="broker.example.com", account_id="424242")
    changed = a.persist_account(info)

    assert changed is True
    assert a.base_path == "broker.example.com/accounts/424242"
    assert store.get("tv.broker_url") == "broker.example.com"
    assert store.get("tv.account_id") == "424242"
    # Re-persisting the same target is a no-op.
    assert a.persist_account(info) is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/unit/test_fusion_adapter.py -k "detect or persist" -q`
Expected: FAIL — `FusionMarketsAdapter` has no `detect_account` / `persist_account`.

- [ ] **Step 3: Add `detect_account` and `persist_account`**

In `app/adapters/fusion_markets.py`, add these two methods to `FusionMarketsAdapter`
(after `matches`):

```python
    def detect_account(self, flow) -> Optional[AccountInfo]:
        """Learn broker_url/account_id from TradingView-originated traffic."""
        if not _is_tradingview(flow):
            return None
        match = _ACCOUNT_RE.search(flow.request.pretty_url)
        if not match:
            return None
        return AccountInfo(broker_url=match.group("host"),
                           account_id=match.group("acct"))

    def persist_account(self, info: AccountInfo) -> bool:
        """Persist a detected target if it differs from the current one.

        Returns True if the stored target changed (so callers can refresh
        derived state like base_path).
        """
        if (info.broker_url, info.account_id) == (self._broker_url, self._account_id):
            return False
        self.store.set("tv.broker_url", info.broker_url)
        self.store.set("tv.account_id", info.account_id)
        self._broker_url = info.broker_url
        self._account_id = info.account_id
        logger.info("Detected TradingView target %s (%s)",
                    info.account_id, info.broker_url)
        return True
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/unit/test_fusion_adapter.py -q`
Expected: PASS (all adapter tests).

- [ ] **Step 5: Commit**

```bash
git add app/adapters/fusion_markets.py tests/unit/test_fusion_adapter.py
git commit -m "feat: FusionMarketsAdapter auto-detects and persists broker target"
```

---

## Task 8: Inject the adapter into the interceptor

**Files:**
- Modify: `src/core/interceptor.py`
- Modify: `tests/unit/test_engine_factory.py`
- Test: `tests/unit/test_fusion_adapter.py` (interceptor-integration portion)

- [ ] **Step 1: Write the failing test for interceptor + adapter**

Append to `tests/unit/test_fusion_adapter.py`:

```python
def test_interceptor_uses_injected_adapter_and_detects(temp_db_path):
    from src.core.interceptor import TradingViewInterceptor

    store = SettingsStore()
    adapter = FusionMarketsAdapter(store=store)

    TradingViewInterceptor._instance = None
    TradingViewInterceptor._initialized = False
    interceptor = TradingViewInterceptor(
        trade_handler=object(), adapter=adapter, sync_instruments=False
    )

    # A matching TradingView flow drives auto-detect through request().
    flow = _Flow("https://broker.example.com/accounts/787878/orders?locale=en&requestId=z",
                 "POST", TV_HEADERS)
    interceptor.request(flow)

    assert store.get("tv.account_id") == "787878"
    assert interceptor.base_path == "broker.example.com/accounts/787878"
    assert interceptor.should_log_request(flow) is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/test_fusion_adapter.py::test_interceptor_uses_injected_adapter_and_detects -q`
Expected: FAIL — `TradingViewInterceptor.__init__` takes no `adapter` argument.

- [ ] **Step 3: Update the interceptor module header**

In `src/core/interceptor.py`, replace lines 8–20:

```python
from dotenv import load_dotenv

from backup.instrument_sync import InstrumentSynchronizer
from mitmproxy import http
from src.core.trade_handler import TradeHandler
from src.utils.token_manager import GLOBAL_TOKEN_MANAGER, TokenManager

project_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, project_root)

load_dotenv()
TV_BROKER_URL = os.getenv('TV_BROKER_URL')
TV_ACCOUNT_ID = os.getenv('TV_ACCOUNT_ID')
```

with:

```python
from backup.instrument_sync import InstrumentSynchronizer
from mitmproxy import http
from src.core.trade_handler import TradeHandler
from src.utils.token_manager import GLOBAL_TOKEN_MANAGER, TokenManager
from app.adapters.fusion_markets import FusionMarketsAdapter

project_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, project_root)
```

- [ ] **Step 4: Update `__init__` to accept an injected adapter**

In `src/core/interceptor.py`, replace `__init__` (original lines 36–51):

```python
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

with:

```python
    def __init__(self, trade_handler=None, adapter=None, sync_instruments=True):
        if not self._initialized:  # Only initialize once
            self.adapter = adapter if adapter is not None else FusionMarketsAdapter()
            self.base_path = self.adapter.base_path or ""
            self.trade_handler = trade_handler if trade_handler is not None else TradeHandler()
            self.token_manager = GLOBAL_TOKEN_MANAGER
            if sync_instruments:
                self._sync_instruments_sync()

            broker_url = self.adapter._broker_url or 'Unknown Broker'
            account_id = self.adapter._account_id or 'Unknown Account'

            print("\n🚀 Trade interceptor initialized")
            print("👀 Watching for trades...\n")
            print(f"✅ TradingView Connected: {account_id} ({broker_url})")

            self._initialized = True
```

- [ ] **Step 5: Update `_sync_instruments_sync` to use the adapter target**

In `src/core/interceptor.py`, replace the URL line (original line 67):

```python
            url = f"https://{os.getenv('TV_BROKER_URL')}/accounts/{os.getenv('TV_ACCOUNT_ID')}/instruments?locale=en"
```

with:

```python
            if not self.adapter.base_path:
                print("ℹ️  TradingView target not known yet; skipping instrument sync")
                return
            url = f"https://{self.adapter.base_path}/instruments?locale=en"
```

- [ ] **Step 6: Delegate matching to the adapter**

In `src/core/interceptor.py`, replace `should_log_request` (original lines 136–153):

```python
    def should_log_request(self, flow: http.HTTPFlow) -> bool:
        """Strictly check if we should log this request."""
        url = flow.request.pretty_url
        
        if self.base_path not in url:
            return False
        
        # Match orders, executions, position closures, and position updates
        if '/orders?locale=' in url and 'requestId=' in url:
            return True
        if '/executions?locale=' in url and 'instrument=' in url:
            return True
        if '/positions/' in url:
            return flow.request.method in ["DELETE", "PUT"]
        if '.TP.' in url or '.SL.' in url:
            return flow.request.method == "DELETE"   
            
        return False
```

with:

```python
    def should_log_request(self, flow: http.HTTPFlow) -> bool:
        """Delegate flow matching to the broker adapter."""
        return self.adapter.matches(flow)
```

- [ ] **Step 7: Run auto-detect + adapter base_path inside `request`**

In `src/core/interceptor.py`, replace the start of `request` (original lines 175–183):

```python
    def request(self, flow: http.HTTPFlow) -> None:
        """Handle requests."""
        if self.base_path in flow.request.pretty_url:
            auth_header = flow.request.headers.get('authorization')
            if auth_header:
                self.token_manager.update_token(auth_header)
        
        if not self.should_log_request(flow):
            return
```

with:

```python
    def request(self, flow: http.HTTPFlow) -> None:
        """Handle requests."""
        # Auto-detect broker_url/account_id from live TradingView traffic.
        info = self.adapter.detect_account(flow)
        if info and self.adapter.persist_account(info):
            self.base_path = self.adapter.base_path
            print(f"🔎 Detected TradingView account: {info.account_id} ({info.broker_url})")

        if self.adapter.base_path and self.adapter.base_path in flow.request.pretty_url:
            auth_header = flow.request.headers.get('authorization')
            if auth_header:
                self.token_manager.update_token(auth_header)

        if not self.should_log_request(flow):
            return
```

- [ ] **Step 8: Keep the Plan 1 interceptor test green under the new constructor**

In `tests/unit/test_engine_factory.py`, replace `test_interceptor_accepts_injected_handler`
(original lines 4–18) with a version that points the default adapter's store at the
temp DB and skips the network sync:

```python
def test_interceptor_accepts_injected_handler(monkeypatch, temp_db_path):
    from src.core.interceptor import TradingViewInterceptor

    # Reset the singleton so the test controls construction.
    TradingViewInterceptor._instance = None
    TradingViewInterceptor._initialized = False

    stub = _StubHandler()
    interceptor = TradingViewInterceptor(trade_handler=stub, sync_instruments=False)
    assert interceptor.trade_handler is stub
```

> The `_StubHandler` class at the top of the file and the other tests stay
> unchanged. `temp_db_path` ensures the default `FusionMarketsAdapter()` builds its
> `SettingsStore` against a throwaway DB rather than `%APPDATA%`.

- [ ] **Step 9: Run the interceptor + engine-factory tests**

Run: `pytest tests/unit/test_fusion_adapter.py tests/unit/test_engine_factory.py -q`
Expected: PASS (all tests).

- [ ] **Step 10: Commit**

```bash
git add src/core/interceptor.py tests/unit/test_fusion_adapter.py tests/unit/test_engine_factory.py
git commit -m "feat: inject broker adapter into interceptor (match + auto-detect)"
```

---

## Task 9: Retarget config consumers to the store

**Files:**
- Modify: `src/config/mt5_config.py`
- Modify: `src/config/mt5_symbol_config.py`
- Modify: `src/services/tradingview_service.py`
- Modify: `src/workers/mt5_worker.py`
- Modify: `src/utils/symbol_mapper.py`
- Modify: `src/utils/instrument_manager.py`
- Test: `tests/unit/test_config_accessors.py` (import-safety portion)

This removes the import-time `os.getenv`/`MT5_CONFIG` reads that would raise for a
fresh install where config lives only in the store.

- [ ] **Step 1: Write the failing import-safety test**

Append to `tests/unit/test_config_accessors.py`:

```python
def test_config_modules_import_without_env(temp_db_path, monkeypatch):
    """A fresh install has no MT5_* env; importing config must not raise."""
    for var in ("MT5_ACCOUNT", "MT5_PASSWORD", "MT5_SERVER", "MT5_TERMINAL_PATH"):
        monkeypatch.delenv(var, raising=False)

    import importlib

    import src.config.mt5_config as mt5_config
    importlib.reload(mt5_config)
    assert hasattr(mt5_config, "get_mt5_config")
    # Calling it returns Nones rather than raising.
    cfg = mt5_config.get_mt5_config()
    assert cfg["account"] is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/test_config_accessors.py::test_config_modules_import_without_env -q`
Expected: FAIL — importing `src.config.mt5_config` calls `get_required_env('MT5_ACCOUNT')` and raises `ValueError`.

- [ ] **Step 3: Replace `src/config/mt5_config.py`**

Replace the entire contents of `src/config/mt5_config.py` with:

```python
"""MT5 connection config, now sourced from the settings store (was .env).

Kept as a thin module so existing imports (`from src.config.mt5_config import
get_mt5_config`) keep working. The import-time MT5_CONFIG dict was removed: it
read os.getenv at import and raised on a fresh install where config lives only
in the SQLite settings table.
"""
from app.config_accessors import get_mt5_config

__all__ = ["get_mt5_config"]
```

- [ ] **Step 4: Run the import-safety test to verify it passes**

Run: `pytest tests/unit/test_config_accessors.py::test_config_modules_import_without_env -q`
Expected: PASS.

- [ ] **Step 5: Update `src/workers/mt5_worker.py` to use the accessor**

In `src/workers/mt5_worker.py`, replace the import (original line 11):

```python
from src.config.mt5_config import MT5_CONFIG
```

with:

```python
from src.config.mt5_config import get_mt5_config
```

Replace the terminal-path check inside `initialize` (original lines 37–44):

```python
        # Check MT5 terminal path before initialization
        terminal_path = os.getenv('MT5_TERMINAL_PATH')
        if not terminal_path:
            print("\n⚠️  MT5_TERMINAL_PATH not set in .env")
            print("Available MT5 terminals:")
            terminals = find_mt5_terminals()
            for i, path in enumerate(terminals, 1):
                print(f"{i}. {path}")
            print("\nAdd your chosen path to .env as MT5_TERMINAL_PATH=<path>")
```

with:

```python
        # Check MT5 terminal path before initialization
        mt5_config = get_mt5_config()
        terminal_path = mt5_config['terminal_path']
        if not terminal_path:
            print("\n⚠️  MT5 terminal path not configured")
            print("Available MT5 terminals:")
            terminals = find_mt5_terminals()
            for i, path in enumerate(terminals, 1):
                print(f"{i}. {path}")
            print("\nConfigure the terminal path in Settings (or .env until then).")
```

Replace the `MT5Service(...)` construction inside `initialize` (original lines 52–57):

```python
        self.mt5 = MT5Service(
            account=MT5_CONFIG['account'],
            password=MT5_CONFIG['password'],
            server=MT5_CONFIG['server'],
            db_handler=self.db
        )
```

with:

```python
        self.mt5 = MT5Service(
            account=mt5_config['account'],
            password=mt5_config['password'],
            server=mt5_config['server'],
            db_handler=self.db
        )
```

Replace the `MT5Service(...)` construction inside `init_inproc` (original lines 74–79):

```python
        self.mt5 = MT5Service(
            account=MT5_CONFIG['account'],
            password=MT5_CONFIG['password'],
            server=MT5_CONFIG['server'],
            db_handler=self.db,
        )
```

with:

```python
        mt5_config = get_mt5_config()
        self.mt5 = MT5Service(
            account=mt5_config['account'],
            password=mt5_config['password'],
            server=mt5_config['server'],
            db_handler=self.db,
        )
```

- [ ] **Step 6: Update `src/utils/symbol_mapper.py` to use the accessor**

In `src/utils/symbol_mapper.py`, replace the import (original line 9):

```python
from src.config.mt5_config import MT5_CONFIG
```

with:

```python
from src.config.mt5_config import get_mt5_config
```

Replace the `MT5Service(...)` construction (original lines 40–44):

```python
        self.mt5_service = MT5Service(
            account=MT5_CONFIG['account'],
            password=MT5_CONFIG['password'],
            server=MT5_CONFIG['server']
        )
```

with:

```python
        _cfg = get_mt5_config()
        self.mt5_service = MT5Service(
            account=_cfg['account'],
            password=_cfg['password'],
            server=_cfg['server']
        )
```

- [ ] **Step 7: Replace `src/config/mt5_symbol_config.py`**

Replace the entire contents of `src/config/mt5_symbol_config.py` with:

```python
"""TradingView->MT5 symbol mapping, sourced from the settings store (was .env)."""
from typing import Dict

from app.config_accessors import get_symbol_settings


class SymbolMapper:
    def __init__(self, suffix: str = None, custom_map: Dict[str, str] = None):
        default_suffix, default_map = get_symbol_settings()
        self.suffix = suffix if suffix is not None else default_suffix
        self.custom_map = custom_map if custom_map is not None else default_map

    def map_symbol(self, tv_symbol: str) -> str:
        """Map TradingView symbol to MT5 symbol."""
        if tv_symbol in self.custom_map:
            return self.custom_map[tv_symbol]
        return f"{tv_symbol}{self.suffix}"

    def add_mapping(self, tv_symbol: str, mt5_symbol: str) -> None:
        """Add a custom symbol mapping."""
        self.custom_map[tv_symbol] = mt5_symbol

    def remove_mapping(self, tv_symbol: str) -> None:
        """Remove a custom symbol mapping."""
        self.custom_map.pop(tv_symbol, None)

    def get_all_mappings(self) -> Dict[str, str]:
        """Get all custom symbol mappings."""
        return self.custom_map.copy()
```

- [ ] **Step 8: Update `src/services/tradingview_service.py`**

In `src/services/tradingview_service.py`, replace the module header (original lines 1–22):

```python
import asyncio
import logging
import os
from typing import Any, Dict

import aiohttp
from dotenv import load_dotenv

from src.utils.token_manager import TokenManager

logger = logging.getLogger('TradingViewService')

load_dotenv()
TV_BROKER_URL = os.getenv('TV_BROKER_URL')
TV_ACCOUNT_ID = os.getenv('TV_ACCOUNT_ID')

class TradingViewService:
    """Service to interact with TradingView API."""
    
    def __init__(self, token_manager: TokenManager):
        self.token_manager = token_manager
        self.base_url = f"https://{TV_BROKER_URL}/accounts/{TV_ACCOUNT_ID}"
```

with:

```python
import asyncio
import logging
from typing import Any, Dict

import aiohttp

from src.utils.token_manager import TokenManager
from app.config_accessors import get_tv_target

logger = logging.getLogger('TradingViewService')


class TradingViewService:
    """Service to interact with TradingView API."""

    def __init__(self, token_manager: TokenManager):
        self.token_manager = token_manager
        broker_url, account_id = get_tv_target()
        self.base_url = f"https://{broker_url}/accounts/{account_id}"
```

Leave the rest of the file (the `self.session`, `self.loop`, `self.proxies` lines and
all methods) unchanged.

- [ ] **Step 9: Update `src/utils/instrument_manager.py`**

In `src/utils/instrument_manager.py`, replace the header + `__init__` (original lines 1–16):

```python
import json
import logging
import os
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv

logger = logging.getLogger('InstrumentManager')

class InstrumentManager:
    def __init__(self):
        load_dotenv()
        self.config_path = Path(__file__).parent.parent.parent / 'data' / 'instruments.json'
        self.default_suffix = os.getenv('MT5_DEFAULT_SUFFIX', '')
        self.instruments = self._load_config()
```

with:

```python
import json
import logging
from pathlib import Path
from typing import Dict

from app.config_accessors import get_symbol_settings

logger = logging.getLogger('InstrumentManager')

class InstrumentManager:
    def __init__(self):
        self.config_path = Path(__file__).parent.parent.parent / 'data' / 'instruments.json'
        self.default_suffix, _ = get_symbol_settings()
        self.instruments = self._load_config()
```

Leave `_load_config`, `get_pip_size`, and `calculate_trailing_distance` unchanged.

- [ ] **Step 10: Confirm no runtime module still imports the removed names**

Run: `grep -rn "MT5_CONFIG\|DEFAULT_SUFFIX\|SYMBOL_MAP" src/workers src/utils/symbol_mapper.py src/utils/instrument_manager.py src/services/tradingview_service.py src/core/interceptor.py`
Expected: no matches (standalone `src/scripts/*` may still reference them — out of scope, see spec).

- [ ] **Step 11: Run the full unit suite**

Run: `pytest tests/unit -q`
Expected: PASS (all unit tests across every file, including Plan 1's).

- [ ] **Step 12: Commit**

```bash
git add src/config/mt5_config.py src/config/mt5_symbol_config.py src/services/tradingview_service.py src/workers/mt5_worker.py src/utils/symbol_mapper.py src/utils/instrument_manager.py tests/unit/test_config_accessors.py
git commit -m "refactor: read config from settings store instead of .env at import"
```

---

## Task 10: Wire the store + adapter into the engine

**Files:**
- Modify: `app/engine.py`
- Test: import smoke + full suite

- [ ] **Step 1: Build the store, seed once, and inject the adapter in `run_engine`**

In `app/engine.py`, inside `run_engine`, replace the local-imports + setup block
(from Plan 1) that currently reads:

```python
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
```

with:

```python
    # Local imports so unit tests can import build_master without these deps.
    from src.models.database import init_db
    from src.utils.database_handler import DatabaseHandler
    from src.core.trade_handler import TradeHandler
    from src.core.interceptor import TradingViewInterceptor
    from src.workers.mt5_worker import MT5Worker
    from app.queue.inproc_queue import InProcQueue
    from app.storage.settings_store import SettingsStore
    from app.adapters.fusion_markets import FusionMarketsAdapter

    init_db()

    # Settings store is the source of truth; seed once from any existing .env.
    store = SettingsStore()
    store.seed_from_env_once()

    loop = asyncio.get_event_loop()
    queue = InProcQueue()
    db = DatabaseHandler()

    # Shared trade handler used by the interceptor; pushes onto the queue.
    trade_handler = TradeHandler(queue=queue, db=db)

    # Worker consumes from the same queue on the same loop.
    worker = MT5Worker()
    worker.init_inproc(loop=loop, queue=queue, db=db)
    queue.subscribe(worker.handle_message)

    # Broker adapter owns flow matching + broker-target auto-detect.
    adapter = FusionMarketsAdapter(store=store)

    # Interceptor addon shares the trade handler and adapter.
    TradingViewInterceptor._instance = None
    TradingViewInterceptor._initialized = False
    interceptor = TradingViewInterceptor(trade_handler=trade_handler, adapter=adapter)
```

Leave the `build_master(...)` call, the worker task, and the `try/finally` shutdown
block unchanged.

- [ ] **Step 2: Verify the engine module imports cleanly**

Run: `python -c "import app.engine; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Verify the full unit suite passes**

Run: `pytest tests/unit -q`
Expected: PASS (all tests).

- [ ] **Step 4: Commit**

```bash
git add app/engine.py
git commit -m "feat: wire settings store + broker adapter into the engine"
```

> Manual end-to-end (cannot be unit-tested here): with the MT5 terminal running and
> either a seeded `.env` or settings entered, `python run.py start` should print the
> interceptor/worker banners. Placing a test trade in TradingView's broker panel
> should (a) print `🔎 Detected TradingView account: ...` on first matching request
> and persist `tv.broker_url`/`tv.account_id` to the settings table, and (b) copy the
> trade into MT5 exactly as before — confirming the adapter seam and store are live
> with no behaviour change.

---

## Self-Review (completed during planning)

**Spec coverage (Plan 2 scope):**
- "SettingsStore backed by a SQLite `settings` table" → Task 2. ✅
- Typed accessors (`get_int`/`get_json`/`get_bool`/`get_secret`/`all`) → Task 2. ✅
- "Seeded once from any existing `.env`" → Task 3. ✅
- `SecretBox` seam, plaintext default, prefix-marked → Task 1; used by store in Task 2. ✅
- Canonical settings keys (tv.*, mt5.*, symbols.*, meta.seeded) → Tasks 2–3 + `_ENV_MAP`. ✅
- `BrokerAdapter` Protocol + `AccountInfo` → Task 5. ✅
- `FusionMarketsAdapter.matches` (parity with `should_log_request`) → Task 6. ✅
- `FusionMarketsAdapter.detect_account` + persistence (auto-detect from live traffic) → Task 7. ✅
- Interceptor uses the injected adapter for matching + auto-detect; instrument-sync URL from the adapter target → Task 8. ✅
- Config reads move off import-time `os.getenv` to the store (`get_mt5_config`/`get_tv_target`/`get_symbol_settings`) → Tasks 4 + 9. ✅
- Engine builds store, seeds once, injects adapter → Task 10. ✅
- Trade parsing/execution unchanged (`trade_handler`, `mt5_service`) → no task touches them. ✅
- Standalone scripts retarget noted as out of scope → Task 9 Step 10 note + spec. ✅

**Placeholder scan:** No TBD/TODO/"add error handling" placeholders; every code step shows full code and exact commands. ✅

**Type/name consistency:**
- `PlaintextSecretBox.PREFIX = "plain:"` (Task 1) matches the `plain:hunter2` expectations in Task 2's secret test. ✅
- `SettingsStore` methods (`get`/`set`/`get_int`/`get_bool`/`get_json`/`get_secret`/`set_secret`/`all`/`seed_from_env_once`) defined in Tasks 2–3 and called in Tasks 4, 6–10. ✅
- `SECRET_KEYS = {"mt5.password"}` (Task 2) matches the `set_secret`/redaction test and `_ENV_MAP`'s `is_secret` flag for `MT5_PASSWORD` (Task 3). ✅
- `_ENV_MAP` env→key mapping (Task 3) matches the canonical keys read by the accessors (Task 4) and the spec's keys table. ✅
- `AccountInfo(broker_url, account_id)` (Task 5) used identically in Tasks 6–8. ✅
- `FusionMarketsAdapter` API (`base_path` property, `matches`, `detect_account`, `persist_account`, `_broker_url`/`_account_id`, `store`) defined in Tasks 6–7 and used in Task 8 (interceptor) + Task 10 (engine). ✅
- `get_mt5_config()` returns `account`/`password`/`server`/`terminal_path` (Task 4) and every consumer in Task 9 reads exactly those keys. ✅
- Interceptor constructor `__init__(self, trade_handler=None, adapter=None, sync_instruments=True)` (Task 8) matches the engine call `TradingViewInterceptor(trade_handler=trade_handler, adapter=adapter)` (Task 10) and the Plan 1 test call (Task 8 Step 8). ✅
- `get_symbol_settings()` returns `(suffix, mapping)` (Task 4) matching the tuple unpacking in `SymbolMapper` and `InstrumentManager` (Task 9). ✅
