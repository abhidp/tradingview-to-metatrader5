# TV2MT5 Desktop — Design Spec

**Date:** 2026-06-13
**Status:** Approved for planning
**Author:** Abhi D (with Claude)

## Problem

The current TradingView→MetaTrader5 copier works but requires Docker Desktop,
a Python venv, `pip install`, manual mitmproxy certificate install, hand-editing
a `.env` file, manually locating `TV_BROKER_URL` / `TV_ACCOUNT_ID`, and running
two terminals. Non-technical traders cannot complete this. The repo receives
hundreds of requests to make it installable and one-click.

## Goal

Repackage the tool as a **single-click Windows desktop app** that any
non-technical trader can install and run. Build **local-first** (for the
author's own testing now) but **architect so it can be monetized later** without
a rewrite.

## Non-Goals

- Not a cloud service yet (no backend stood up; monetization features are seams/stubs).
- Not multi-broker on day one (Fusion Markets only; pluggable for later).
- Not cross-platform (Windows-only; MT5 Python API + WebView2 are Windows-bound).
- Not a rewrite of the trade interception/execution logic, which already works.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Strategy | Evolve repo (collapse + wrap), not rewrite | Interception/execution is the hard, proven part; keep it. |
| Signal source | Fusion Markets via TV broker panel | Current working setup; user trades in TV's broker panel. |
| Broker support | Fusion now, pluggable adapter later | "Local now, monetize later" — additive, not a rewrite. |
| Persistence | SQLite (replaces PostgreSQL) | Single user needs no DB server; ports the `trades` schema. |
| Queue | In-process `asyncio` queue (replaces Redis) | One user, one process — pub/sub is overkill. |
| Process model | One process (proxy + worker + UI + tray) | Eliminates two-terminal setup. |
| UI | FastAPI + `pywebview` on WebView2 + `pystray` | Modern UI, lean bundle (WebView2 preinstalled), reusable as future cloud dashboard. |
| UI layout | Sidebar nav (Dashboard/Trades/Symbols/Settings/Logs) | Product-like, scales with features. |
| Monetization | Pure seams/stubs (license, update, telemetry, errors) | Lowest commitment; nothing external wired during local testing. |
| Packaging | PyInstaller one-folder → Inno Setup `.exe` | Standard, no Docker, signable later. |

## Architecture

Single Python process, one `asyncio` event loop, hosting:

```
┌─────────────────────────────────────────────────────────┐
│  TV2MT5 Desktop (single process)                          │
│                                                            │
│  pystray tray ──── pywebview window (WebView2)            │
│        │                    │                             │
│        │            FastAPI (local UI + JSON API)         │
│        │                    │   ← future cloud API seam   │
│  ┌─────┴────────────────────┴──────────────────────────┐ │
│  │  Core engine (asyncio)                               │ │
│  │   mitmproxy addon (interceptor)                      │ │
│  │     → BrokerAdapter (FusionMarketsAdapter)           │ │
│  │     → in-process asyncio.Queue                       │ │
│  │     → TradeHandler → MT5Service → MetaTrader5 API    │ │
│  │   SQLite (trades, settings)                          │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│  Seams (stubbed): LicenseService · Updater ·              │
│                   Telemetry · ErrorReporter                │
└─────────────────────────────────────────────────────────┘
        │ auto-sets Windows system proxy on Start
        │ reverts on Stop
   TradingView (browser/desktop) traffic → localhost proxy
```

### Components

**Kept from current repo (logic preserved, dependencies retargeted):**
- `src/core/interceptor.py` — mitmproxy addon capturing TV traffic.
- `src/core/trade_handler.py` — async order/execution/TP-SL processing.
- `src/services/mt5_service.py` — MT5 API wrapper.
- `src/utils/symbol_mapper.py` — TV→MT5 symbol translation.
- `src/utils/token_manager.py` — TV auth token capture/refresh.

**New:**
- `app/main.py` — single entrypoint: starts event loop, FastAPI, tray, webview.
- `app/api/` — FastAPI routes serving UI + JSON API (status, trades, settings, control).
- `app/ui/` — web frontend (sidebar nav: Dashboard/Trades/Symbols/Settings/Logs).
- `app/tray.py` — pystray icon (Start/Stop/Open/Quit + status).
- `app/wizard/` — first-run onboarding logic (cert, MT5 detect, TV auto-detect).
- `app/proxy_manager.py` — set/revert Windows system proxy around Start/Stop.
- `app/storage/sqlite_store.py` — SQLite persistence (replaces Postgres handler).
- `app/queue/inproc_queue.py` — asyncio queue (replaces Redis pub/sub).
- `app/adapters/base.py` — `BrokerAdapter` interface.
- `app/adapters/fusion_markets.py` — first adapter impl.
- `app/seams/` — `LicenseService`, `Updater`, `Telemetry`, `ErrorReporter` (stubs).

**Cut:**
- Docker, `docker-compose.yml`, PostgreSQL, Redis, 20-connection pool.
- Manual `.env` workflow (replaced by settings UI + SQLite settings table).
- Separate `start_proxy.py` / `start_worker.py` two-terminal flow.

### Interfaces (seams)

```python
class BrokerAdapter(Protocol):
    def matches(self, flow) -> bool: ...          # is this flow ours?
    def detect_account(self, flow) -> AccountInfo | None: ...
    def parse_trade(self, flow) -> TradeSignal | None: ...

class LicenseService(Protocol):
    def is_valid(self) -> LicenseStatus: ...       # local stub returns VALID

class Updater(Protocol):
    def check(self) -> UpdateInfo | None: ...      # no-op now

class Telemetry(Protocol):
    def event(self, name: str, props: dict) -> None: ...   # local log now

class ErrorReporter(Protocol):
    def capture(self, err: Exception, ctx: dict) -> None: ... # local log now
```

## Onboarding Wizard (first run)

1. **Welcome** — what it does, safety note (credentials stay local).
2. **Security certificate** — one-click auto-install of the mitmproxy cert.
3. **MT5 account** — auto-detect terminal path; enter account/password/server; **Test connection**.
4. **Connect TradingView** — user places one small test trade in TV's broker
   panel; app auto-detects `broker_url` + `account_id` and confirms by capturing
   the trade. (Opening the panel alone can detect IDs; the test trade also proves
   end-to-end copy.)
5. **Symbols** — auto-suggest default suffix (e.g. `.r`); advanced/optional overrides.
6. **Done** — Start Copying.

**Automatic, no user action:** Windows system proxy set on Start / reverted on
Stop; SQLite + queue in-process; local rotating logs.

## Error Handling

- Connection problems (MT5 terminal down, TV traffic not routed, cert missing,
  proxy not set) surface as **clear UI banner states**, never raw stack traces.
- Each copied trade shows explicit ✓ / ✗ with a human-readable reason.
- All errors written to a local rotating log file, viewable in the Logs tab.
- On Stop/crash, the proxy_manager reverts Windows proxy settings so the user's
  internet is never left broken.

## Testing

- Retarget existing `run.py test-*` infra checks to SQLite (drop test-db/redis
  for Docker; add a SQLite smoke test).
- Unit tests for `FusionMarketsAdapter.parse_trade` / `detect_account` using
  captured sample payloads (the most fragile surface).
- Unit tests for `symbol_mapper` translation rules.
- Manual end-to-end validation via the wizard's Step 4 test-trade.

## Packaging & Distribution

- **PyInstaller** one-folder build of the single entrypoint.
- **Inno Setup** wraps it into an `.exe` installer.
- App data + SQLite live in `%APPDATA%\TV2MT5`.
- Code signing and GitHub-Releases-based auto-update are deferred (Updater seam
  exists for later).

## Future (monetization path, not in scope now)

- Real `LicenseService`: Ed25519-signed offline keys, public key embedded in app.
- Real `Updater`: GitHub Releases + static `version.json`.
- Real `Telemetry`/`ErrorReporter`: Sentry + PostHog free tiers.
- Cloud config sync + the FastAPI JSON API repointed at a hosted backend.
- Additional `BrokerAdapter` implementations.
