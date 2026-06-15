# Plan 4a — Onboarding Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-run, full-screen onboarding wizard (cert install → MT5 detect+test → TradingView detect → symbol suffix → done) inside the existing Plan 3 app shell, gated by an `onboarding.complete` flag.

**Architecture:** A small `app/wizard/` package holds the logic (cert trust, MT5 detection/test, suffix suggestion, onboarding state). A new `app/api/wizard.py` registers JSON endpoints onto the existing FastAPI app via `create_app()`. The frontend adds a `view-wizard` full-screen view (left step rail) to the existing single-page `app.js`/`index.html`, shown when onboarding is incomplete and re-runnable from Settings.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy (SQLite settings store), `MetaTrader5`, `certutil`/`ShellExecuteW` for cert trust, vanilla JS frontend, pytest + `fastapi.testclient`.

Spec: `docs/superpowers/specs/2026-06-15-tv2mt5-plan-04a-onboarding-wizard-design.md`
Branch: `plan-04-onboarding-wizard` (already created off `v2-desktop`).

---

## File Structure

**Create:**
- `app/wizard/__init__.py` — package marker.
- `app/wizard/state.py` — onboarding completion flag + resume-step helpers.
- `app/wizard/cert.py` — `is_cert_trusted()`, `install_cert_elevated()` (UAC launch).
- `app/wizard/_cert_admin.py` — elevated entry point that generates + installs the CA (reuses `MitmCertInstaller`).
- `app/wizard/detect.py` — `detect_mt5_terminals()`, `check_mt5_connection()`, `suggest_symbol_suffix()`.
- `app/api/wizard.py` — `add_wizard_routes(app)` registering the wizard endpoints.
- `tests/unit/test_wizard_state.py`
- `tests/unit/test_wizard_cert.py`
- `tests/unit/test_wizard_detect.py`
- `tests/unit/test_api_wizard.py`

**Modify:**
- `app/api/server.py` — import and call `add_wizard_routes(app)` inside `create_app()`.
- `app/ui/index.html` — add `view-wizard` section (left step rail + 6 panes) and a "Re-run setup" button in Settings.
- `app/ui/app.js` — wizard logic + first-run gating + re-run handler.
- `app/ui/styles.css` — append wizard styling.

**Conventions to follow (already in the codebase):**
- Routes are registered inline inside `create_app()` (see `app/api/server.py`).
- Tests use the `temp_db_path` fixture (`tests/conftest.py`) for an isolated SQLite DB and `TestClient(create_app(...))` with a `_FakeRunner` (see `tests/unit/test_api_server.py`).
- Settings persist via `SettingsStore` / `app/api/config_api.py` / `app/config_accessors.py`.

---

## Task 1: Onboarding state module

**Files:**
- Create: `app/wizard/__init__.py`
- Create: `app/wizard/state.py`
- Test: `tests/unit/test_wizard_state.py`

- [ ] **Step 1: Create the package marker**

Create `app/wizard/__init__.py`:

```python
"""First-run onboarding wizard logic (Plan 4a)."""
```

- [ ] **Step 2: Write the failing test**

Create `tests/unit/test_wizard_state.py`:

```python
from app.wizard import state


def test_onboarding_defaults_incomplete(temp_db_path):
    assert state.is_onboarding_complete() is False
    assert state.get_step() == 1


def test_set_complete_and_step(temp_db_path):
    state.set_step(3)
    assert state.get_step() == 3
    state.set_onboarding_complete(True)
    assert state.is_onboarding_complete() is True
```

- [ ] **Step 3: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/unit/test_wizard_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.wizard.state'`

- [ ] **Step 4: Write minimal implementation**

Create `app/wizard/state.py`:

```python
"""Onboarding wizard state: the first-run completion flag + resume step.

Stored in the SQLite settings store alongside the rest of the app config.
Step data itself (MT5 creds, symbols, TV target) is persisted through the
existing config accessors as each step completes; this module only tracks
*whether* onboarding is done and *where* the user left off.
"""
from typing import Optional

from app.storage.settings_store import SettingsStore

ONBOARDING_COMPLETE_KEY = "onboarding.complete"
ONBOARDING_STEP_KEY = "onboarding.step"


def is_onboarding_complete(store: Optional[SettingsStore] = None) -> bool:
    s = store or SettingsStore()
    return s.get_bool(ONBOARDING_COMPLETE_KEY, False)


def set_onboarding_complete(value: bool = True, store: Optional[SettingsStore] = None) -> None:
    s = store or SettingsStore()
    s.set(ONBOARDING_COMPLETE_KEY, "1" if value else "0")


def get_step(store: Optional[SettingsStore] = None) -> int:
    s = store or SettingsStore()
    return s.get_int(ONBOARDING_STEP_KEY, 1)


def set_step(step: int, store: Optional[SettingsStore] = None) -> None:
    s = store or SettingsStore()
    s.set(ONBOARDING_STEP_KEY, str(int(step)))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/unit/test_wizard_state.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add app/wizard/__init__.py app/wizard/state.py tests/unit/test_wizard_state.py
git commit -m "feat(wizard): onboarding completion flag + resume step"
```

