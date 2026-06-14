# TV2MT5 Desktop — Plan Roadmap

Source spec: `docs/superpowers/specs/2026-06-13-tv2mt5-desktop-design.md`

The spec spans several independent subsystems. Rather than one giant plan, it is
split into a sequence of plans. **Each plan produces working, testable software
on its own** and is built in order (later plans depend on earlier ones).

| # | Plan | Outcome (working software at the end) | Status |
|---|------|----------------------------------------|--------|
| 1 | **Foundation: Infra Collapse** | Headless copier runs as **one process, no Docker/Postgres/Redis** — SQLite + in-process queue. Trades still copy TV→MT5. | **Written** (`2026-06-13-tv2mt5-desktop-plan-01-foundation.md`) |
| 2 | **Broker Adapter + Settings Store** | `BrokerAdapter` interface with `FusionMarketsAdapter`; config moves from `.env` to a SQLite `settings` table; auto-detect of `broker_url`/`account_id` from live traffic. | **Written** (`2026-06-14-tv2mt5-desktop-plan-02-broker-adapter-settings.md`) |
| 3 | **App Shell (UI + tray)** | FastAPI local API + `pywebview`/WebView2 window + `pystray` tray with sidebar nav (Dashboard/Trades/Symbols/Settings/Logs); Start/Stop controls the engine from Plan 1. | Pending |
| 4 | **Onboarding Wizard** | 6-step first-run wizard: auto cert install, MT5 terminal auto-detect + Test, TradingView auto-detect, symbol suffix, done. Auto-set/revert Windows system proxy on Start/Stop. | Pending |
| 5 | **Monetization Seams** | `LicenseService`, `Updater`, `Telemetry`, `ErrorReporter` interfaces with local stubs, wired into the app behind feature checks. | Pending |
| 6 | **Packaging** | PyInstaller one-folder build + Inno Setup `.exe` installer; app data in `%APPDATA%\TV2MT5`. | Pending |

## Build order rationale

- **Plan 1 first** because removing Docker/Postgres/Redis is the single biggest
  ease-of-use win and the highest technical risk (embedding mitmproxy + worker
  in one event loop). Everything else wraps this core, so de-risk it first.
- **Plan 2** before the UI because the UI and wizard read/write settings and rely
  on the adapter boundary.
- **Plans 3–4** build the user-facing shell on the now-stable core.
- **Plans 5–6** are additive and ship last.

After Plan 2 is executed and verified, return to writing-plans to author Plan 3.
