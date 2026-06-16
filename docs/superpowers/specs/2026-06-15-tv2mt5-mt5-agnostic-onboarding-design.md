# TV2MT5 — MT5-Agnostic Onboarding & Broker Profiles Design Spec

**Date:** 2026-06-15
**Status:** Approved for planning
**Author:** Abhi D (with Claude)
**Branch:** `plan-07-mt5-agnostic` (off `v2-desktop`)
**Parent context:** v2 desktop app (`docs/superpowers/specs/2026-06-13-tv2mt5-desktop-design.md`); follows Plan 6 packaging (merged PR #56).

## Problem

The packaged app is meant for community distribution, but MT5 setup is not broker/path
agnostic:

1. **Terminal detection is too narrow.** `find_mt5_terminals()` only scans
   `%APPDATA%\Roaming` and requires "MT5"/"MetaTrader 5" in the folder name. It misses
   terminals installed under `C:\Program Files\...` (e.g. Vantage) and brokers with
   differently-named folders. When detection fails or returns the wrong terminal,
   `mt5.initialize()` launches the system-default terminal — the wrong broker — causing
   intermittent `Failed to select symbol` errors.
2. **The terminal field is a bare text box.** Both the onboarding wizard and the Settings
   tab expect the user to type/paste a path; when multiple terminals exist the wizard
   just grabs the first. Non-technical traders cannot do this reliably.
3. **No fast way to switch brokers.** Changing brokers means hand-editing several
   Settings fields (terminal, account, server, password, symbol suffix) every time.

## Goal

Make MT5 setup work for any trader on any machine, and make switching brokers a one-click
operation. Two phases, each independently shippable:

- **Phase 7a — Detection + picker + Browse:** robust multi-location terminal detection, a
  dropdown picker + native "Browse…" file dialog in both the wizard and Settings.
- **Phase 7b — Broker profiles:** save named broker setups (MT5 connection + symbols) and
  switch between them with one click (auto-restarting the engine).

## Non-Goals

- No change to the trade interception/execution engine or `mt5_service` connection logic
  (profiles write into the existing live config keys the engine already reads).
- TV broker target (`tv.broker_url`/`tv.account_id`) stays **global and auto-detected**
  from live traffic — it is not part of a profile.
- Not cross-platform (Windows-only; same as the rest of v2).
- No cloud sync of profiles; profiles live in the local SQLite settings store.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Profile contents | MT5 connection (terminal/account/password/server) **+ symbols** (suffix + map) | A broker switch usually changes the suffix too; bundling makes switching complete. |
| TV target in profiles | No — stays global/auto-detected | It re-detects from live traffic when the TV broker panel changes. |
| Activation behavior | Copy profile → live keys; **auto-restart** engine if running | One click to switch; engine already reads the live keys, so no engine changes. |
| Profile storage | JSON blob in settings store (`profiles.list`) + per-profile secret password (`profiles.<id>.password`) + `profiles.active` | Reuses the existing store; keeps passwords in the secret mechanism, not plaintext JSON. |
| Detection | Multi-root filesystem scan (bounded depth) ∪ running-`terminal64.exe` paths (psutil); drop name filter; dedupe; return `{path,label}` | Catches Program Files installs and odd folder names; running-process union is the reliable backstop. |
| Browse dialog | `desktop.py` passes a `pick_file` callback into the API (mirrors `focus_callback`); endpoint opens pywebview `create_file_dialog` | The GUI thread/window owns native dialogs; this is the established seam. |

## Phase 7a — Detection + Picker + Browse

### Detection (`src/services/mt5_service.py::find_mt5_terminals`)

Rewrite to return a deduped list of `{"path": str, "label": str}`:
- **Roots scanned:** `%APPDATA%`, `%LOCALAPPDATA%`, `%ProgramFiles%`, `%ProgramFiles(x86)%`,
  `%ProgramW6432%` (skip any unset/missing). Search each for `terminal64.exe` with a
  **bounded depth (≤3)** to stay fast (avoid a full Program Files walk).
- **No name filter** — the old "MT5 in path" requirement is removed.
- **Running-process union:** add the executable path of every running `terminal64.exe`
  (via `psutil`, already a dependency). This is the reliable catch-all for unusual installs.
- **Label:** derived from the immediate parent folder (e.g.
  `…\Fusion Markets MT5 Terminal\terminal64.exe` → `Fusion Markets`); fall back to the
  parent folder name as-is.
- **Dedupe** by case-insensitive normalized absolute path.

A thin backward-compatible helper keeps any existing string-list callers working
(`find_mt5_terminal_paths()` returns just the paths), or update call sites — see plan.

### Detection API

- `GET /api/mt5/terminals` → `{"terminals": [{"path","label"}], "current": <stored path>}`.
  Used by **both** the wizard and Settings (the wizard's existing
  `/api/wizard/mt5/detect` is re-pointed at / wraps this).
- `POST /api/mt5/browse-terminal` → opens a native file dialog (filtered to
  `terminal64.exe`), returns `{"path": <selected>}` or `{"path": null}` if cancelled.

### Browse dialog wiring

- `app/desktop.py` defines a `pick_terminal_file()` that calls
  `_window.create_file_dialog(webview.OPEN_DIALOG, file_types=("MT5 terminal (terminal64.exe)",))`
  and returns the first selected path (or `None`). pywebview marshals the dialog to the GUI
  thread; the call may be made from the API worker thread.
- `app/api/server.py::create_app` gains a `pick_file` parameter (like `focus_callback`),
  passed through from `desktop.py`. When `pick_file` is `None` (e.g. headless tests), the
  browse endpoint returns `{"path": null}`.

### Picker UI (`app/ui/index.html` + `app/ui/app.js`)

Replace the bare terminal text input in **both** places (wizard MT5 step + Settings) with a
small reusable control:
- a `<select>` populated from `GET /api/mt5/terminals` (each option: `label — path`),
- a "Browse…" button → `POST /api/mt5/browse-terminal` → on success adds/selects the path,
- a manual-entry option (selecting "Other…" reveals a text input) as the ultimate fallback.

Selection rules: if exactly one terminal is detected, preselect it; if a value is already
stored, preselect it; otherwise leave unselected and (in the wizard) require a selection
before "Test connection". The wizard's existing **Test connection** and Settings' existing
save/restart flow are unchanged otherwise.

### 7a testing

- Unit: detection over a faked filesystem + faked psutil process list — asserts multi-root
  discovery, name-filter removal, running-process union, dedupe, and label derivation.
- Unit: `/api/mt5/terminals` shape; `/api/mt5/browse-terminal` returns the callback's path
  and degrades to `null` when `pick_file` is absent.
- Manual: wizard + Settings show the dropdown, Browse opens a real dialog, a picked path
  drives a successful Test connection.

## Phase 7b — Broker Profiles

### Data model (settings store)

- `profiles.list` → JSON array; each profile:
  `{"id": str, "name": str, "mt5": {"terminal_path","account","server"}, "symbols": {"default_suffix","map": {}}}`
  (no password here).
- `profiles.<id>.password` → stored via the store's **secret** API (`set_secret`/`get_secret`).
- `profiles.active` → active profile `id` (or empty).
- `id` is a short stable slug/uuid generated on create (no `Date.now`/random concerns —
  generated server-side with `uuid4`).

### Profile module (`app/storage/profiles.py`)

Pure, independently testable CRUD + activation over an injected `SettingsStore`:
- `list_profiles()` → profiles with passwords redacted + which is active.
- `create_profile(data)` / `update_profile(id, data)` / `delete_profile(id)`.
- `activate_profile(id)` → **copies** the profile's values into the live keys
  (`mt5.account`, `mt5.password` [secret], `mt5.server`, `mt5.terminal_path`,
  `symbols.default_suffix`, `symbols.map`) and sets `profiles.active`. Returns the applied
  config. Does **not** itself restart the engine (the API layer does, so the module stays
  pure/testable).

### Profiles API (`app/api`)

- `GET /api/profiles` → `{profiles: [...], active: <id>}` (passwords redacted).
- `POST /api/profiles` → create (validates via the existing settings validators); returns the new profile.
- `PUT /api/profiles/{id}` → update.
- `DELETE /api/profiles/{id}` → delete (cannot delete the active profile without confirmation; API returns 409 → UI confirms then re-calls with `?force=1`, or activates another first).
- `POST /api/profiles/{id}/activate` → `activate_profile(id)`, then if the engine is running call `controller.restart()`. Returns the new status.

### UI (`app/ui` Settings tab)

A "Broker profiles" section above/beside the existing MT5 fields:
- list of profiles with an **active** indicator and **Activate / Edit / Delete** buttons,
- an **Add / Save current as profile** form reusing 7a's terminal picker + the existing
  **Test connection** + symbol suffix/map inputs,
- Activate shows a progress state and the auto-restart result (reuses the existing
  restart banner pattern).

### Onboarding tie-in

On `POST /api/wizard/complete`, if no profiles exist, auto-create a **"Default"** profile
from the current live settings and mark it active — so profiles are never empty after
first-run.

### 7b testing

- Unit: `profiles.py` CRUD round-trips through a temp `SettingsStore`; password stored as a
  secret (not present in `profiles.list` JSON); `activate_profile` copies all live keys and
  sets `profiles.active`.
- Unit: profiles API routes (create/list/update/delete/activate); activate triggers
  `controller.restart()` only when running (fake controller).
- Manual: create two profiles (two brokers), activate each, confirm the engine restarts and
  copies trades on the right broker.

## Error Handling

- Detection never raises: unreadable roots / psutil errors are caught per-source; an empty
  list is valid (UI then relies on Browse + manual entry).
- Browse endpoint returns `{"path": null}` on cancel or when no GUI window is present.
- Activating a profile with an unreachable terminal/credentials surfaces via the normal
  engine-start banner (the restart will report the connection error); activation itself
  succeeds (it only writes config).
- Deleting the active profile is guarded (see API).

## Rollout / Compatibility

- Existing installs keep working unchanged: with no `profiles.list`, the app behaves exactly
  as today (live keys drive the engine). Profiles are additive.
- 7a ships first (high value, no data model). 7b builds on 7a's picker.

## Out of scope / future

- Tray quick-switch between profiles.
- Importing/exporting profiles between machines.
- Per-profile TV target.