---

## Task 2: Certificate trust module

**Files:**
- Create: `app/wizard/cert.py`
- Create: `app/wizard/_cert_admin.py`
- Test: `tests/unit/test_wizard_cert.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_wizard_cert.py`:

```python
import subprocess

from app.wizard import cert


class _R:
    def __init__(self, returncode, stdout):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = ""


def test_is_cert_trusted_true(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: _R(0, "== Certificate 0 ==\nIssuer: CN=mitmproxy\n"),
    )
    assert cert.is_cert_trusted() is True


def test_is_cert_trusted_false_when_absent(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _R(0, "no certificates"))
    assert cert.is_cert_trusted() is False


def test_is_cert_trusted_false_on_error(monkeypatch):
    def boom(*a, **k):
        raise OSError("certutil missing")
    monkeypatch.setattr(subprocess, "run", boom)
    assert cert.is_cert_trusted() is False


def test_install_returns_ok_when_already_trusted(monkeypatch):
    monkeypatch.setattr(cert, "is_cert_trusted", lambda: True)
    assert cert.install_cert_elevated() == {"ok": True, "pending": False}


def test_install_pending_when_launch_accepted(monkeypatch):
    monkeypatch.setattr(cert, "is_cert_trusted", lambda: False)
    monkeypatch.setattr(cert, "_launch_elevated_cert_install", lambda: 42)
    assert cert.install_cert_elevated() == {"ok": False, "pending": True}


def test_install_error_when_uac_declined(monkeypatch):
    monkeypatch.setattr(cert, "is_cert_trusted", lambda: False)
    monkeypatch.setattr(cert, "_launch_elevated_cert_install", lambda: 5)
    r = cert.install_cert_elevated()
    assert r["ok"] is False
    assert r["pending"] is False
    assert "administrator" in r["error"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/unit/test_wizard_cert.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.wizard.cert'`

- [ ] **Step 3: Write the cert module**

Create `app/wizard/cert.py`:

```python
"""Wizard step 2: mitmproxy CA certificate trust.

is_cert_trusted() is an idempotent check of the Windows Root store. Installing
the CA requires admin rights, so install_cert_elevated() launches a one-shot
elevated helper (app.wizard._cert_admin) via a UAC prompt; the app itself stays
unelevated. The frontend then polls is_cert_trusted() until it flips true.
"""
import subprocess
import sys

# mitmproxy's generated CA uses CN/issuer "mitmproxy".
_CERT_COMMON_NAME = "mitmproxy"


def is_cert_trusted() -> bool:
    """True if the mitmproxy CA is already in the Windows Root store."""
    try:
        result = subprocess.run(
            ["certutil", "-store", "root", _CERT_COMMON_NAME],
            capture_output=True, text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and _CERT_COMMON_NAME in (result.stdout or "")


def _launch_elevated_cert_install() -> int:
    """Trigger a UAC prompt to run the elevated cert-install helper.

    Returns the ShellExecuteW result code (>32 means the launch was accepted).
    """
    import ctypes
    return int(ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, "-m app.wizard._cert_admin", None, 1
    ))


def install_cert_elevated() -> dict:
    """Install the CA via an elevated helper. Idempotent.

    Returns one of:
      {"ok": True,  "pending": False}                already trusted
      {"ok": False, "pending": True}                 elevation launched; poll status
      {"ok": False, "pending": False, "error": ...}  UAC declined / launch failed
    """
    if is_cert_trusted():
        return {"ok": True, "pending": False}
    rc = _launch_elevated_cert_install()
    if rc <= 32:
        return {
            "ok": False, "pending": False,
            "error": "Could not get administrator access (was the UAC prompt declined?).",
        }
    return {"ok": False, "pending": True}
```

- [ ] **Step 4: Write the elevated helper entry point**

Create `app/wizard/_cert_admin.py`:

```python
"""Elevated entry point: generate + install the mitmproxy CA.

Run only via app.wizard.cert.install_cert_elevated() through a UAC prompt:
    python -m app.wizard._cert_admin
Reuses the existing MitmCertInstaller.
"""
from src.scripts.install_certificate import MitmCertInstaller


def main() -> int:
    installer = MitmCertInstaller()
    if not installer.generate_certificate():
        return 1
    return 0 if installer.install_certificate() else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/unit/test_wizard_cert.py -v`
