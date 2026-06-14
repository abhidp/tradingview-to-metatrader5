# TV2MT5 Desktop — Plan 3a Design: App Shell Foundation (UI + Tray)

**Date:** 2026-06-14
**Status:** Approved for planning
**Author:** Abhi D (with Claude)
**Parent spec:** `docs/superpowers/specs/2026-06-13-tv2mt5-desktop-design.md`
**Roadmap row:** Plan 3 (App Shell) of `docs/superpowers/plans/2026-06-13-tv2mt5-desktop-plan-roadmap.md`, split into 3a (this) + 3b (content tabs).

## Problem

After Plans 1–2 the copier runs as a single headless process (`python -m app`)
that blocks on `master.run()` forever. A non-technical trader has no way to
start/stop it, see whether it is working, or read what happened — and there is
**no guard against running two engines at once**, which silently breaks MT5
execution via single-terminal IPC contention (the confusing "trades not copying"
episode found during Plan 2 verification).

## Goal

Wrap the proven engine in a **single-process Windows desktop app**: a WebView2
window plus a tray icon that **Start/Stops** the engine and shows live status and
logs, with single-instance and proxy-port guards. The engine's trade
interception/execution is unchanged — this plan is the shell around it.

## Non-Goals (deferred)

- **Trades / Symbols / Settings tabs** — Plan 3b. In 3a they appear in the sidebar
  but greyed as "soon".
- **Editing settings from the UI** — Plan 3b (the store is written by seed/auto-detect
  for now).
- **Auto-setting the Windows/TradingView proxy** — Plan 4 (onboarding wizard).
- **Packaging / installer** — Plan 6.
- No change to `trade_handler` / `mt5_service` / the interception logic.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Process model | One background asyncio loop hosts **uvicorn + the engine as a cancellable task**; pywebview on the main thread; pystray on its own thread | pywebview must own the main thread on Windows; putting the engine in the same loop as the API makes Start/Stop trivial in-loop task control (no cross-thread engine signaling); one process keeps the MT5 single-terminal constraint satisfied. |
| Start/Stop | In-loop `create_task` / `master.shutdown()`+cancel via an `EngineController` | The control endpoints run in the engine's loop, so they manage its task directly. |
| Frontend | Vanilla HTML/CSS/JS served by FastAPI | Zero build step, leanest PyInstaller bundle (Plan 6), enough for status + logs. |
| Live updates | UI **polls** the JSON API (~1.5s) | Robust and simple; no SSE/WebSocket complexity for 3a. |
| Singleton guard | Bind the app's **single FastAPI port** (the same one that serves the UI + JSON API, e.g. `127.0.0.1:8420`) at startup; if taken, another instance is running → best-effort focus it, then exit | One port for UI + API + guard; loud, simple, cross-process. |
| Proxy-port guard | On Start, check `127.0.0.1:8080` is free; if not, return a clear UI error (no crash) | The Plan 2 carry-forward fix for concurrent-engine MT5 contention. |
| Window close vs Quit | Close → hide to tray (engine keeps running); **Quit** (tray) → stop engine + exit | Standard tray-app behaviour; closing the window shouldn't kill a running copier. |
| Dashboard layout | **Layout A** — status pill + Start/Stop, connection cards (TV / MT5 / Proxy), recent-activity strip | Chosen in brainstorming; status-at-a-glance. |
| Recent activity | Compact preview of the **last ~10 trades** from the `trades` table | Glanceable; full scrollable history is the 3b Trades tab. No history is lost (all trades persist in SQLite). |
| Future tabs | Shown in the sidebar but **greyed "soon"** | Users see the product's final shape from day one. |

## Architecture

Single process, three threads:

```
┌──────────────────────────────────────────────────────────────┐
│ TV2MT5 Desktop (one process)                                   │
│                                                                │
│  MAIN THREAD ── pywebview window (WebView2) → http://127.0.0.1:<app_port>/
                 (<app_port> = the single FastAPI port: UI + API + singleton guard)
│                                                                │
│  BG THREAD ──── asyncio loop                                   │
│    ├─ uvicorn(FastAPI)  : serves UI + JSON API                 │
│    └─ EngineController  : engine as a start/stoppable task     │
│         └─ run_engine wiring (mitmproxy + MT5 worker) [Plan 1/2]│
│                                                                │
│  TRAY THREAD ── pystray icon (Start / Stop / Open / Quit + status)
│                                                                │
│  Guards: control-port singleton · 8080 free-before-Start       │
└──────────────────────────────────────────────────────────────┘
```

### Components (new)

- `app/desktop.py` — desktop entrypoint: acquire singleton → launch the FastAPI/asyncio
  background thread → launch the tray thread → run the webview on the main thread →
  on window Quit, stop the engine and shut down cleanly.
- `app/engine_controller.py` — `EngineController`: owns the engine lifecycle and state.
- `app/api/__init__.py`, `app/api/server.py` — FastAPI app (JSON API + static UI mount).
- `app/tray.py` — pystray icon + menu; calls the controller via the API (or a shared handle).
- `app/singleton.py` — control-port single-instance guard + best-effort focus.
- `app/ui/index.html`, `app/ui/app.js`, `app/ui/styles.css` — sidebar nav (Dashboard +
  Logs active; Trades/Symbols/Settings greyed "soon"), Dashboard layout A, Logs view.

