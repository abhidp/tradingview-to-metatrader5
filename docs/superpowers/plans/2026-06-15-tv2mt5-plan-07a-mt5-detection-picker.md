# TV2MT5 Plan 7a — MT5 Detection + Picker + Browse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make MT5 terminal selection work for any broker/install location — robust multi-location detection (incl. running processes), a dropdown picker, and a native "Browse…" file dialog, in both the onboarding wizard and the Settings tab.

**Architecture:** Rewrite terminal discovery in `mt5_service` to scan multiple install roots plus running `terminal64.exe` processes (psutil) and return `{path,label}` records. Add a shared `GET /api/mt5/terminals` endpoint and a `POST /api/mt5/browse-terminal` endpoint backed by a `pick_file` callback that `desktop.py` wires to the pywebview window's native file dialog. The UI gains a select + Browse control above the existing terminal text input (which stays the value source, so existing test/save logic is untouched).

**Tech Stack:** Python 3.11, FastAPI, pywebview (WebView2), psutil, MetaTrader5; vanilla JS frontend.

**Spec:** `docs/superpowers/specs/2026-06-15-tv2mt5-mt5-agnostic-onboarding-design.md` (Phase 7a)

> Test commands assume the repo venv: `venv\Scripts\python -m pytest ...` (PowerShell) or `./venv/Scripts/python.exe -m pytest ...` (Git Bash). Do NOT run git checkout/switch/branch/reset during tasks; commit on the current branch `plan-07-mt5-agnostic`.

---

## File Structure

- Modify `src/services/mt5_service.py` — add `discover_mt5_terminals()` (rich, multi-root + psutil); make `find_mt5_terminals()` a thin path-list wrapper (keeps existing callers working).
- Create `app/api/mt5_api.py` — `add_mt5_routes(app, pick_file)`: `GET /api/mt5/terminals`, `POST /api/mt5/browse-terminal`.
- Modify `app/api/server.py` — `create_app(controller, focus_callback=None, pick_file=None)`; call `add_mt5_routes`.
- Modify `app/desktop.py` — define `pick_terminal_file()` (native dialog via the window) and pass it as `pick_file`.
- Modify `app/ui/index.html` — add a `<select>` + Browse button above the terminal input in the wizard MT5 step and the Settings tab.
- Modify `app/ui/app.js` — a `wireTerminalPicker()` helper that loads terminals, populates the select, and wires select/Browse to the existing text input.
- Tests: `tests/unit/test_mt5_discovery.py`, `tests/unit/test_mt5_api.py`.

---

## Task 1: Robust terminal discovery

**Files:**
- Modify: `src/services/mt5_service.py:16-27`
- Test: `tests/unit/test_mt5_discovery.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_mt5_discovery.py
import src.services.mt5_service as mod


def _make_terminal(root, *parts):
    p = root.joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("", encoding="utf-8")
    return p


def test_discover_scans_multiple_roots_drops_name_filter_and_dedupes(tmp_path, monkeypatch):
    appdata = tmp_path / "Roaming"
    progfiles = tmp_path / "ProgramFiles"
    # A broker WITHOUT "MT5" in the name (old filter would have missed it):
    vantage = _make_terminal(progfiles, "Vantage Australia Terminal", "terminal64.exe")
    fusion = _make_terminal(appdata, "Fusion Markets MT5 Terminal", "terminal64.exe")

    monkeypatch.setattr(mod, "_terminal_roots",
                        lambda: [appdata, progfiles, tmp_path / "missing"])
    monkeypatch.setattr(mod, "_running_terminal_paths", lambda: [str(fusion)])  # dupe of fusion

    found = mod.discover_mt5_terminals()
    paths = sorted(t["path"].lower() for t in found)
    assert str(vantage).lower() in paths
    assert str(fusion).lower() in paths
    # Fusion appears via both filesystem and running-process — must be deduped.
    assert paths.count(str(fusion).lower()) == 1


def test_discover_labels_from_parent_folder(tmp_path, monkeypatch):
    pf = tmp_path / "PF"
    _make_terminal(pf, "Fusion Markets MT5 Terminal", "terminal64.exe")
    monkeypatch.setattr(mod, "_terminal_roots", lambda: [pf])
    monkeypatch.setattr(mod, "_running_terminal_paths", lambda: [])
    [t] = mod.discover_mt5_terminals()
    assert t["label"] == "Fusion Markets"  # " MT5 Terminal" suffix stripped


def test_find_mt5_terminals_is_path_list(tmp_path, monkeypatch):
    pf = tmp_path / "PF"
    _make_terminal(pf, "MetaTrader 5", "terminal64.exe")
    monkeypatch.setattr(mod, "_terminal_roots", lambda: [pf])
    monkeypatch.setattr(mod, "_running_terminal_paths", lambda: [])
    paths = mod.find_mt5_terminals()
    assert isinstance(paths, list) and all(isinstance(p, str) for p in paths)
    assert len(paths) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_mt5_discovery.py -v`