Expected: PASS (6 passed)

- [ ] **Step 6: Commit**

```bash
git add app/wizard/cert.py app/wizard/_cert_admin.py tests/unit/test_wizard_cert.py
git commit -m "feat(wizard): idempotent CA trust check + elevated install"
```

---

## Task 3: Detection module (MT5 terminals, test connection, suffix)

**Files:**
- Create: `app/wizard/detect.py`
- Test: `tests/unit/test_wizard_detect.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_wizard_detect.py`:

```python
import MetaTrader5  # imported so monkeypatch targets resolve

from app.wizard import detect


def test_detect_mt5_terminals_reuses_finder(monkeypatch):
    monkeypatch.setattr(
        "src.services.mt5_service.find_mt5_terminals",
        lambda: ["C:/x/terminal64.exe"],
    )
    assert detect.detect_mt5_terminals() == ["C:/x/terminal64.exe"]


def test_suggest_suffix_default(temp_db_path):
    assert detect.suggest_symbol_suffix() == ".r"


def test_suggest_suffix_uses_stored(temp_db_path):
    from app.storage.settings_store import SettingsStore
    SettingsStore().set("symbols.default_suffix", ".pro")
    assert detect.suggest_symbol_suffix() == ".pro"


class _Acct:
    login = 12345
    balance = 1000.0
    server = "Demo"
    currency = "USD"


def test_check_mt5_connection_success(monkeypatch):
    monkeypatch.setattr(MetaTrader5, "initialize", lambda **k: True)
    monkeypatch.setattr(MetaTrader5, "login", lambda *a, **k: True)
    monkeypatch.setattr(MetaTrader5, "account_info", lambda: _Acct())
    monkeypatch.setattr(MetaTrader5, "shutdown", lambda: None)
    r = detect.check_mt5_connection("12345", "pw", "Demo")
    assert r == {
        "ok": True, "account": 12345, "balance": 1000.0,
        "server": "Demo", "currency": "USD",
    }


def test_check_mt5_connection_init_fails(monkeypatch):
    monkeypatch.setattr(MetaTrader5, "initialize", lambda **k: False)
    monkeypatch.setattr(MetaTrader5, "last_error", lambda: (1, "no terminal"))
    monkeypatch.setattr(MetaTrader5, "shutdown", lambda: None)
    r = detect.check_mt5_connection("12345", "pw", "Demo")
    assert r["ok"] is False
    assert "Could not connect" in r["error"]


def test_check_mt5_connection_bad_account():
    r = detect.check_mt5_connection("abc", "pw", "Demo")
    assert r["ok"] is False
    assert "number" in r["error"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/unit/test_wizard_detect.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.wizard.detect'`

- [ ] **Step 3: Write the detection module**

Create `app/wizard/detect.py`:

```python
"""Wizard detection helpers: MT5 terminals, MT5 test-connection, symbol suffix.

Heavy imports (the MetaTrader5 package, the engine's MT5 service) are done
lazily inside functions so importing this module — and therefore the API
server — stays cheap and these functions stay easy to mock in tests.
"""
import os
from typing import Optional


def detect_mt5_terminals() -> list:
    """Installed MT5 terminal paths (reuses the engine's discovery)."""
    from src.services.mt5_service import find_mt5_terminals
    return find_mt5_terminals()


def check_mt5_connection(account, password: str, server: str,
                         terminal_path: Optional[str] = None) -> dict:
    """Try to connect to MT5 with the given credentials.

    Returns {"ok": True, "account", "balance", "server", "currency"} or
    {"ok": False, "error": "..."}. Named check_* (not test_*) so pytest does
    not collect it when it is imported into a test module.
    """
    try:
        account = int(account)
    except (TypeError, ValueError):
        return {"ok": False, "error": "MT5 account must be a number."}

    import MetaTrader5 as mt5

    init_params = {"login": account, "password": password, "server": server}
    if terminal_path and os.path.exists(terminal_path):
        init_params["path"] = terminal_path
    try:
        if not mt5.initialize(**init_params):
            return {"ok": False, "error": f"Could not connect to MT5: {mt5.last_error()}"}
        if not mt5.login(account, password=password, server=server):
            return {"ok": False, "error": f"Login failed: {mt5.last_error()}"}
        info = mt5.account_info()
        if info is None:
            return {"ok": False, "error": "Connected, but could not read account info."}
        return {
            "ok": True, "account": info.login, "balance": info.balance,
            "server": info.server, "currency": info.currency,
        }
    except Exception as e:  # noqa: BLE001 - surfaced to the wizard banner
        return {"ok": False, "error": str(e)}
    finally:
        try:
            mt5.shutdown()
        except Exception:
            pass


def suggest_symbol_suffix() -> str:
    """Suggest a default broker symbol suffix.

    Prefers any suffix already stored; otherwise the common Fusion Markets ".r".
    """
    from app.storage.settings_store import SettingsStore
    existing = SettingsStore().get("symbols.default_suffix")
    return existing if existing else ".r"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/unit/test_wizard_detect.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add app/wizard/detect.py tests/unit/test_wizard_detect.py
git commit -m "feat(wizard): MT5 detect/test-connection + suffix suggestion"
```

