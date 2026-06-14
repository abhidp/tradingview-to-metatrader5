# TV2MT5 Desktop — Plan 3b: Content Tabs (Trades / Symbols / Settings) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill the three greyed sidebar tabs (Trades / Symbols / Settings) with read/write views over the existing SQLite `settings` store and `trades` table, plus a one-click engine restart — without changing the engine or the trade-execution path.

**Architecture:** Add small testable read/write helpers (`query_trades` in `app/api/trades.py`; `app/api/config_api.py` for settings + symbols), an `EngineController.restart()`, and thin FastAPI routes in `app/api/server.py`. Extend the Plan 3a vanilla-JS UI: generalize sidebar view-switching and add Trades (paged table + status filter), Symbols (suffix + map editor), and Settings (MT5 form, read-only TV target, password redacted) views.

**Tech Stack:** Python 3.11, FastAPI + uvicorn, SQLAlchemy (SQLite), pytest + FastAPI TestClient, vanilla HTML/CSS/JS.

---

## File Structure

**Create:**
- `app/api/config_api.py` — `get_settings`/`update_settings` (MT5 editable, TV read-only, password redacted/keep-on-blank) and `get_symbols`/`update_symbols`; `SettingsValidationError`.
- `tests/unit/test_api_config.py` — unit tests for `config_api`.

**Modify:**
- `app/api/trades.py` — replace `recent_trades` with `query_trades(limit, offset, status) -> (rows, total)`.
- `app/engine_controller.py` — add `restart()`.
- `app/api/server.py` — extend `GET /api/trades` (offset/status/total); add `GET`/`PUT /api/settings`, `GET`/`PUT /api/symbols`, `POST /api/engine/restart`.
- `app/ui/index.html` — add Trades/Symbols/Settings view sections; un-grey nav items.
- `app/ui/app.js` — generalize view-switching; add Trades/Symbols/Settings logic + restart banner.
- `app/ui/styles.css` — table + form styles.
- `tests/unit/test_api_server.py` — tests for the new/extended routes.
- `tests/unit/test_engine_controller.py` — test for `restart()`.

**Unchanged (explicitly):** `src/core`, `src/workers`, the engine/runner, the adapter, the settings store.

---

## Task 1: Paged trades query + endpoint

**Files:**
- Modify: `app/api/trades.py`
- Modify: `app/api/server.py`
- Test: `tests/unit/test_api_server.py`

- [ ] **Step 1: Replace the recent-trades test with a paged-query test**

In `tests/unit/test_api_server.py`, replace the existing `test_recent_trades_newest_first_and_limited` test with:

```python
def test_query_trades_paging_filter_and_total(temp_db_path):
    from datetime import datetime, timedelta
    from src.models.database import init_db
    from src.utils.database_handler import DatabaseHandler
    from app.api.trades import query_trades

    init_db()
    db = DatabaseHandler()
    base = datetime(2026, 6, 14, 12, 0, 0)
    for i in range(5):
        db.save_trade({
            "trade_id": f"T{i}",
            "order_id": f"O{i}",
            "instrument": "EURUSD",
            "side": "buy",
            "quantity": "0.10",
            "type": "market",
            "ask_price": "1.1000",
            "bid_price": "1.0998",
            "tv_request": "{}",
            "tv_response": "{}",
            "status": "completed" if i % 2 == 0 else "failed",
            "created_at": base + timedelta(minutes=i),
        })

    rows, total = query_trades(limit=2, offset=0)
    assert total == 5
    assert [r["trade_id"] for r in rows] == ["T4", "T3"]  # newest first

    rows, total = query_trades(limit=2, offset=2)
    assert [r["trade_id"] for r in rows] == ["T2", "T1"]

    rows, total = query_trades(limit=10, offset=0, status="failed")
    assert total == 2
    assert {r["trade_id"] for r in rows} == {"T1", "T3"}
    db.cleanup()
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `pytest tests/unit/test_api_server.py::test_query_trades_paging_filter_and_total -q`
Expected: FAIL — `cannot import name 'query_trades' from 'app.api.trades'`.

- [ ] **Step 3: Replace `recent_trades` with `query_trades`**

Replace the entire contents of `app/api/trades.py` with:

```python
"""Trade-history reads for the dashboard preview + the Trades tab (Plan 3b)."""
from typing import List, Optional, Tuple