Expected: FAIL (`discover_mt5_terminals` / `_terminal_roots` / `_running_terminal_paths` not defined).

- [ ] **Step 3: Implement**

Replace `find_mt5_terminals` (lines 16-27 of `src/services/mt5_service.py`) with:

```python
def _terminal_roots() -> List[Path]:
    """Install roots to scan for terminal64.exe (existing ones only)."""
    names = ("APPDATA", "LOCALAPPDATA", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432")
    roots = []
    for name in names:
        val = os.getenv(name)
        if val:
            p = Path(val)
            if p.is_dir() and p not in roots:
                roots.append(p)
    return roots


def _scan_root(root: Path, max_depth: int = 3) -> List[str]:
    """Find terminal64.exe under root, bounded to max_depth to stay fast."""
    found = []
    root = root.resolve()
    base_depth = len(root.parts)
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            depth = len(Path(dirpath).parts) - base_depth
            if depth >= max_depth:
                dirnames[:] = []  # stop descending
            if "terminal64.exe" in filenames:
                found.append(str(Path(dirpath) / "terminal64.exe"))
    except OSError:
        pass  # unreadable tree — skip
    return found


def _running_terminal_paths() -> List[str]:
    """Paths of currently-running terminal64.exe processes (reliable backstop)."""
    paths = []
    try:
        import psutil
        for proc in psutil.process_iter(["name", "exe"]):
            try:
                if (proc.info.get("name") or "").lower() == "terminal64.exe":
                    exe = proc.info.get("exe")
                    if exe:
                        paths.append(exe)
            except (psutil.Error, OSError):
                continue
    except Exception:  # noqa: BLE001 - psutil missing/blocked must not break detection
        pass
    return paths


def _label_for(path: str) -> str:
    """Friendly broker label from the terminal's parent folder name."""
    name = Path(path).parent.name
    for suffix in (" MT5 Terminal", " MT5", " Terminal"):
        if name.endswith(suffix):
            return name[: -len(suffix)].strip() or name
    return name


def discover_mt5_terminals() -> List[dict]:
    """All MT5 terminals on this machine as [{"path","label"}], deduped.

    Scans common install roots (incl. Program Files) AND the paths of any running
    terminal64.exe processes. No folder-name filter, so non-"MT5" brokers are found.
    """
    raw = []
    for root in _terminal_roots():
        raw.extend(_scan_root(root))
    raw.extend(_running_terminal_paths())

    seen, out = set(), []
    for path in raw:
        key = os.path.normcase(os.path.abspath(path))
        if key in seen:
            continue
        seen.add(key)
        out.append({"path": path, "label": _label_for(path)})
    return out


def find_mt5_terminals() -> List[str]:
    """Backward-compatible path-only list (used by MT5Service init logging)."""
    return [t["path"] for t in discover_mt5_terminals()]
```

Confirm `from pathlib import Path`, `import os`, `from typing import List` are imported at the top of the file (they already are).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_mt5_discovery.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Run full suite + commit**