---

## Task 4: Wizard API routes

**Files:**
- Create: `app/api/wizard.py`
- Modify: `app/api/server.py` (add import + `add_wizard_routes(app)` call)
- Test: `tests/unit/test_api_wizard.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_api_wizard.py`:

```python
from fastapi.testclient import TestClient

from app.engine_controller import EngineController


class _FakeRunner:
    def __init__(self, listen_host="127.0.0.1", listen_port=8080):
        pass
    async def serve(self):
        pass
    def shutdown(self):
        pass
    def mt5_connected(self):
        return False
    def tv_connected(self):
        return False


def _client():
    from app.api.server import create_app
    return TestClient(create_app(EngineController(runner_factory=_FakeRunner, listen_port=0)))


def test_wizard_state_default(temp_db_path):
    r = _client().get("/api/wizard/state")
    assert r.status_code == 200
    assert r.json() == {"onboarding_complete": False, "step": 1}


def test_wizard_complete_sets_flag(temp_db_path):
    c = _client()
    assert c.post("/api/wizard/complete").json() == {"ok": True}
    assert c.get("/api/wizard/state").json()["onboarding_complete"] is True


def test_wizard_set_step(temp_db_path):
    c = _client()
    assert c.post("/api/wizard/step", json={"step": 4}).json() == {"ok": True}
    assert c.get("/api/wizard/state").json()["step"] == 4


def test_wizard_cert_status(temp_db_path, monkeypatch):
    from app.wizard import cert
    monkeypatch.setattr(cert, "is_cert_trusted", lambda: True)
    assert _client().get("/api/wizard/cert/status").json() == {"trusted": True}


def test_wizard_cert_install_pending(temp_db_path, monkeypatch):
    from app.wizard import cert
    monkeypatch.setattr(cert, "is_cert_trusted", lambda: False)
    monkeypatch.setattr(cert, "_launch_elevated_cert_install", lambda: 42)
    assert _client().post("/api/wizard/cert/install").json() == {"ok": False, "pending": True}


def test_wizard_mt5_detect(temp_db_path, monkeypatch):
    from app.wizard import detect
    monkeypatch.setattr(detect, "detect_mt5_terminals", lambda: ["C:/a/terminal64.exe"])
    body = _client().get("/api/wizard/mt5/detect").json()
    assert body["terminals"] == ["C:/a/terminal64.exe"]
    assert body["current"] is None


def test_wizard_mt5_test_success_persists(temp_db_path, monkeypatch):
    from app.wizard import detect
    monkeypatch.setattr(
        detect, "check_mt5_connection",
        lambda account, password, server, terminal_path=None: {
            "ok": True, "account": 1, "balance": 0.0, "server": server, "currency": "USD"},
    )
    r = _client().post("/api/wizard/mt5/test",
                       json={"mt5": {"account": "777", "password": "pw", "server": "Live"}})
    assert r.json()["ok"] is True
    from app.storage.settings_store import SettingsStore
    assert SettingsStore().get_int("mt5.account") == 777
    assert SettingsStore().get_secret("mt5.password") == "pw"


def test_wizard_mt5_test_failure_does_not_persist(temp_db_path, monkeypatch):
    from app.wizard import detect
    monkeypatch.setattr(detect, "check_mt5_connection",
                        lambda *a, **k: {"ok": False, "error": "bad creds"})
    r = _client().post("/api/wizard/mt5/test",
                       json={"mt5": {"account": "777", "password": "pw", "server": "Live"}})
    assert r.json() == {"ok": False, "error": "bad creds"}
    from app.storage.settings_store import SettingsStore
    assert SettingsStore().get_int("mt5.account") is None


def test_wizard_tv_detection(temp_db_path):
    from app.storage.settings_store import SettingsStore
    s = SettingsStore()
    s.set("tv.broker_url", "broker.x")
    s.set("tv.account_id", "42")
    r = _client().get("/api/wizard/tv/detection").json()
    assert r == {"detected": True, "broker_url": "broker.x", "account_id": "42"}


def test_wizard_symbols_suggest(temp_db_path):
    assert _client().get("/api/wizard/symbols/suggest").json() == {"suffix": ".r"}


def test_index_contains_wizard_markup(temp_db_path):
    html = _client().get("/").text
    assert "view-wizard" in html
    assert "wiz-rail" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/unit/test_api_wizard.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.api.wizard'` (and the markup test fails because `view-wizard` is not in the HTML yet; that is fixed in Task 5).