from src.config.database import get_session_factory
from src.models.database import Trade


def _serialize(t) -> dict:
    created = getattr(t, "created_at", None)
    return {
        "trade_id": getattr(t, "trade_id", None),
        "instrument": getattr(t, "instrument", None),
        "side": getattr(t, "side", None),
        "quantity": str(getattr(t, "quantity", "")),
        "status": getattr(t, "status", None),
        "mt5_ticket": getattr(t, "mt5_ticket", None),
        "created_at": created.isoformat() if created else None,
    }


def query_trades(
    limit: int = 50, offset: int = 0, status: Optional[str] = None
) -> Tuple[List[dict], int]:
    """Return (rows, total) — trades newest-first, paged, optionally status-filtered."""
    Session = get_session_factory()
    session = Session()
    try:
        q = session.query(Trade)
        if status:
            q = q.filter(Trade.status == status)
        total = q.count()
        rows = (
            q.order_by(Trade.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [_serialize(t) for t in rows], total
    finally:
        session.close()
```

- [ ] **Step 4: Point the `/api/trades` route at `query_trades`**

In `app/api/server.py`, replace the import line `from app.api.trades import recent_trades` with:

```python
from app.api.trades import query_trades
```

Then replace the `get_trades` route:

```python
    @app.get("/api/trades")
    def get_trades(limit: int = Query(10, ge=1, le=200)):
        return {"trades": recent_trades(limit=limit)}
```

with:

```python
    @app.get("/api/trades")
    def get_trades(
        limit: int = Query(10, ge=1, le=200),
        offset: int = Query(0, ge=0),
        status: str = Query(None),
    ):
        rows, total = query_trades(limit=limit, offset=offset, status=status)
        return {"trades": rows, "total": total}
```

- [ ] **Step 5: Run it — expect PASS**

Run: `pytest tests/unit/test_api_server.py -q`
Expected: PASS (the new query test + existing endpoint tests; the dashboard's `?limit=10` call still works since it reads `.trades`).

- [ ] **Step 6: Commit**

```bash
git add app/api/trades.py app/api/server.py tests/unit/test_api_server.py
git commit -m "$(cat <<'EOF'
feat: paged + status-filtered trades query and endpoint

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: config_api — settings read/write

**Files:**
- Create: `app/api/config_api.py`
- Test: `tests/unit/test_api_config.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_api_config.py`:

```python
import pytest

from app.api.config_api import (SettingsValidationError, get_settings,
                                update_settings)
from app.storage.settings_store import SettingsStore


def test_get_settings_redacts_password_and_marks_set(temp_db_path):
    s = SettingsStore()
    s.set("mt5.account", "123456")
    s.set("mt5.server", "Demo")
    s.set("mt5.terminal_path", "C:/t.exe")
    s.set_secret("mt5.password", "hunter2")
    s.set("tv.broker_url", "broker.example.com")
    s.set("tv.account_id", "999")

    out = get_settings()
    assert out["mt5"]["account"] == 123456
    assert out["mt5"]["server"] == "Demo"
    assert out["mt5"]["terminal_path"] == "C:/t.exe"
    assert out["mt5"]["password_set"] is True
    assert out["tv"] == {"broker_url": "broker.example.com", "account_id": "999"}
    # password value must never be exposed
    import json
    assert "hunter2" not in json.dumps(out)
    assert "password" not in out["mt5"] or out["mt5"].get("password") is None


def test_update_settings_writes_mt5_fields(temp_db_path):
    update_settings({"mt5": {"account": "555", "server": "Live", "terminal_path": "C:/x.exe"}})
    s = SettingsStore()
    assert s.get_int("mt5.account") == 555
    assert s.get("mt5.server") == "Live"
    assert s.get("mt5.terminal_path") == "C:/x.exe"


def test_update_settings_password_only_when_provided(temp_db_path):
    s = SettingsStore()
    s.set_secret("mt5.password", "original")
    update_settings({"mt5": {"server": "X"}})            # no password key -> keep
    assert s.get_secret("mt5.password") == "original"
    update_settings({"mt5": {"password": ""}})            # blank -> keep
    assert s.get_secret("mt5.password") == "original"
    update_settings({"mt5": {"password": "newpw"}})       # value -> update
    assert s.get_secret("mt5.password") == "newpw"


def test_update_settings_rejects_non_integer_account(temp_db_path):
    with pytest.raises(SettingsValidationError):
        update_settings({"mt5": {"account": "abc"}})


def test_update_settings_ignores_tv_target(temp_db_path):
    update_settings({"tv": {"broker_url": "evil", "account_id": "0"}, "mt5": {"server": "S"}})
    s = SettingsStore()
    assert s.get("tv.broker_url") is None  # TV target is read-only here
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/unit/test_api_config.py -q`
Expected: FAIL — `No module named 'app.api.config_api'`.

- [ ] **Step 3: Implement settings part of config_api**

Create `app/api/config_api.py`:

```python
"""Read/write helpers for the Settings and Symbols tabs (Plan 3b).

All values live in the SQLite settings store. The TV target (broker_url/
account_id) is auto-detected from live traffic, so it is exposed read-only here.
The MT5 password is never returned; it is updated only when a new value is given.
"""
import json

from app.storage.settings_store import SettingsStore


class SettingsValidationError(ValueError):
    """Raised on invalid settings/symbols input (maps to HTTP 400)."""


def get_settings() -> dict:
    s = SettingsStore()
    return {
        "mt5": {
            "account": s.get_int("mt5.account"),
            "server": s.get("mt5.server"),
            "terminal_path": s.get("mt5.terminal_path"),
            "password_set": bool(s.get("mt5.password")),
        },
        "tv": {  # read-only — auto-detected from live traffic
            "broker_url": s.get("tv.broker_url"),
            "account_id": s.get("tv.account_id"),
        },
    }


def update_settings(data: dict) -> None:
    """Apply editable MT5 settings. Ignores the (read-only) TV target.

    Password is updated only when a non-empty value is supplied (blank = keep).
    Raises SettingsValidationError on invalid input.
    """
    s = SettingsStore()
    mt5 = data.get("mt5", {}) or {}

    if "account" in mt5 and mt5["account"] not in (None, ""):
        try:
            account = int(mt5["account"])
        except (TypeError, ValueError):
            raise SettingsValidationError("MT5 account must be an integer")
        s.set("mt5.account", str(account))

    if mt5.get("server") is not None:
        s.set("mt5.server", mt5["server"])

    if mt5.get("terminal_path") is not None:
        s.set("mt5.terminal_path", mt5["terminal_path"])

    password = mt5.get("password")
    if password:  # non-empty -> update; None/"" -> keep existing
        s.set_secret("mt5.password", password)
```

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/unit/test_api_config.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add app/api/config_api.py tests/unit/test_api_config.py
git commit -m "$(cat <<'EOF'
feat: config_api settings read/write (MT5 editable, TV read-only, password safe)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: config_api — symbols read/write

**Files:**
- Modify: `app/api/config_api.py`
- Test: `tests/unit/test_api_config.py` (append)

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_api_config.py`:

```python
def test_symbols_roundtrip(temp_db_path):
    from app.api.config_api import get_symbols, update_symbols

    update_symbols({"default_suffix": ".r", "map": {"USTEC": "NAS100", "DE40": "DAX40"}})
    out = get_symbols()
    assert out["default_suffix"] == ".r"
    assert out["map"] == {"USTEC": "NAS100", "DE40": "DAX40"}


def test_symbols_defaults_when_unset(temp_db_path):
    from app.api.config_api import get_symbols

    out = get_symbols()
    assert out["default_suffix"] == ""
    assert out["map"] == {}


def test_update_symbols_rejects_non_dict_map(temp_db_path):
    import pytest
    from app.api.config_api import SettingsValidationError, update_symbols

    with pytest.raises(SettingsValidationError):
        update_symbols({"default_suffix": ".r", "map": ["not", "a", "dict"]})
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/unit/test_api_config.py -k symbols -q`
Expected: FAIL — `cannot import name 'get_symbols'`.

- [ ] **Step 3: Add symbols functions to config_api**

Append to `app/api/config_api.py`:

```python
def get_symbols() -> dict:
    s = SettingsStore()
    suffix = s.get("symbols.default_suffix")
    mapping = s.get_json("symbols.map", {}) or {}
    return {"default_suffix": suffix if suffix is not None else "", "map": mapping}


def update_symbols(data: dict) -> None:
    """Write the default suffix + the TV->MT5 symbol map. Raises on a bad map."""
    s = SettingsStore()
    mapping = data.get("map", {})
    if not isinstance(mapping, dict):
        raise SettingsValidationError("Symbol map must be an object of TV->MT5 pairs")
    clean = {str(k): str(v) for k, v in mapping.items()}
    s.set("symbols.default_suffix", data.get("default_suffix", "") or "")
    s.set("symbols.map", json.dumps(clean))
```

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/unit/test_api_config.py -q`
Expected: PASS (all config tests).

- [ ] **Step 5: Commit**

```bash
git add app/api/config_api.py tests/unit/test_api_config.py
git commit -m "$(cat <<'EOF'
feat: config_api symbols read/write (suffix + TV->MT5 map)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: EngineController.restart()

**Files:**
- Modify: `app/engine_controller.py`
- Test: `tests/unit/test_engine_controller.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_engine_controller.py`:

```python
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
```

(`_FakeRunner` and `EngineState` are already imported/defined earlier in this test file.)

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/unit/test_engine_controller.py -k restart -q`
Expected: FAIL — `EngineController` has no `restart`.

- [ ] **Step 3: Add `restart`**

In `app/engine_controller.py`, add this method to `EngineController` (after `stop`):

```python
    async def restart(self) -> Status:
        """Stop (if running) then start — used to apply settings changes.

        stop() fully releases the proxy port before start() re-checks it, so this
        avoids a client-side stop/start race.
        """
        await self.stop()
        return await self.start()
```

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/unit/test_engine_controller.py -q`
Expected: PASS (all controller tests).

- [ ] **Step 5: Commit**

```bash
git add app/engine_controller.py tests/unit/test_engine_controller.py
git commit -m "$(cat <<'EOF'
feat: EngineController.restart (stop then start)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: API routes — settings, symbols, restart

**Files:**
- Modify: `app/api/server.py`
- Test: `tests/unit/test_api_server.py` (append)

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_api_server.py`:

```python
def test_settings_get_redacts_and_put_writes(temp_db_path):
    from app.storage.settings_store import SettingsStore
    client, _ = _client(temp_db_path)
    SettingsStore().set_secret("mt5.password", "secret")

    r = client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    assert body["mt5"]["password_set"] is True
    assert "secret" not in r.text

    r = client.put("/api/settings", json={"mt5": {"account": "777", "server": "Live"}})
    assert r.status_code == 200
    assert SettingsStore().get_int("mt5.account") == 777


def test_settings_put_rejects_bad_account(temp_db_path):
    client, _ = _client(temp_db_path)
    r = client.put("/api/settings", json={"mt5": {"account": "abc"}})
    assert r.status_code == 400


def test_symbols_get_put(temp_db_path):
    client, _ = _client(temp_db_path)
    r = client.put("/api/symbols", json={"default_suffix": ".r", "map": {"USTEC": "NAS100"}})
    assert r.status_code == 200
    r = client.get("/api/symbols")
    assert r.json() == {"default_suffix": ".r", "map": {"USTEC": "NAS100"}}


def test_symbols_put_rejects_bad_map(temp_db_path):
    client, _ = _client(temp_db_path)
    r = client.put("/api/symbols", json={"default_suffix": ".r", "map": [1, 2]})
    assert r.status_code == 400


def test_restart_endpoint(temp_db_path):
    client, _ = _client(temp_db_path)
    client.post("/api/engine/start")
    r = client.post("/api/engine/restart")
    assert r.status_code == 200
    assert r.json()["engine"] == "running"
    client.post("/api/engine/stop")
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/unit/test_api_server.py -k "settings or symbols or restart" -q`
Expected: FAIL — those routes don't exist (404).

- [ ] **Step 3: Add the routes**

In `app/api/server.py`, update the imports — change:

```python
from fastapi import FastAPI, HTTPException, Query
```

to:

```python
from fastapi import Body, FastAPI, HTTPException, Query
```

and add:

```python
from app.api.config_api import (SettingsValidationError, get_settings,
                                get_symbols, update_settings, update_symbols)
```

Then add these routes inside `create_app` (e.g., after the `stop_engine` route):

```python
    @app.post("/api/engine/restart")
    async def restart_engine():
        try:
            status = await controller.restart()
        except ProxyPortInUseError as e:
            raise HTTPException(status_code=409, detail=str(e))
        return status.to_dict()

    @app.get("/api/settings")
    def read_settings():
        return get_settings()

    @app.put("/api/settings")
    def write_settings(payload: dict = Body(...)):
        try:
            update_settings(payload)
        except SettingsValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"ok": True}

    @app.get("/api/symbols")
    def read_symbols():
        return get_symbols()

    @app.put("/api/symbols")
    def write_symbols(payload: dict = Body(...)):
        try:
            update_symbols(payload)
        except SettingsValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"ok": True}
