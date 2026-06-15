# TV2MT5 Desktop — Plan 4a: Onboarding Wizard (Design)

Source spec: `docs/superpowers/specs/2026-06-13-tv2mt5-desktop-design.md`
Roadmap: `docs/superpowers/plans/2026-06-13-tv2mt5-desktop-plan-roadmap.md`
Branch: `plan-04-onboarding-wizard` (off `v2-desktop`)

## Scope decision

The roadmap's Plan 4 bundled two independent subsystems: the first-run **wizard**
and the **proxy manager** (which modifies the Windows system proxy and must revert
safely on Stop/crash). Mirroring the 3a/3b split, Plan 4 is divided:

- **Plan 4a (this spec): Onboarding Wizard** — the 6-step first-run flow.
- **Plan 4b (deferred, own spec): Proxy Manager** — automated app-level/system
  proxy routing with revert-on-Stop/crash.

This split is clean because the wizard's *preferred* TradingView routing path is
already manual (the wizard shows the values to type into the TradingView desktop
app's own proxy setting). Plan 4b later adds the automated system-proxy fallback.

## Goal

A first-run, full-screen onboarding wizard inside the existing Plan 3 app shell
that takes a new user from a fresh install to copying trades, with no terminal,
no manual cert steps, and no hand-edited config.

## Hosting & triggering

- The wizard is a **full-screen takeover view** inside the existing SPA
  (`app/ui/app.js` + `index.html`), not a separate page or modal.
- Gated by a new settings flag `onboarding_complete` (bool). When false, the
  wizard takes over the whole window (sidebar hidden) until finished. When true,
  the normal shell loads.
- Re-runnable later via a "Re-run setup" entry in the Settings tab.
- **Layout: left step rail** — vertical 1–6 step list on the left (echoes the
  app's existing sidebar), content panel on the right, Back/Next at the bottom.

## Components

### Backend

- `app/wizard/__init__.py` — onboarding logic package.
- `app/wizard/cert.py` — wraps the existing `MitmCertInstaller`
  (`src/scripts/install_certificate.py`):
  - `is_cert_trusted()` — idempotent check of whether the mitmproxy CA is already
    in the Windows Root store.
  - `install_cert_elevated()` — spawns a UAC-elevated `runas` helper
    (`ShellExecute` "runas") that runs **only** the cert install; the app itself
    stays unelevated. Returns a structured status.
- `app/wizard/detect.py`:
  - `detect_mt5_terminals()` — reuses `MT5Service.find_mt5_terminals()`.
  - `test_mt5_connection(creds)` — reuses `MT5Service` connect; returns
    account/balance/server on success or a clear error string on failure.
  - `suggest_symbol_suffix()` — suggests a default suffix (e.g. `.r`).
- `app/api/wizard.py` — new FastAPI router mounted by `create_app()`:
  - `GET  /api/wizard/state` — current step data + `onboarding_complete`.
  - `GET  /api/wizard/cert/status` — `is_cert_trusted()`.
  - `POST /api/wizard/cert/install` — triggers elevated install; returns status.
  - `GET  /api/wizard/mt5/detect` — auto-detected terminal path(s).
  - `POST /api/wizard/mt5/test` — test connection with entered credentials.
  - `GET  /api/wizard/tv/detection` — polls the live engine for captured
    `broker_url`/`account_id`.
  - `POST /api/wizard/symbols/suffix` — suggest/persist suffix.
  - `POST /api/wizard/complete` — sets `onboarding_complete=true`.
  - All endpoints return structured `{ok, error}` JSON.

### Frontend

- New full-screen `wizard` view in `app/ui/app.js` + `index.html`, left-step-rail
  layout, reusing the existing dark app-shell styling. Sidebar hidden while the
  wizard is active.
- A "Re-run setup" control in the Settings tab.

### Settings store

- New key `onboarding_complete` (bool).
- Per-step data persisted via the existing `SettingsStore` + config accessors as
  the user advances (MT5 creds via the existing secret box; symbol suffix via the
  existing symbol config; `broker_url`/`account_id` via the existing accessors
  from Plan 2/3b).

## Per-step flow

Each step persists to the `SettingsStore` as completed (resumable if the user
closes mid-wizard). `onboarding_complete=true` is written only at step 6.

1. **Welcome** — what it does + safety note (credentials stay local). No
   persistence. → Next.
2. **Certificate** — on load, `GET /cert/status` runs `is_cert_trusted()`.
   - Already trusted → green "✓ installed", Next enabled.
   - Otherwise → "Install" button → `POST /cert/install` triggers the UAC prompt;
     UI shows pending → success/failure banner. Idempotent and re-runnable.
3. **MT5 account** — on load, `GET /mt5/detect` auto-fills the detected terminal
   path. User enters account / password / server → "Test connection"
   (`POST /mt5/test`). Success shows account #, balance, server name and persists
   config (password via the secret box); failure shows a clear reason. Next gated
   on a successful test.
4. **Connect TradingView** — wizard calls `EngineController.start()` to run the
   engine in detection mode and shows the manual app-level proxy values to enter
   in the TradingView desktop app (**HTTP**, host `127.0.0.1`, port `8080`, no
   username/password). Frontend polls `GET /tv/detection`; when broker-panel
   traffic is seen, `broker_url`/`account_id` are captured + persisted and the
   step can complete. Then an **optional** "place a small test trade to verify
   copy end-to-end" with a clear **Skip**. (Automated system-proxy fallback is
   Plan 4b.)
5. **Symbols** — `POST /symbols/suffix` suggests a default suffix (e.g. `.r`);
   advanced/optional overrides. Persisted via existing symbol config.
6. **Done** — summary; `POST /complete` sets `onboarding_complete=true`. "Start
   Copying" exits the wizard, reveals the normal shell, and starts the engine via
   the existing Start control.

### Engine lifecycle nuance

The engine started for step-4 detection is the **same** `EngineController` the
main shell uses, so the Plan 3 singleton / port-in-use guard applies — no second
instance is created. If the user backs out of step 4, the engine is stopped.

## Error handling

Matches the parent spec's "clear UI banner states, never raw stack traces":

- **Cert install** — UAC declined / certutil failure → actionable banner
  ("Certificate not installed — click to retry"); Next stays disabled.
- **MT5 test** — terminal not found, bad credentials, terminal down → specific
  reason from `MT5Service`, never a stack trace.
- **TV detection** — no traffic after a timeout → hint banner ("No TradingView
  traffic seen yet — check the proxy values above") with a recheck. Engine errors
  (e.g. port `8080` busy) surface the existing Plan 3 `ProxyPortInUseError`
  message.
- All wizard endpoints return structured `{ok, error}` JSON; the frontend renders
  banners and everything is also written to the rotating log (Logs tab).

## Testing

Pytest, mirroring the existing `tests/unit` style. No live MT5/TV required — all
external surfaces mocked.

- `cert.py`: `is_cert_trusted()` true/false branches; elevated-install command
  construction (mock the elevation call — no real UAC in tests).
- `detect.py`: `detect_mt5_terminals()`; `test_mt5_connection()` success + each
  failure mode (mock `MT5Service`); `suggest_symbol_suffix()`.
- `app/api/wizard.py`: each endpoint via FastAPI `TestClient` — state, cert
  status/install, mt5 detect/test, tv detection (mock captured IDs), symbols,
  complete (asserts `onboarding_complete` flips true).
- Wizard gating: shell serves the wizard when `onboarding_complete` is false and
  the normal shell when true.

## Out of scope (Plan 4a)

- Automated proxy routing (app-level set + Windows system-proxy fallback with
  revert-on-Stop/crash) — **Plan 4b**.
- PyInstaller/Inno Setup packaging and installer-time cert trust — **Plan 6**.
- Monetization seams — **Plan 5**.