- [ ] **Step 3: Write the wizard router module**

Create `app/api/wizard.py`:

```python
"""Wizard API routes (Plan 4a). Registered onto the app by create_app()."""
from fastapi import Body, FastAPI

from app.api.config_api import SettingsValidationError, update_settings
from app.config_accessors import get_tv_target
from app.storage.settings_store import SettingsStore
from app.wizard import cert, detect, state


def add_wizard_routes(app: FastAPI) -> None:
    @app.get("/api/wizard/state")
    def wizard_state():
        return {
            "onboarding_complete": state.is_onboarding_complete(),
            "step": state.get_step(),
        }

    @app.post("/api/wizard/step")
    def wizard_set_step(payload: dict = Body(...)):
        state.set_step(int(payload.get("step", 1)))
        return {"ok": True}

    @app.post("/api/wizard/complete")
    def wizard_complete():
        state.set_onboarding_complete(True)
        return {"ok": True}

    @app.get("/api/wizard/cert/status")
    def wizard_cert_status():
        return {"trusted": cert.is_cert_trusted()}

    @app.post("/api/wizard/cert/install")
    def wizard_cert_install():
        return cert.install_cert_elevated()

    @app.get("/api/wizard/mt5/detect")
    def wizard_mt5_detect():
        return {
            "terminals": detect.detect_mt5_terminals(),
            "current": SettingsStore().get("mt5.terminal_path"),
        }

    @app.post("/api/wizard/mt5/test")
    def wizard_mt5_test(payload: dict = Body(...)):
        mt5 = payload.get("mt5", {}) or {}
        result = detect.check_mt5_connection(
            mt5.get("account"), mt5.get("password", ""),
            mt5.get("server", ""), mt5.get("terminal_path"),
        )
        if result.get("ok"):
            try:
                update_settings({"mt5": mt5})
            except SettingsValidationError as e:
                return {"ok": False, "error": str(e)}
        return result

    @app.get("/api/wizard/tv/detection")
    def wizard_tv_detection():
        broker_url, account_id = get_tv_target()
        return {
            "detected": bool(broker_url and account_id),
            "broker_url": broker_url,
            "account_id": account_id,
        }

    @app.get("/api/wizard/symbols/suggest")
    def wizard_symbols_suggest():
        return {"suffix": detect.suggest_symbol_suffix()}
```

- [ ] **Step 4: Wire the routes into create_app**

In `app/api/server.py`, add the import alongside the other `app.api` imports (after line 14, the `from app.api.trades import query_trades` line):

```python
from app.api.wizard import add_wizard_routes
```

Then, inside `create_app()`, register the routes just before the `@app.get("/")` index route (currently around line 94). Add:

```python
    add_wizard_routes(app)

```

- [ ] **Step 5: Run tests — API passes, markup test still fails**

Run: `venv\Scripts\python.exe -m pytest tests/unit/test_api_wizard.py -v`
Expected: All pass EXCEPT `test_index_contains_wizard_markup` (still failing — fixed in Task 5).

- [ ] **Step 6: Commit**

```bash
git add app/api/wizard.py app/api/server.py tests/unit/test_api_wizard.py
git commit -m "feat(wizard): JSON API endpoints + wiring into create_app"
```

---

## Task 5: Frontend — wizard view, gating, and re-run

**Files:**
- Modify: `app/ui/index.html`
- Modify: `app/ui/app.js`
- Modify: `app/ui/styles.css`
- Test: reuses `tests/unit/test_api_wizard.py::test_index_contains_wizard_markup`

- [ ] **Step 1: Add the wizard section to index.html**

In `app/ui/index.html`, insert the following as the FIRST child of `<main class="content">` (immediately after the `<main class="content">` line, before `<section id="view-dashboard" ...>`):