```

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/unit/test_api_server.py -q`
Expected: PASS (all server tests).

- [ ] **Step 5: Run the full unit suite**

Run: `pytest tests/unit -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/api/server.py tests/unit/test_api_server.py
git commit -m "$(cat <<'EOF'
feat: settings/symbols endpoints + engine restart route

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: UI — view sections + un-grey nav

**Files:**
- Modify: `app/ui/index.html`
- Test: `tests/unit/test_api_server.py` (append serve check)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_api_server.py`:

```python
def test_index_has_all_tabs(temp_db_path):
    client, _ = _client(temp_db_path)
    html = client.get("/").text
    for view in ("view-trades", "view-symbols", "view-settings"):
        assert view in html
    assert "soon" not in html  # future-tab placeholders removed
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/unit/test_api_server.py::test_index_has_all_tabs -q`
Expected: FAIL — the new view sections / un-greyed nav aren't there yet.

- [ ] **Step 3: Replace `app/ui/index.html`**

Replace the entire contents of `app/ui/index.html` with:

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
      <a class="nav-item" data-view="trades">Trades</a>
      <a class="nav-item" data-view="symbols">Symbols</a>
      <a class="nav-item" data-view="settings">Settings</a>
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

      <section id="view-trades" class="view hidden">
        <div class="topbar">
          <div class="lab">TRADES</div>
          <select id="trades-status">
            <option value="">All</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="pending">Pending</option>
          </select>
        </div>
        <table class="grid">
          <thead><tr><th>Time</th><th>Side</th><th>Instrument</th><th>Qty</th><th>Status</th><th>MT5#</th></tr></thead>
          <tbody id="trades-body"></tbody>
        </table>
        <div class="pager">
          <button id="trades-prev" class="btn ghost">‹ Prev</button>
          <span id="trades-range" class="lab"></span>
          <button id="trades-next" class="btn ghost">Next ›</button>
        </div>
      </section>

      <section id="view-symbols" class="view hidden">
        <div class="lab">SYMBOLS</div>
        <div id="symbols-banner" class="banner hidden"></div>
        <label class="field">Default suffix
          <input id="sym-suffix" type="text" placeholder=".r" />
        </label>
        <div class="lab">TradingView → MT5 overrides</div>
        <div id="sym-map"></div>
        <button id="sym-add" class="btn ghost">+ Add row</button>
        <div><button id="sym-save" class="btn start">Save</button></div>
      </section>

      <section id="view-settings" class="view hidden">
        <div class="lab">SETTINGS</div>
        <div id="settings-banner" class="banner hidden"></div>
        <label class="field">MT5 account
          <input id="set-account" type="number" />
        </label>
        <label class="field">MT5 password
          <input id="set-password" type="password" placeholder="•••••• (unchanged)" />
        </label>
        <label class="field">MT5 server
          <input id="set-server" type="text" />
        </label>
        <label class="field">MT5 terminal path
          <input id="set-terminal" type="text" />
        </label>
        <label class="field">TradingView broker (auto-detected)
          <input id="set-tv-broker" type="text" disabled />
        </label>
        <label class="field">TradingView account (auto-detected)
          <input id="set-tv-account" type="text" disabled />
        </label>
        <div><button id="set-save" class="btn start">Save</button></div>
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

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/unit/test_api_server.py::test_index_has_all_tabs -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/ui/index.html tests/unit/test_api_server.py
git commit -m "$(cat <<'EOF'
feat: add Trades/Symbols/Settings view sections; un-grey nav

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: UI — generalized view-switching + Trades view

