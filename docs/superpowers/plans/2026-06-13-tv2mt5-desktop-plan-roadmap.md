# TV2MT5 Desktop — Plan Roadmap

Source spec: `docs/superpowers/specs/2026-06-13-tv2mt5-desktop-design.md`

The spec spans several independent subsystems. Rather than one giant plan, it is
split into a sequence of plans. **Each plan produces working, testable software
on its own** and is built in order (later plans depend on earlier ones).

| #   | Plan                                | Outcome (working software at the end)                                                                                                                                          | Status                                                                                                                                        |
| --- | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Foundation: Infra Collapse**      | Headless copier runs as **one process, no Docker/Postgres/Redis** — SQLite + in-process queue. Trades still copy TV→MT5.                                                       | **Written** (`2026-06-13-tv2mt5-desktop-plan-01-foundation.md`)                                                                               |
| 2   | **Broker Adapter + Settings Store** | `BrokerAdapter` interface with `FusionMarketsAdapter`; config moves from `.env` to a SQLite `settings` table; auto-detect of `broker_url`/`account_id` from live traffic.      | **Executed + verified** end-to-end (open/close/TP-SL modify) on `v2-desktop` (`2026-06-14-tv2mt5-desktop-plan-02-broker-adapter-settings.md`) |
| 3   | **App Shell (UI + tray)**           | FastAPI local API + `pywebview`/WebView2 window + `pystray` tray with sidebar nav (Dashboard/Trades/Symbols/Settings/Logs); Start/Stop controls the engine from Plan 1.        | **Done** — 3a app shell (#51), venv launcher fix (#52), 3b content tabs (#53), display polish (#54); singleton guard landed; merged on `v2-desktop` |
| 4a  | **Onboarding Wizard**               | 6-step first-run wizard: auto cert install (per-click UAC), MT5 terminal auto-detect + Test, TradingView auto-detect (test trade optional), symbol suffix, done. Full-screen takeover in the SPA, left step rail. | **Written** (`2026-06-15-tv2mt5-plan-04a-onboarding-wizard-design.md`) |
| 4b  | **Proxy Manager**                   | Automated app-level proxy guidance + Windows system-proxy fallback with revert on Stop/crash. Split out of Plan 4.                                                             | Pending                                                                                                                                       |
| 5   | **Monetization Seams**              | `LicenseService`, `Updater`, `Telemetry`, `ErrorReporter` interfaces with local stubs, wired into the app behind feature checks.                                               | Pending                                                                                                                                       |
| 6   | **Packaging**                       | PyInstaller one-folder build + Inno Setup `.exe` installer; app data in `%APPDATA%\TV2MT5`.                                                                                    | Pending                                                                                                                                       |

## Build order rationale

- **Plan 1 first** because removing Docker/Postgres/Redis is the single biggest
  ease-of-use win and the highest technical risk (embedding mitmproxy + worker
  in one event loop). Everything else wraps this core, so de-risk it first.
- **Plan 2** before the UI because the UI and wizard read/write settings and rely
  on the adapter boundary.
- **Plans 3–4** build the user-facing shell on the now-stable core.
- **Plans 5–6** are additive and ship last.

After Plan 2 is executed and verified, return to writing-plans to author Plan 3.

## Carry-forward note for Plan 3/4

During Plan 2 verification a "trades not copying" episode traced to **multiple engine
instances running at once**, contending for MetaTrader5's single-terminal IPC
(`-10005 IPC timeout` → `order_send` "Request timeout"; only the `:8080` bind fails
loudly). The engine has **no singleton guard**. Fold a single-instance lock /
port-in-use check (abort with a clear message) into the Plan 3/4 tray Start/Stop work.

## Development workflow (from Plan 3 onward)

Each plan is built on its own branch off `v2-desktop` (e.g. `plan-03-app-shell`),
verified end-to-end, then merged back via a PR with **base = `v2-desktop`** using a
**merge commit** (preserves the task-by-task TDD history). `main` stays v1 until all
of v2 is ready. Plan 2 was committed directly on `v2-desktop` before this convention
was adopted.