### Modified

- `app/engine.py` — extract the `run_engine` body into a form `EngineController` can
  start/stop (build master + worker, run until stopped, clean up). `python -m app`
  (headless) keeps working by delegating to the controller. No change to what gets wired.
- `app/__main__.py` — unchanged entry for headless; the desktop app is launched via
  `app/desktop.py` (and later `run.py`/the installer).
- `requirements.txt` — add `fastapi`, `uvicorn`, `pywebview`, `pystray`, `pillow`.

## Interfaces

```python
# app/engine_controller.py
class EngineState(str, Enum):
    STOPPED = "stopped"; STARTING = "starting"; RUNNING = "running"
    STOPPING = "stopping"; ERROR = "error"

@dataclass
class Status:
    engine: EngineState
    tv: dict        # {"connected": bool, "account": str | None, "broker_url": str | None}
    mt5: dict       # {"connected": bool, "account": int | None, "server": str | None}
    proxy: dict     # {"listening": bool, "port": int}
    error: str | None = None

class EngineController:
    async def start(self) -> Status: ...   # guards 8080; create_task(engine); STARTING→RUNNING
    async def stop(self) -> Status: ...     # master.shutdown() + cancel worker; →STOPPED
    def status(self) -> Status: ...         # snapshot derived from controller/worker/interceptor
```

**FastAPI routes** (`app/api/server.py`):

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/status` | current `Status` (polled by UI) |
| POST | `/api/engine/start` | start the engine; returns `Status` (or 409 + message if 8080 busy) |
| POST | `/api/engine/stop` | stop the engine; returns `Status` |
| GET | `/api/logs?after=<cursor>` | new log lines from `%APPDATA%/TV2MT5/logs/tv2mt5.log` since cursor |
| GET | `/api/trades?limit=10` | most recent trades (newest first) from the `trades` table |
| POST | `/api/focus` | raise the existing window (used by a second instance) |
| GET | `/` + `/static/*` | serve `app/ui/` |

**Singleton** (`app/singleton.py`): attempt to bind the control port on startup. Bound
already → POST `/api/focus` to the running instance (best effort), then exit with a
clear message. Free → keep the bound socket for uvicorn.

## Data Flow

- **Status:** webview JS polls `GET /api/status` every ~1.5s and renders the pill,
  connection cards, and Start/Stop button state.
- **Start:** UI/tray → `POST /api/engine/start` → controller verifies `8080` is free
  (else 409 + banner), then `create_task` of the engine; status goes `STARTING`→`RUNNING`
  once mitmproxy is listening and the worker has initialised.
- **Stop:** `POST /api/engine/stop` → `master.shutdown()` + cancel worker + cleanup →
  `STOPPED`.
- **Logs:** UI polls `GET /api/logs?after=<cursor>`; server returns new lines + a new
  cursor (byte offset / line count) from the rotating log file.
- **Recent activity:** Dashboard calls `GET /api/trades?limit=10` and renders newest-first.

## Error Handling

- **8080 in use on Start** → `409` with `"Proxy port 8080 is in use — another copier may
  be running."`; UI shows a banner; no crash. (Plan 2 carry-forward.)
- **MT5 connect fails / terminal down** → `engine: error` with a human-readable reason;
  UI banner; Start button returns to actionable state.
- **Engine task dies unexpectedly** → controller catches, sets `ERROR` with the reason,
  surfaces it in `/api/status`.
- **Second instance** → control port bound → focus the first window, exit with a message.
- **Window close** → hide to tray (engine keeps running); **Quit** → stop engine + exit.

## Testing

- **Unit (pytest):**
  - `EngineController` start/stop state transitions with a mocked master/worker
    (STOPPED→STARTING→RUNNING→STOPPING→STOPPED; ERROR on failure; 8080-busy guard).
  - `singleton` — second bind detects the port in use; focus call best-effort.
  - FastAPI endpoints via `TestClient` with a fake controller: `/api/status`,
    `/api/engine/start` (success + 409), `/api/engine/stop`, `/api/logs` (cursor paging),
    `/api/trades` (limit, newest-first).
  - Log tailer (cursor advance over appended lines) and `Status` serialization.
- **Manual end-to-end:** launch the desktop app → window + tray appear → **Start** →
  place a TradingView trade → it copies to MT5 and the Dashboard status + recent-activity
  update → **Stop** → closing the window hides to tray (engine still running if started) →
  **Quit** exits cleanly → launching a second time focuses the first window.

## Future (not in scope)

- **Plan 3b:** Trades (full scrollable/filterable history), Symbols (suffix/map edit),
  Settings (view/edit all keys incl. secrets) tabs — all read/write the existing
  SQLite store + `trades` table.
- **Plan 4:** onboarding wizard + auto proxy set/revert.
- **Plan 6:** PyInstaller one-folder + Inno Setup installer; the desktop entry becomes
  the packaged executable.