**Files:**
- Modify: `app/ui/app.js`

- [ ] **Step 1: Generalize view-switching**

In `app/ui/app.js`, replace the existing nav block:

```javascript
document.querySelectorAll('.nav-item[data-view]').forEach(el => {
  el.addEventListener('click', () => {
    document.querySelectorAll('.nav-item[data-view]').forEach(n => n.classList.remove('active'));
    el.classList.add('active');
    const view = el.getAttribute('data-view');
    $('view-dashboard').classList.toggle('hidden', view !== 'dashboard');
    $('view-logs').classList.toggle('hidden', view !== 'logs');
  });
});
```

with:

```javascript
const VIEWS = ['dashboard', 'trades', 'symbols', 'settings', 'logs'];

function showView(view) {
  VIEWS.forEach(v => $('view-' + v).classList.toggle('hidden', v !== view));
  document.querySelectorAll('.nav-item[data-view]').forEach(n =>
    n.classList.toggle('active', n.getAttribute('data-view') === view));
  if (view === 'trades') loadTrades();
  if (view === 'symbols') loadSymbols();
  if (view === 'settings') loadSettings();
}

document.querySelectorAll('.nav-item[data-view]').forEach(el => {
  el.addEventListener('click', () => showView(el.getAttribute('data-view')));
});
```