Run: `pytest tests/unit -q` (expect all pass).
```bash
git add src/services/mt5_service.py tests/unit/test_mt5_discovery.py
git commit -m "feat(mt5): robust multi-root + running-process terminal discovery"
```

---

## Task 2: Terminals + Browse API

**Files:**
- Create: `app/api/mt5_api.py`
- Test: `tests/unit/test_mt5_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_mt5_api.py
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.mt5_api as mt5_api


def _client(pick_file=None, monkeypatch=None, terminals=None):
    if terminals is not None:
        monkeypatch.setattr(mt5_api, "discover_mt5_terminals", lambda: terminals)
    app = FastAPI()
    mt5_api.add_mt5_routes(app, pick_file=pick_file)
    return TestClient(app)


def test_terminals_endpoint_returns_list_and_current(monkeypatch):
    monkeypatch.setattr(mt5_api, "discover_mt5_terminals",
                        lambda: [{"path": "C:/x/terminal64.exe", "label": "X"}])
    monkeypatch.setattr(mt5_api, "_current_terminal", lambda: "C:/x/terminal64.exe")
    c = _client()
    r = c.get("/api/mt5/terminals")
    assert r.status_code == 200
    body = r.json()
    assert body["terminals"] == [{"path": "C:/x/terminal64.exe", "label": "X"}]
    assert body["current"] == "C:/x/terminal64.exe"


def test_browse_returns_picked_path(monkeypatch):
    c = _client(pick_file=lambda: "C:/picked/terminal64.exe")
    r = c.post("/api/mt5/browse-terminal")
    assert r.status_code == 200
    assert r.json() == {"path": "C:/picked/terminal64.exe"}


def test_browse_returns_null_when_no_picker():
    app = FastAPI()
    mt5_api.add_mt5_routes(app, pick_file=None)
    c = TestClient(app)
    r = c.post("/api/mt5/browse-terminal")
    assert r.status_code == 200
    assert r.json() == {"path": None}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_mt5_api.py -v`
Expected: FAIL (`app.api.mt5_api` does not exist).

- [ ] **Step 3: Implement**

```python
# app/api/mt5_api.py
"""MT5 terminal discovery + native Browse endpoints (shared by wizard & Settings)."""
from typing import Callable, Optional

from fastapi import FastAPI

from src.services.mt5_service import discover_mt5_terminals
from app.storage.settings_store import SettingsStore


def _current_terminal() -> Optional[str]:
    return SettingsStore().get("mt5.terminal_path")


def add_mt5_routes(app: FastAPI, pick_file: Optional[Callable[[], Optional[str]]] = None) -> None:
    @app.get("/api/mt5/terminals")
    def list_terminals():
        return {"terminals": discover_mt5_terminals(), "current": _current_terminal()}

    @app.post("/api/mt5/browse-terminal")
    def browse_terminal():
        # pick_file runs the native dialog on the GUI thread; absent in headless/tests.
        path = pick_file() if pick_file is not None else None
        return {"path": path}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_mt5_api.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/api/mt5_api.py tests/unit/test_mt5_api.py
git commit -m "feat(mt5): /api/mt5/terminals + /api/mt5/browse-terminal endpoints"
```

---

## Task 3: Wire the API + pick_file callback

**Files:**
- Modify: `app/api/server.py:23` (signature) and the route-registration area (after `add_wizard_routes(app)`)
- Modify: `app/desktop.py`

- [ ] **Step 1: Extend `create_app` to accept and wire `pick_file`**

In `app/api/server.py`, add the import near the others at the top:
```python
from app.api.mt5_api import add_mt5_routes
```
Change the signature (line 23):
```python
def create_app(controller: EngineController, focus_callback: Optional[Callable] = None) -> FastAPI:
```
to:
```python
def create_app(controller: EngineController, focus_callback: Optional[Callable] = None,
               pick_file: Optional[Callable] = None) -> FastAPI:
```
And where routes are registered (right after the existing `add_wizard_routes(app)` line), add:
```python
    add_mt5_routes(app, pick_file=pick_file)
```