```html
      <section id="view-wizard" class="view hidden wizard">
        <div class="wiz-rail">
          <div class="brand">TV2MT5 Setup</div>
          <ol>
            <li data-step="1" class="wiz-step active">Welcome</li>
            <li data-step="2" class="wiz-step">Certificate</li>
            <li data-step="3" class="wiz-step">MT5 Account</li>
            <li data-step="4" class="wiz-step">TradingView</li>
            <li data-step="5" class="wiz-step">Symbols</li>
            <li data-step="6" class="wiz-step">Done</li>
          </ol>
        </div>
        <div class="wiz-panel">
          <div id="wiz-banner" class="banner hidden"></div>

          <div class="wiz-pane" data-pane="1">
            <h2>Welcome to TV2MT5</h2>
            <p>This copies your TradingView broker-panel trades into MetaTrader 5.
               Your credentials stay on this PC.</p>
          </div>

          <div class="wiz-pane hidden" data-pane="2">
            <h2>Security certificate</h2>
            <p>We need to trust the local proxy certificate so TradingView traffic can be read.</p>
            <div id="wiz-cert-status" class="lab">Checking…</div>
            <button id="wiz-cert-install" class="btn start">Install certificate</button>
          </div>

          <div class="wiz-pane hidden" data-pane="3">
            <h2>MT5 account</h2>
            <label class="field">Terminal path
              <input id="wiz-mt5-terminal" type="text" placeholder="auto-detected" />
            </label>
            <label class="field">Account <input id="wiz-mt5-account" type="number" /></label>
            <label class="field">Password <input id="wiz-mt5-password" type="password" /></label>
            <label class="field">Server <input id="wiz-mt5-server" type="text" /></label>
            <button id="wiz-mt5-test" class="btn">Test connection</button>
            <div id="wiz-mt5-result" class="lab"></div>
          </div>

          <div class="wiz-pane hidden" data-pane="4">
            <h2>Connect TradingView</h2>
            <p>In the TradingView desktop app, set its proxy to:</p>
            <pre class="logbox">Type: HTTP
Host: 127.0.0.1
Port: 8080
No username / password</pre>
            <p>Then open your broker panel. We'll detect it automatically.</p>
            <div id="wiz-tv-status" class="lab">Waiting for TradingView traffic…</div>
          </div>

          <div class="wiz-pane hidden" data-pane="5">
            <h2>Symbols</h2>
            <label class="field">Default suffix
              <input id="wiz-suffix" type="text" placeholder=".r" />
            </label>
            <p class="lab">Most accounts need a suffix like <code>.r</code>. You can change this later.</p>
          </div>

          <div class="wiz-pane hidden" data-pane="6">
            <h2>All set</h2>
            <p>Setup complete. Click Start Copying to begin.</p>
          </div>

          <div class="wiz-nav">
            <button id="wiz-back" class="btn ghost">Back</button>
            <button id="wiz-next" class="btn start">Next</button>
          </div>
        </div>
      </section>
```

- [ ] **Step 2: Add the "Re-run setup" button to the Settings section**

In `app/ui/index.html`, inside `<section id="view-settings" ...>`, replace the final save-button line:

```html
        <div><button id="set-save" class="btn start">Save</button></div>
```

with:

```html
        <div>
          <button id="set-save" class="btn start">Save</button>
          <button id="set-rerun" class="btn ghost">Re-run setup wizard</button>
        </div>
```

- [ ] **Step 3: Run the markup test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/unit/test_api_wizard.py::test_index_contains_wizard_markup -v`
Expected: PASS

- [ ] **Step 4: Append wizard styling to styles.css**

Append to the end of `app/ui/styles.css`:

```css
/* --- Onboarding wizard (Plan 4a) --- */
.onboarding .sidebar { display: none; }
.view.wizard { display: flex; gap: 0; height: 100vh; }
.view.wizard.hidden { display: none; }
.wiz-rail {
  width: 220px; background: #17181c; border-right: 1px solid #2c2e36; padding: 18px;
}
.wiz-rail .brand { font-weight: 700; margin-bottom: 16px; }
.wiz-rail ol { list-style: none; padding: 0; margin: 0; }
.wiz-step { padding: 8px 6px; opacity: .5; font-size: 14px; }
.wiz-step.active { opacity: 1; color: #4ea1ff; font-weight: 600; }
.wiz-panel { flex: 1; padding: 28px 32px; overflow: auto; display: flex; flex-direction: column; }
.wiz-pane { flex: 1; }
.wiz-pane.hidden { display: none; }
.wiz-nav { display: flex; justify-content: space-between; margin-top: 24px; }
```

- [ ] **Step 5: Add the wizard logic to app.js**

Append to the end of `app/ui/app.js`:

```javascript
// --- Onboarding wizard (Plan 4a) ---
let wizStep = 1;
const WIZ_LAST = 6;
let certPoll = null;
let tvPoll = null;

function wizBanner(msg, ok) {
  const b = $('wiz-banner');
  b.textContent = msg;
  b.className = 'banner' + (ok ? ' ok' : '');
}

function enterWizard() {
  document.body.classList.add('onboarding');
  VIEWS.forEach(v => $('view-' + v).classList.add('hidden'));
  $('view-wizard').classList.remove('hidden');
  gotoStep(wizStep);
}

function exitWizard() {
  document.body.classList.remove('onboarding');
  clearInterval(certPoll); clearInterval(tvPoll);
  $('view-wizard').classList.add('hidden');
  showView('dashboard');
}

function gotoStep(step) {
  wizStep = Math.max(1, Math.min(WIZ_LAST, step));
  document.querySelectorAll('.wiz-step').forEach(li =>
    li.classList.toggle('active', Number(li.getAttribute('data-step')) === wizStep));
  document.querySelectorAll('.wiz-pane').forEach(p =>
    p.classList.toggle('hidden', Number(p.getAttribute('data-pane')) !== wizStep));
  $('wiz-back').disabled = wizStep === 1;
  $('wiz-next').textContent = wizStep === WIZ_LAST ? 'Start Copying' : 'Next';
  $('wiz-banner').classList.add('hidden');
  $('wiz-next').disabled = false;
  fetch('/api/wizard/step', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ step: wizStep }),
  }).catch(() => {});
  if (wizStep !== 4) wizStopTvDetection();
  if (wizStep === 2) wizLoadCert();
  if (wizStep === 3) wizLoadMt5();
  if (wizStep === 4) wizStartTvDetection();
  if (wizStep === 5) wizLoadSuffix();
}