- [ ] **Step 2: Add the Trades view logic**

Append to `app/ui/app.js`:

```javascript
// --- Trades tab ---
let tradesOffset = 0;
const TRADES_PAGE = 50;

async function loadTrades() {
  const status = $('trades-status').value;
  const url = `/api/trades?limit=${TRADES_PAGE}&offset=${tradesOffset}&status=${encodeURIComponent(status)}`;
  try {
    const d = await (await fetch(url)).json();
    const rows = d.trades || [];
    $('trades-body').innerHTML = rows.map(t => `<tr>
      <td>${t.created_at ? t.created_at.replace('T', ' ').slice(0, 19) : ''}</td>
      <td>${t.side || ''}</td>
      <td>${t.instrument || ''}</td>
      <td>${t.quantity || ''}</td>
      <td>${t.status || ''}</td>
      <td>${t.mt5_ticket || ''}</td>
    </tr>`).join('') || '<tr><td colspan="6">No trades</td></tr>';
    const total = d.total || 0;
    const from = total ? tradesOffset + 1 : 0;
    const to = Math.min(tradesOffset + TRADES_PAGE, total);
    $('trades-range').textContent = `${from}–${to} of ${total}`;
    $('trades-prev').disabled = tradesOffset === 0;
    $('trades-next').disabled = tradesOffset + TRADES_PAGE >= total;
  } catch (e) {}
}

$('trades-status').addEventListener('change', () => { tradesOffset = 0; loadTrades(); });
$('trades-prev').addEventListener('click', () => { tradesOffset = Math.max(0, tradesOffset - TRADES_PAGE); loadTrades(); });
$('trades-next').addEventListener('click', () => { tradesOffset += TRADES_PAGE; loadTrades(); });
```