- [ ] **Step 2: Define the native picker in `desktop.py` and pass it**

In `app/desktop.py`, add this function near `_focus_window` (it uses the module-level `_window`):
```python
def _pick_terminal_file():
    """Open a native file dialog to choose terminal64.exe; return the path or None.

    pywebview marshals create_file_dialog to the GUI thread, so this is safe to call
    from the API worker thread. Returns None on cancel or if the window is gone.
    """
    if _window is None:
        return None
    try:
        result = _window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=("MetaTrader terminal (terminal64.exe)", "Executable (*.exe)"),
        )
    except Exception as e:  # noqa: BLE001 - dialog failure must not crash the API
        logger.info("file dialog failed: %s", e)
        return None
    if not result:
        return None
    return result[0] if isinstance(result, (list, tuple)) else result
```
Then update the `create_app(...)` call inside `_run_api` to pass it:
```python
        app = create_app(controller, focus_callback=_focus_window, pick_file=_pick_terminal_file)
```

- [ ] **Step 3: Verify wiring (no GUI needed)**

Run:
```
./venv/Scripts/python.exe -c "from app.engine_controller import EngineController; from app.api.server import create_app; from fastapi.testclient import TestClient; c=TestClient(create_app(EngineController(), pick_file=lambda: 'C:/p/terminal64.exe')); print(c.get('/api/mt5/terminals').status_code); print(c.post('/api/mt5/browse-terminal').json())"
```
Expected: prints `200` and `{'path': 'C:/p/terminal64.exe'}`.

- [ ] **Step 4: Run suite + commit**

Run: `pytest tests/unit -q` (expect all pass).
```bash
git add app/api/server.py app/desktop.py
git commit -m "feat(mt5): wire terminal discovery + native Browse into the app"
```

---

## Task 4: Picker UI in the wizard and Settings

**Files:**
- Modify: `app/ui/index.html` (wizard MT5 step ~line 51; Settings tab terminal field)
- Modify: `app/ui/app.js`

- [ ] **Step 1: Add the select + Browse markup (HTML)**

In `app/ui/index.html`, the wizard MT5 step currently has:
```html
            <label class="field">Terminal path
              <input id="wiz-mt5-terminal" type="text" placeholder="auto-detected" />
            </label>
```
Replace it with:
```html
            <label class="field">Terminal
              <select id="wiz-mt5-terminal-select"></select>
            </label>
            <div class="row">
              <input id="wiz-mt5-terminal" type="text" placeholder="terminal64.exe path" />
              <button id="wiz-mt5-terminal-browse" type="button" class="btn">Browse…</button>
            </div>
```
Find the Settings tab terminal field (the input with id `set-terminal`) and similarly add, immediately before that input, a select + Browse:
```html
            <label class="field">Terminal
              <select id="set-terminal-select"></select>
            </label>
            <div class="row">
              <input id="set-terminal" type="text" placeholder="terminal64.exe path" />
              <button id="set-terminal-browse" type="button" class="btn">Browse…</button>
            </div>
```
(Keep the existing `id="set-terminal"` input — it stays the value source that save reads. If it already sits inside a `<label>`, move it into the `row` div as shown.)

- [ ] **Step 2: Add the reusable picker wiring (JS)**