async function wizLoadCert() {
  try {
    const d = await (await fetch('/api/wizard/cert/status')).json();
    setCertUi(d.trusted);
  } catch (e) {}
}

function setCertUi(trusted) {
  $('wiz-cert-status').textContent = trusted ? '✓ Certificate installed' : 'Not installed yet';
  $('wiz-cert-install').classList.toggle('hidden', trusted);
  if (wizStep === 2) $('wiz-next').disabled = !trusted;
}

$('wiz-cert-install').addEventListener('click', async () => {
  $('wiz-cert-status').textContent = 'Requesting administrator access…';
  let r;
  try { r = await (await fetch('/api/wizard/cert/install', { method: 'POST' })).json(); }
  catch (e) { wizBanner('Install failed', false); return; }
  if (r.ok) { setCertUi(true); return; }
  if (r.error) { wizBanner(r.error, false); $('wiz-cert-status').textContent = 'Not installed yet'; return; }
  $('wiz-cert-status').textContent = 'Installing… approve the Windows prompt.';
  clearInterval(certPoll);
  certPoll = setInterval(async () => {
    try {
      const d = await (await fetch('/api/wizard/cert/status')).json();
      if (d.trusted) { clearInterval(certPoll); setCertUi(true); }
    } catch (e) {}
  }, 1500);
});

async function wizLoadMt5() {
  $('wiz-next').disabled = true; // require a successful test first
  try {
    const d = await (await fetch('/api/wizard/mt5/detect')).json();
    const t = $('wiz-mt5-terminal');
    if (!t.value) t.value = d.current || (d.terminals && d.terminals[0]) || '';
  } catch (e) {}
}

$('wiz-mt5-test').addEventListener('click', async () => {
  $('wiz-mt5-result').textContent = 'Testing…';
  const mt5 = {
    account: $('wiz-mt5-account').value.trim(),
    password: $('wiz-mt5-password').value,
    server: $('wiz-mt5-server').value.trim(),
    terminal_path: $('wiz-mt5-terminal').value.trim(),
  };
  let r;
  try {
    r = await (await fetch('/api/wizard/mt5/test', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mt5 }),
    })).json();
  } catch (e) { wizBanner('Test failed', false); return; }
  if (r.ok) {
    $('wiz-mt5-result').textContent = `✓ ${r.account} — ${r.balance} ${r.currency} (${r.server})`;
    $('wiz-next').disabled = false;
  } else {
    $('wiz-mt5-result').textContent = '';
    wizBanner(r.error || 'Connection failed', false);
  }
});

async function wizStartTvDetection() {
  $('wiz-next').disabled = true;
  await fetch('/api/engine/start', { method: 'POST' }).catch(() => {});
  clearInterval(tvPoll);
  tvPoll = setInterval(async () => {
    try {
      const d = await (await fetch('/api/wizard/tv/detection')).json();
      if (d.detected) {
        $('wiz-tv-status').textContent = `✓ Detected account ${d.account_id}`;
        $('wiz-next').disabled = false;
      }
    } catch (e) {}
  }, 2000);
}

function wizStopTvDetection() { clearInterval(tvPoll); tvPoll = null; }