- [ ] **Step 3: Verify the app still imports/serves (no Python change; sanity)**

Run: `pytest tests/unit/test_api_server.py -q`
Expected: PASS (no regression; JS isn't unit-tested but the page still serves).

- [ ] **Step 4: Commit**

```bash
git add app/ui/app.js
git commit -m "$(cat <<'EOF'
feat: generalized view-switching + Trades tab (paged table + status filter)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: UI — Symbols + Settings views + restart banner + styles

**Files:**
- Modify: `app/ui/app.js`
- Modify: `app/ui/styles.css`

- [ ] **Step 1: Track engine state for the restart banner**

In `app/ui/app.js`, inside `refreshStatus`, immediately after `const running = s.engine === 'running';`, add:

```javascript
    window._engineRunning = running;
```

- [ ] **Step 2: Add Symbols + Settings logic**

Append to `app/ui/app.js`:

```javascript
// --- Symbols tab ---
function symbolRow(tv = '', mt5 = '') {
  const div = document.createElement('div');
  div.className = 'map-row';
  div.innerHTML = `<input class="map-tv" placeholder="BTCUSD" value="${tv}" />
    <span>→</span>
    <input class="map-mt5" placeholder="BTCUSD.r" value="${mt5}" />
    <button class="btn ghost map-del">✕</button>`;
  div.querySelector('.map-del').addEventListener('click', () => div.remove());
  return div;
}

async function loadSymbols() {
  try {
    const d = await (await fetch('/api/symbols')).json();
    $('sym-suffix').value = d.default_suffix || '';
    const box = $('sym-map');
    box.innerHTML = '';
    Object.entries(d.map || {}).forEach(([tv, mt5]) => box.appendChild(symbolRow(tv, mt5)));
  } catch (e) {}
}

$('sym-add').addEventListener('click', () => $('sym-map').appendChild(symbolRow()));

$('sym-save').addEventListener('click', async () => {
  const map = {};
  document.querySelectorAll('#sym-map .map-row').forEach(r => {
    const tv = r.querySelector('.map-tv').value.trim();
    const mt5 = r.querySelector('.map-mt5').value.trim();
    if (tv) map[tv] = mt5;
  });
  const body = { default_suffix: $('sym-suffix').value.trim(), map };
  const r = await fetch('/api/symbols', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  showSaveResult($('symbols-banner'), r);
});

// --- Settings tab ---
async function loadSettings() {
  try {
    const d = await (await fetch('/api/settings')).json();
    $('set-account').value = d.mt5.account ?? '';
    $('set-server').value = d.mt5.server || '';
    $('set-terminal').value = d.mt5.terminal_path || '';
    $('set-password').value = '';
    $('set-password').placeholder = d.mt5.password_set ? '•••••• (unchanged)' : 'not set';
    $('set-tv-broker').value = d.tv.broker_url || '';
    $('set-tv-account').value = d.tv.account_id || '';
  } catch (e) {}
}

$('set-save').addEventListener('click', async () => {
  const mt5 = {
    account: $('set-account').value.trim(),
    server: $('set-server').value.trim(),
    terminal_path: $('set-terminal').value.trim(),
  };
  const pw = $('set-password').value;
  if (pw) mt5.password = pw;
  const r = await fetch('/api/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mt5 }) });
  showSaveResult($('settings-banner'), r, true);
});

// --- shared save-result + restart banner ---
async function showSaveResult(banner, resp, reload) {
  if (!resp.ok) {
    const j = await resp.json().catch(() => ({}));
    banner.textContent = j.detail || 'Save failed';
    banner.className = 'banner';
    return;
  }
  if (reload) loadSettings();
  if (window._engineRunning) {
    banner.innerHTML = 'Saved — restart the engine to apply. <button id="restart-now" class="btn start">Restart engine</button>';
    banner.className = 'banner ok';
    $('restart-now').addEventListener('click', async () => {
      banner.textContent = 'Restarting…';
      await fetch('/api/engine/restart', { method: 'POST' });
      refreshStatus();
      banner.textContent = 'Engine restarted.';
    });
  } else {
    banner.textContent = 'Saved.';
    banner.className = 'banner ok';
  }
}
```

- [ ] **Step 3: Add styles**

Append to `app/ui/styles.css`:

```css
.grid { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e1e5ea; border-radius: 8px; overflow: hidden; }
.grid th, .grid td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #f0f2f5; font-size: 13px; }
.grid th { background: #f5f7fa; color: #6b7484; font-size: 11px; text-transform: uppercase; }
.pager { display: flex; align-items: center; gap: 12px; margin-top: 12px; }
.btn.ghost { background: #e8ecf2; color: #1f2430; }
.btn:disabled { opacity: .5; cursor: default; }
.field { display: block; margin: 10px 0; font-size: 12px; color: #6b7484; }
.field input { display: block; width: 360px; max-width: 100%; margin-top: 4px; padding: 7px 9px; border: 1px solid #cfd6e4; border-radius: 5px; font-size: 14px; color: #1f2430; }
.field input:disabled { background: #eef1f5; color: #6b7484; }
.map-row { display: flex; align-items: center; gap: 8px; margin: 6px 0; }
.map-row input { padding: 6px 8px; border: 1px solid #cfd6e4; border-radius: 5px; }
.banner.ok { background: #e6f4ea; color: #137333; }
select#trades-status { padding: 6px 10px; border: 1px solid #cfd6e4; border-radius: 5px; }
```

- [ ] **Step 4: Verify the page still serves + full suite**

Run: `pytest tests/unit -q`
Expected: PASS (all unit tests).

- [ ] **Step 5: Commit**

```bash
git add app/ui/app.js app/ui/styles.css
git commit -m "$(cat <<'EOF'
feat: Symbols + Settings tabs with save + one-click engine restart

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Full unit suite**

Run: `pytest tests/unit -q`
Expected: PASS (all tests across the suite).

- [ ] **Step 2: Whole-tree collection (no import errors)**

Run: `pytest --collect-only -q` (tail the output)
Expected: collection succeeds, no import errors.

- [ ] **Step 3: Engine module + UI serve smoke**

Run: `python -c "import app.api.server, app.api.config_api, app.api.trades, app.engine_controller; print('ok')"`
Expected: prints `ok`.

> **Manual end-to-end (cannot be unit-tested):** launch `python run.py desktop`.
> - **Trades** tab: shows full history newest-first; status filter narrows; Prev/Next pages; range text updates.
> - **Symbols** tab: loads current suffix + map; add/remove rows; Save → "Saved" (or restart banner if running); the mapping change takes effect after a restart.
> - **Settings** tab: shows MT5 fields + read-only TV target; password field never shows the real value; edit a field → Save → **Restart engine** button appears (when running) → click → engine restarts and reconnects with the new value.
> - Confirm the MT5 password never appears in the UI or in any `/api/settings` response.

- [ ] **Step 4: Commit (if any verification-only doc notes were added; otherwise skip)**

No code changes in this task.

---

## Self-Review (completed during planning)

**Spec coverage (Plan 3b):**
- Trades: paged history + status filter → Task 1 (`query_trades` + endpoint) + Task 7 (UI). ✅
- Symbols: edit suffix + map → Task 3 (config_api) + Task 5 (routes) + Task 8 (UI). ✅
- Settings: MT5 editable, TV read-only, password redacted/keep-on-blank → Task 2 (config_api) + Task 5 (routes) + Task 8 (UI). ✅
- Restart engine button + `POST /api/engine/restart` → Task 4 (controller) + Task 5 (route) + Task 8 (UI banner). ✅
- Generalized view-switching + un-grey nav → Task 6 (HTML) + Task 7 (JS). ✅
- Apply-on-restart banner semantics → Task 8 (`showSaveResult` uses `window._engineRunning`). ✅
- No engine/trade-path changes → no task touches `src/core`/`src/workers`/runner/adapter. ✅

**Placeholder scan:** No TBD/TODO; every code step has full code; commands have expected output. ✅

**Type/name consistency:**
- `query_trades(limit, offset, status) -> (rows, total)` (Task 1) consumed by `/api/trades` (Task 1) and the JS `loadTrades` (Task 7). ✅
- `get_settings`/`update_settings`/`get_symbols`/`update_symbols`/`SettingsValidationError` (Tasks 2–3) imported + used by routes (Task 5). ✅
- Response shapes: `/api/settings` `{mt5:{account,server,terminal_path,password_set}, tv:{broker_url,account_id}}` (Task 2) matches `loadSettings` (Task 8); `/api/symbols` `{default_suffix, map}` (Task 3) matches `loadSymbols`/save (Task 8); `/api/trades` `{trades, total}` (Task 1) matches `loadTrades` (Task 7). ✅
- `EngineController.restart()` (Task 4) called by `/api/engine/restart` (Task 5), surfaced by the UI restart button (Task 8). ✅
- DOM ids in `index.html` (Task 6) match every `$()` lookup in `app.js` (Tasks 7–8): `trades-status/trades-body/trades-range/trades-prev/trades-next`, `sym-suffix/sym-map/sym-add/sym-save/symbols-banner`, `set-account/set-password/set-server/set-terminal/set-tv-broker/set-tv-account/set-save/settings-banner`. ✅
