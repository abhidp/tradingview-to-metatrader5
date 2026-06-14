# TV2MT5 Desktop — Plan 3b Design: Content Tabs (Trades / Symbols / Settings)

**Date:** 2026-06-14
**Status:** Approved for planning
**Author:** Abhi D (with Claude)
**Parent spec:** `docs/superpowers/specs/2026-06-13-tv2mt5-desktop-design.md`
**Builds on:** `docs/superpowers/specs/2026-06-14-tv2mt5-plan-03a-app-shell-design.md`
**Roadmap row:** Plan 3 (App Shell), part b of the 3a/3b split.

## Problem

Plan 3a shipped the app shell with a working Dashboard and Logs tab; the
Trades, Symbols, and Settings sidebar items are present but greyed "soon". A
non-technical trader currently can't review full trade history, change the
symbol suffix/map, or edit their MT5 credentials without hand-editing the
SQLite `settings` table.

## Goal

Fill in the three remaining tabs as read/write views over the **existing**
SQLite `settings` store and `trades` table, reusing the Plan 3a FastAPI + vanilla
JS shell. No changes to the engine or the trade interception/execution path.

## Non-Goals (deferred)

- Onboarding wizard + auto proxy set/revert — Plan 4.
- Rich trade filters (by instrument / date range) — only a status filter in 3b.
- Auto-applying settings without an engine restart — the engine reads config at
  Start; 3b surfaces a one-click restart instead of live reconfiguration.
- Packaging — Plan 6.
- No change to `src/core`, `src/workers`, the engine, or the adapter.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Settings editability | Edit **MT5** fields (account / password / server / terminal_path); show **TV target** (broker_url / account_id) **read-only** | TV target is auto-detected from live traffic; manual edits would be overwritten and confuse. MT5 creds need a UI. |
| Secret handling | `GET /api/settings` never returns the password (returns a `mt5.password_set` flag); `PUT` updates it **only if a new value is supplied** (blank = keep) | Don't leak the secret to the UI; allow changing it without forcing re-entry. |
| Apply semantics | Edits take effect on the next engine **Start**; a save while RUNNING shows a banner with a one-click **Restart engine** button | The engine reads config at Start; restart is simpler and safer than live reconfiguration. |
| Restart | `POST /api/engine/restart` = `controller.stop()` then `controller.start()` in the engine loop | `stop()` fully releases port 8080 before `start()` re-checks it; avoids a client-side stop/start race. |
| Trades depth | Full history, newest-first, **paged** (limit/offset) + a **status filter** | Covers "what happened / what failed"; richer filters deferred. |
| Symbols | Edit `symbols.default_suffix` + the `symbols.map` (add/remove key→value rows) | The two symbol-mapping knobs already in the store. |
| Frontend | Extend the Plan 3a vanilla HTML/CSS/JS; generalize view-switching to all 5 views | Consistent with 3a; zero build step. |

## Architecture

Extends the Plan 3a shell (one FastAPI app served into the WebView2 window; engine
on the shared loop via `EngineController`). 3b adds JSON endpoints + three UI views;
it does not touch the process model.

## Components

### API (`app/api/`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/trades?limit&offset&status` | `{trades, total}` — paged history, newest-first; optional `status` filter. Dashboard's existing `?limit=10` call keeps working (offset defaults 0, status optional). |
| GET | `/api/symbols` | `{default_suffix, map}` from the store. |
| PUT | `/api/symbols` | Body `{default_suffix, map}` → writes `symbols.default_suffix` and `symbols.map` (JSON-encoded). |
| GET | `/api/settings` | Editable MT5 fields + read-only TV target; password redacted to a `mt5.password_set` bool. |
| PUT | `/api/settings` | Writes `mt5.account` (int-validated), `mt5.server`, `mt5.terminal_path`, and `mt5.password` only when a non-empty value is provided (via `set_secret`). |
| POST | `/api/engine/restart` | `await controller.stop()` then `await controller.start()`; returns `Status` (or 409 if 8080 busy). |

New query module `app/api/trades.py` gains `query_trades(limit, offset, status) -> (rows, total)` alongside the existing `recent_trades`. Settings/symbols read/write go through the existing `SettingsStore` (`get`/`set`/`get_int`/`get_json`/`get_secret`/`set_secret`).

### UI (`app/ui/`)

- Generalize `app.js` view-switching: iterate all `.nav-item[data-view]` and toggle the matching `#view-*` section (replaces the hardcoded dashboard/logs toggle). Un-grey Trades/Symbols/Settings nav items (give them `data-view`).
- **Trades view:** a table (time, side, instrument, qty, status, MT5#) with a status `<select>` (all / completed / failed / pending) and paging (Prev/Next over limit/offset using `total`).
- **Symbols view:** a `default_suffix` text field and an editable list of `TV symbol → MT5 symbol` rows (add/remove), with Save.
- **Settings view:** an MT5 form (account, password [placeholder "•••• unchanged"], server, terminal_path), disabled TV target fields, and Save. After a successful Save while the engine is RUNNING, show a banner: *"Saved — restart the engine to apply"* with a **Restart engine** button (→ `POST /api/engine/restart`).

## Data Flow

- **Trades:** view fetches `/api/trades?limit=50&offset=N&status=…`; renders the table + paging from `{trades, total}`.
- **Symbols/Settings:** view GETs current values on open; Save issues the PUT, then shows success/restart banner (banner's restart button appears only when `/api/status` reports `engine == running`).
- **Restart:** button → `POST /api/engine/restart` → refresh status.

## Error Handling

- `PUT /api/settings` with non-integer `mt5.account` → 400 + message; UI shows it inline.
- `PUT /api/symbols` with a malformed map → 400 + message.
- Password never serialized in any GET response.
- Failed saves/restart surface the API `detail` in a banner.
- `/api/engine/restart` maps `ProxyPortInUseError` to 409 (same as start).
- Empty `trades` table → `{trades: [], total: 0}`.

## Testing

- **Unit (pytest + FastAPI TestClient + `temp_db_path`):**
  - `query_trades`: paging (limit/offset), status filter, `total` count, newest-first.
  - `GET /api/settings`: password redacted to `mt5.password_set`; TV target present as read-only.
  - `PUT /api/settings`: writes MT5 fields; blank password keeps the existing secret; non-int account → 400.
  - `GET`/`PUT /api/symbols`: suffix + map round-trip; malformed map → 400.
  - `POST /api/engine/restart`: drives stop→start on a fake-runner controller (RUNNING→…→RUNNING); 409 path.
- **Manual E2E:** edit MT5 creds → Restart engine → reconnects with new creds; edit suffix/map → reflected in mapping; Trades tab pages + status-filters; password never visible in the UI/network.

## Future (not in scope)

- Auto-restart-on-save (vs the explicit button).
- Rich trade filters (instrument, date range), CSV export.
- Plan 4 wizard reuses the Settings/Symbols endpoints for first-run setup.