In `app/ui/app.js`, add this helper (near the other helpers, before it is used):
```javascript
// Populate a <select> with detected MT5 terminals and wire Browse → the text input.
// The text input (inputId) stays the value source that test/save read.
async function wireTerminalPicker(selectId, browseId, inputId) {
  const sel = $(selectId), input = $(inputId), browse = $(browseId);
  if (!sel || !input) return;
  let terminals = [], current = '';
  try {
    const d = await (await fetch('/api/mt5/terminals')).json();
    terminals = d.terminals || [];
    current = d.current || '';
  } catch (e) {}

  sel.innerHTML = '';
  for (const t of terminals) {
    const o = document.createElement('option');
    o.value = t.path;
    o.textContent = t.label ? `${t.label} — ${t.path}` : t.path;
    sel.appendChild(o);
  }
  const other = document.createElement('option');
  other.value = '__other__';
  other.textContent = 'Other… (enter path manually)';
  sel.appendChild(other);

  // Initial selection: stored value, else single detected, else "Other".
  const initial = input.value || current ||
    (terminals.length === 1 ? terminals[0].path : '');
  if (initial && terminals.some(t => t.path === initial)) {
    sel.value = initial; input.value = initial;
  } else if (initial) {
    sel.value = '__other__'; input.value = initial;
  } else {
    sel.value = terminals.length ? terminals[0].path : '__other__';
    input.value = sel.value === '__other__' ? '' : sel.value;
  }

  sel.addEventListener('change', () => {
    input.value = sel.value === '__other__' ? '' : sel.value;
    input.dispatchEvent(new Event('input'));  // re-runs wizard's test-enable check
  });
  if (browse) {
    browse.addEventListener('click', async () => {
      try {
        const r = await (await fetch('/api/mt5/browse-terminal', { method: 'POST' })).json();
        if (r.path) {
          input.value = r.path;
          if (![...sel.options].some(o => o.value === r.path)) {
            const o = document.createElement('option');
            o.value = r.path; o.textContent = r.path;
            sel.insertBefore(o, sel.lastChild);
          }
          sel.value = r.path;
          input.dispatchEvent(new Event('input'));
        }
      } catch (e) {}
    });
  }
}
```

- [ ] **Step 3: Call the helper from both places**

In `wizLoadMt5()` in `app/ui/app.js`, replace the body that prefilled the terminal input:
```javascript
  try {
    const d = await (await fetch('/api/wizard/mt5/detect')).json();
    const t = $('wiz-mt5-terminal');
    if (!t.value) t.value = d.current || (d.terminals && d.terminals[0]) || '';
  } catch (e) {}
```
with:
```javascript
  await wireTerminalPicker('wiz-mt5-terminal-select', 'wiz-mt5-terminal-browse', 'wiz-mt5-terminal');
```
In `loadSettings()` in `app/ui/app.js`, after the line `$('set-terminal').value = d.mt5.terminal_path || '';`, add:
```javascript
    await wireTerminalPicker('set-terminal-select', 'set-terminal-browse', 'set-terminal');
```
(Make `loadSettings` `async` if it is not already — it is declared `async function loadSettings()`.)

- [ ] **Step 4: Manual verification (needs the desktop app)**

Run: `venv\Scripts\python -m app.desktop`
- Settings tab: the Terminal dropdown lists detected terminals (including any in Program Files / running); selecting one fills the path; **Browse…** opens a native file dialog and the chosen `terminal64.exe` populates the field; Save still works.
- Reset onboarding to see the wizard if desired (`UPDATE settings SET value='0' WHERE key='onboarding.complete'` via the app DB, or a fresh `%APPDATA%\TV2MT5`), then confirm the wizard MT5 step shows the same picker and Test connection still works.
Quit from the tray.

- [ ] **Step 5: Commit**

```bash
git add app/ui/index.html app/ui/app.js
git commit -m "feat(mt5): terminal dropdown picker + Browse in wizard and Settings"
```

---

## Self-Review notes (addressed)

- **Spec coverage (7a):** detection rewrite (T1), terminals + browse endpoints (T2), callback wiring (T3), picker UI in both places (T4). All 7a spec items covered.
- **Backward compatibility:** `find_mt5_terminals()` keeps returning `list[str]` so `MT5Service.__init__`'s terminal-listing log and `detect.detect_mt5_terminals()` keep working unchanged; the new rich data flows only through the new endpoint/UI.
- **Type consistency:** `discover_mt5_terminals() -> [{"path","label"}]`, `pick_file() -> Optional[str]`, endpoints `/api/mt5/terminals` and `/api/mt5/browse-terminal` used identically across API, wiring, and UI.
- **No placeholders:** every code step is complete; run steps state expected output.