async function wizLoadSuffix() {
  try {
    const d = await (await fetch('/api/wizard/symbols/suggest')).json();
    if (!$('wiz-suffix').value) $('wiz-suffix').value = d.suffix || '.r';
  } catch (e) {}
}

$('wiz-back').addEventListener('click', () => gotoStep(wizStep - 1));

$('wiz-next').addEventListener('click', async () => {
  if (wizStep === 5) {
    let cur = { map: {} };
    try { cur = await (await fetch('/api/symbols')).json(); } catch (e) {}
    await fetch('/api/symbols', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ default_suffix: $('wiz-suffix').value.trim(), map: cur.map || {} }),
    }).catch(() => {});
  }
  if (wizStep === WIZ_LAST) {
    await fetch('/api/wizard/complete', { method: 'POST' }).catch(() => {});
    exitWizard();
    await fetch('/api/engine/start', { method: 'POST' }).catch(() => {});
    refreshStatus();
    return;
  }
  gotoStep(wizStep + 1);
});

$('set-rerun').addEventListener('click', () => { wizStep = 1; enterWizard(); });

async function initOnboarding() {
  try {
    const d = await (await fetch('/api/wizard/state')).json();
    if (!d.onboarding_complete) { wizStep = d.step || 1; enterWizard(); }
  } catch (e) {}
}
initOnboarding();
```

- [ ] **Step 6: Run the full unit suite**

Run: `venv\Scripts\python.exe -m pytest tests/unit -q`
Expected: PASS (all previous tests + the new wizard tests).

- [ ] **Step 7: Commit**

```bash
git add app/ui/index.html app/ui/app.js app/ui/styles.css
git commit -m "feat(wizard): full-screen wizard view, first-run gating, re-run from Settings"
```

---

## Task 6: Manual verification + final suite

**Files:** none (verification only).

- [ ] **Step 1: Run the entire unit suite**

Run: `venv\Scripts\python.exe -m pytest tests/unit -q`
Expected: all tests pass, no errors.

- [ ] **Step 2: Launch the desktop app on a clean DB and walk the wizard**

Run (PowerShell), pointing at a throwaway DB so onboarding is incomplete:

```powershell
$env:TV2MT5_DB_PATH = "$env:TEMP\tv2mt5-wizard-check.db"
venv\Scripts\python.exe run.py desktop
```

Verify:
- The window opens directly into the wizard (sidebar hidden), step 1 Welcome.
- Step 2: cert status shows; if already trusted, Next enables; otherwise "Install certificate" triggers a UAC prompt and, after approval, status flips to "✓ Certificate installed".
- Step 3: terminal path auto-fills; "Test connection" with valid creds shows account/balance/server and enables Next; bad creds show a banner and keep Next disabled.
- Step 4: shows the HTTP/127.0.0.1/8080 proxy values; after routing TradingView and opening the broker panel, "✓ Detected account …" appears and Next enables.
- Step 5: suffix pre-fills `.r` (or stored value).
- Step 6: "Start Copying" closes the wizard, reveals the normal shell, and the engine starts.
- Relaunch with the same DB → wizard does NOT reappear (onboarding complete).
- In Settings, "Re-run setup wizard" reopens the wizard.

Clean up: `Remove-Item $env:TEMP\tv2mt5-wizard-check.db`

- [ ] **Step 3: Final commit (if any verification fixes were needed)**

```bash
git add -A
git commit -m "test(wizard): verification fixes from manual end-to-end walkthrough"
```

(If no fixes were needed, skip this commit.)

---

## Self-Review Notes

- **Spec coverage:** Welcome (Task 5 pane 1) · Certificate one-click + idempotent + UAC (Tasks 2, 4, 5) · MT5 auto-detect + Test (Tasks 3, 4, 5) · TradingView detect via live engine + optional manual proxy values, test-trade optional/skippable since Next enables on detection (Tasks 4, 5) · Symbols suffix suggest (Tasks 3, 4, 5) · Done sets `onboarding.complete` + Start (Tasks 1, 4, 5) · full-screen left-rail hosting + gating + re-run (Task 5) · error banners (Tasks 4, 5) · tests with mocked externals (every task).
- **Deferred to Plan 4b (out of scope, per spec):** automated app-level/system proxy set + revert-on-Stop/crash. Step 4 shows the manual proxy values only.
- **Naming note:** the MT5 connection helper is `check_mt5_connection` (not `test_*`) so pytest does not collect it when imported into a test module.
- **Reuse:** `MitmCertInstaller` (cert), `find_mt5_terminals` (detect), `update_settings`/`SettingsStore`/`get_tv_target` (persistence + detection), `EngineController` start/stop via existing `/api/engine/*` endpoints (step 4).
