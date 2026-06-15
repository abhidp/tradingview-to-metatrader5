# TV2MT5 Plan 6a — PyInstaller Freeze Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a working PyInstaller one-folder build (`dist/TV2MT5/TV2MT5.exe`) that launches windowed, serves its bundled UI, embeds mitmproxy, installs the CA via an elevated re-exec, and copies a live trade — proving every risky frozen-mode path before any installer work.

**Architecture:** Add a `_MEIPASS`-aware resource resolver and route all read-only bundled assets through it. Relocate mutable runtime data (`instruments.json`, `symbol_mappings.json`) out of the source tree into `%APPDATA%\TV2MT5\data` with seed-on-first-run (this also fixes an existing CWD-relative path bug). Replace two subprocess-based steps that assume a dev environment (`mitmdump` for CA generation, `python -m module` for the elevated cert helper) with frozen-safe equivalents. Drive everything from a new top-level `tv2mt5.py` entry that PyInstaller targets.

**Tech Stack:** Python 3.11, PyInstaller (one-folder), mitmproxy 11, pywebview/WebView2, pystray, FastAPI/uvicorn, MetaTrader5, Pillow.

**Spec:** `docs/superpowers/specs/2026-06-15-tv2mt5-plan-06-packaging-design.md`

---

## File Structure

- Create `app/resources.py` — `resource_path()` resolver (frozen vs source).
- Modify `app/paths.py` — add `get_data_file(name, seed_name=None)` for mutable data files in `%APPDATA%\TV2MT5\data`, seeding from bundled defaults.
- Modify `app/api/server.py` — resolve `UI_DIR` via `resource_path`.
- Modify `src/utils/symbol_mapper.py` — `mappings_file` via `get_data_file`.
- Modify `src/core/interceptor.py` — `instruments.json` via `get_data_file`.
- Modify `src/utils/instrument_manager.py` — `instruments.json` via `get_data_file`.
- Modify `src/scripts/install_certificate.py` — generate CA in-process (no `mitmdump`).
- Modify `app/wizard/cert.py` — frozen-aware elevated re-exec command.
- Modify `app/tray.py` — load tray icon from the bundled `.ico` (fallback to drawn glyph).
- Create `app/__version__.py` — single version constant.
- Create `tools/make_icon.py` + `app/ui/img/tv2mt5.ico` — generated placeholder icon.
- Create `tv2mt5.py` — top-level entry: argv dispatch (`--run-cert-admin`) → desktop.
- Create `tv2mt5.spec` — PyInstaller one-folder spec.
- Tests: `tests/unit/test_resources.py`, `tests/unit/test_paths_data.py`, `tests/unit/test_cert_reexec.py`, `tests/unit/test_cert_generate.py`.

> Test commands assume the repo venv. Use `venv\Scripts\python -m pytest ...` on Windows (or `./venv/Scripts/python.exe -m pytest ...` in Git Bash).

---

## Task 1: `resource_path()` resolver

**Files:**
- Create: `app/resources.py`
- Test: `tests/unit/test_resources.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_resources.py
import sys
from pathlib import Path

from app.resources import resource_path


def test_resource_path_from_source_points_at_repo_root():
    # In source mode (sys.frozen unset), app/ui must resolve under the repo root.
    p = resource_path("app/ui")
    assert p.name == "ui"
    assert (p.parent.name == "app")
    assert (p.parent.parent / "app").is_dir()


def test_resource_path_uses_meipass_when_frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    p = resource_path("data/instruments.json")
    assert p == Path(tmp_path) / "data" / "instruments.json"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_resources.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.resources'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/resources.py
"""Resolve read-only bundled resources in both source and PyInstaller-frozen runs.

When frozen, PyInstaller extracts bundled data under sys._MEIPASS. In source runs
the same relative paths resolve under the repo root (the parent of this app/ dir).
"""
import sys
from pathlib import Path


def resource_path(rel: str) -> Path:
    """Return the absolute path to a bundled resource given a repo-root-relative path."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent.parent  # repo root (parent of app/)
    return base / rel
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_resources.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add app/resources.py tests/unit/test_resources.py
git commit -m "feat(packaging): add _MEIPASS-aware resource_path resolver"
```

---

## Task 2: Mutable-data path helper with seed-on-first-run

**Files:**
- Modify: `app/paths.py`
- Test: `tests/unit/test_paths_data.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_paths_data.py
from pathlib import Path

import app.paths as paths


def test_get_data_file_returns_appdata_data_subdir(tmp_path, monkeypatch):
    monkeypatch.setenv("TV2MT5_DATA_DIR", str(tmp_path))
    p = paths.get_data_file("symbol_mappings.json")
    assert p == tmp_path / "symbol_mappings.json"
    assert tmp_path.is_dir()  # dir created


def test_get_data_file_seeds_from_bundled_default(tmp_path, monkeypatch):
    monkeypatch.setenv("TV2MT5_DATA_DIR", str(tmp_path))
    seed = tmp_path / "seed_src" / "instruments.json"
    seed.parent.mkdir(parents=True)
    seed.write_text('{"hello": 1}', encoding="utf-8")
    monkeypatch.setattr(paths, "resource_path", lambda rel: seed)

    p = paths.get_data_file("instruments.json", seed_name="instruments.json")
    assert p.read_text(encoding="utf-8") == '{"hello": 1}'


def test_get_data_file_no_seed_leaves_file_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("TV2MT5_DATA_DIR", str(tmp_path))
    p = paths.get_data_file("symbol_mappings.json")
    assert not p.exists()  # no seed_name → caller initialises lazily
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_paths_data.py -v`
Expected: FAIL with `AttributeError: module 'app.paths' has no attribute 'get_data_file'`

- [ ] **Step 3: Write minimal implementation**

Add to the top of `app/paths.py` (imports):

```python
import shutil

from app.resources import resource_path
```

Append to `app/paths.py`:

```python
def get_data_file(name: str, seed_name: str | None = None) -> Path:
    """Return the path to a mutable data file under %APPDATA%/TV2MT5/data/<name>.

    Creates the data dir. When seed_name is given and the target does not yet
    exist, copies the bundled default resource data/<seed_name> into place
    (first-run seeding). Honours TV2MT5_DATA_DIR for tests/packaging.
    """
    override = os.getenv("TV2MT5_DATA_DIR")
    data_dir = Path(override) if override else get_data_dir() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / name
    if seed_name and not target.exists():
        seed = resource_path(f"data/{seed_name}")
        if seed.exists():
            shutil.copyfile(seed, target)
    return target
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_paths_data.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add app/paths.py tests/unit/test_paths_data.py
git commit -m "feat(packaging): add get_data_file with seed-on-first-run"
```

---

## Task 3: Serve UI from the bundle

**Files:**
- Modify: `app/api/server.py:20`

- [ ] **Step 1: Make the change**

Replace line 20:

```python
UI_DIR = Path(__file__).parent.parent / "ui"
```

with:

```python
from app.resources import resource_path

UI_DIR = resource_path("app/ui")
```

(Keep the existing `from pathlib import Path` import; it is still used elsewhere in the file.)

- [ ] **Step 2: Verify the app still serves the UI from source**

Run: `venv\Scripts\python -m app.desktop`
Expected: window opens, dashboard renders (UI loaded from `app/ui`). Close the window (it minimises to tray); quit from the tray.

- [ ] **Step 3: Run the test suite to confirm no regression**

Run: `pytest tests/unit -q`
Expected: PASS (no failures introduced).

- [ ] **Step 4: Commit**

```bash
git add app/api/server.py
git commit -m "refactor(packaging): resolve UI_DIR via resource_path"
```

---

## Task 4: Relocate `symbol_mappings.json` to appdata

**Files:**
- Modify: `src/utils/symbol_mapper.py:36-37`

- [ ] **Step 1: Make the change**

Add the import near the other imports at the top of `src/utils/symbol_mapper.py`:

```python
from app.paths import get_data_file
```

Replace lines 36-37:

```python
        # Set up file path for mappings
        self.mappings_file = Path('data/symbol_mappings.json')
        self.mappings_file.parent.mkdir(exist_ok=True)
```

with:

```python
        # Mutable mappings live in %APPDATA%/TV2MT5/data (self-initialises from
        # MT5 when absent, so no bundled seed is needed).
        self.mappings_file = get_data_file('symbol_mappings.json')
```

- [ ] **Step 2: Verify import resolves and path is correct**

Run:
```bash
venv\Scripts\python -c "import os; os.environ['TV2MT5_DATA_DIR']=r'%TEMP%\tv2test'; from src.utils.symbol_mapper import SymbolMapper; print('import OK')"
```
Expected: prints `import OK` (no exception at import time).

- [ ] **Step 3: Commit**

```bash
git add src/utils/symbol_mapper.py
git commit -m "fix(packaging): store symbol_mappings.json in appdata (fixes CWD-relative path)"
```

---

## Task 5: Relocate `instruments.json` to appdata (with bundled seed)

**Files:**
- Modify: `src/utils/instrument_manager.py:12`
- Modify: `src/core/interceptor.py:112,126-128`

- [ ] **Step 1: Update `instrument_manager.py`**

Add the import at the top:

```python
from app.paths import get_data_file
```

Replace line 12:

```python
        self.config_path = Path(__file__).parent.parent.parent / 'data' / 'instruments.json'
```

with:

```python
        self.config_path = get_data_file('instruments.json', seed_name='instruments.json')
```

- [ ] **Step 2: Update `interceptor.py`**

Add the import near the top of `src/core/interceptor.py` (with the other imports):

```python
from app.paths import get_data_file
```

Replace lines 111-112:

```python
            # Preserve custom pairs if file exists
            config_path = Path(__file__).parent.parent.parent / 'data' / 'instruments.json'
```

with:

```python
            # Preserve custom pairs if file exists
            config_path = get_data_file('instruments.json', seed_name='instruments.json')
```

The existing save block (`config_path.parent.mkdir(...)` then `open(config_path, 'w')`) stays unchanged — `get_data_file` already created the dir, and `mkdir(parents=True, exist_ok=True)` is harmless.

- [ ] **Step 3: Verify imports resolve**

Run:
```bash
venv\Scripts\python -c "from src.utils.instrument_manager import InstrumentManager; from src.core.interceptor import *; print('imports OK')"
```
Expected: prints `imports OK`.

- [ ] **Step 4: Run the test suite**

Run: `pytest tests/unit -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/utils/instrument_manager.py src/core/interceptor.py
git commit -m "fix(packaging): store instruments.json in appdata with bundled seed"
```

---

## Task 6: Generate the CA in-process (no `mitmdump`)

**Files:**
- Modify: `src/scripts/install_certificate.py:44-70`
- Test: `tests/unit/test_cert_generate.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_cert_generate.py
from pathlib import Path

import src.scripts.install_certificate as ic


def test_generate_certificate_uses_certstore_not_mitmdump(monkeypatch, tmp_path):
    installer = ic.MitmCertInstaller()
    cert = tmp_path / ".mitmproxy" / "mitmproxy-ca-cert.cer"
    installer.cert_path = str(cert)

    calls = {}

    def fake_from_store(path, basename, key_size):
        calls["args"] = (Path(path), basename, key_size)
        Path(path).mkdir(parents=True, exist_ok=True)
        cert.write_text("CERT", encoding="utf-8")

    # Fail loudly if the old mitmdump subprocess path is taken.
    monkeypatch.setattr(ic.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("mitmdump used")))
    monkeypatch.setattr("mitmproxy.certs.CertStore.from_store", staticmethod(fake_from_store))

    assert installer.generate_certificate() is True
    assert cert.exists()
    assert calls["args"] == (cert.parent, "mitmproxy", 2048)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_cert_generate.py -v`
Expected: FAIL (current code calls `subprocess.Popen(['mitmdump', ...])` → `AssertionError: mitmdump used`).

- [ ] **Step 3: Replace `generate_certificate`**

Replace the whole `generate_certificate` method (lines 44-70) with:

```python
    def generate_certificate(self):
        """Generate the mitmproxy CA in-process if missing (no mitmdump subprocess).

        A frozen build ships no `mitmdump` executable, so we create the CA store
        directly via mitmproxy's API. CertStore.from_store writes
        mitmproxy-ca-cert.cer into the confdir (~/.mitmproxy by default).
        """
        if os.path.exists(self.cert_path):
            self.logger.info("Certificate already exists")
            return True
        self.logger.info("Certificate not found. Generating now...")
        try:
            from mitmproxy.certs import CertStore
            confdir = Path(self.cert_path).parent
            confdir.mkdir(parents=True, exist_ok=True)
            CertStore.from_store(confdir, "mitmproxy", 2048)
            if os.path.exists(self.cert_path):
                self.logger.info(f"Certificate generated successfully at: {self.cert_path}")
                return True
            self.logger.error("Certificate generation failed")
            return False
        except Exception as e:
            self.logger.error(f"Error generating certificate: {e}")
            return False
```

Ensure `from pathlib import Path` is imported at the top (it already is, line 7).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_cert_generate.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/scripts/install_certificate.py tests/unit/test_cert_generate.py
git commit -m "fix(packaging): generate mitmproxy CA in-process instead of via mitmdump"
```

---

## Task 7: Frozen-aware elevated cert re-exec

**Files:**
- Modify: `app/wizard/cert.py:31-39`
- Test: `tests/unit/test_cert_reexec.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_cert_reexec.py
import sys

import app.wizard.cert as cert


class _FakeShell:
    def __init__(self):
        self.last = None

    def ShellExecuteW(self, hwnd, verb, file, params, directory, show):
        self.last = (verb, file, params)
        return 42  # >32 == accepted


def _patch_shell(monkeypatch):
    fake = _FakeShell()
    import ctypes
    monkeypatch.setattr(ctypes, "windll", type("W", (), {"shell32": fake}), raising=False)
    return fake


def test_reexec_uses_module_flag_when_not_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    fake = _patch_shell(monkeypatch)
    cert._launch_elevated_cert_install()
    assert fake.last[2] == "-m app.wizard._cert_admin"


def test_reexec_uses_argv_sentinel_when_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    fake = _patch_shell(monkeypatch)
    cert._launch_elevated_cert_install()
    assert fake.last[2] == "--run-cert-admin"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_cert_reexec.py -v`
Expected: FAIL on the frozen case (current code always passes `-m app.wizard._cert_admin`).

- [ ] **Step 3: Update `_launch_elevated_cert_install`**

Replace lines 31-39 of `app/wizard/cert.py`:

```python
def _launch_elevated_cert_install() -> int:
    """Trigger a UAC prompt to run the elevated cert-install helper.

    Returns the ShellExecuteW result code (>32 means the launch was accepted).
    """
    import ctypes
    return int(ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, "-m app.wizard._cert_admin", None, 1
    ))
```

with:

```python
def _launch_elevated_cert_install() -> int:
    """Trigger a UAC prompt to run the elevated cert-install helper.

    A frozen exe cannot run `-m module`, so it re-execs itself with the
    --run-cert-admin sentinel (handled in tv2mt5.py). From source we keep the
    module form. Returns the ShellExecuteW code (>32 means the launch was accepted).
    """
    import ctypes
    params = "--run-cert-admin" if getattr(sys, "frozen", False) else "-m app.wizard._cert_admin"
    return int(ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, None, 1
    ))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_cert_reexec.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/wizard/cert.py tests/unit/test_cert_reexec.py
git commit -m "feat(packaging): frozen-aware elevated cert re-exec via --run-cert-admin"
```

---

## Task 8: Version constant

**Files:**
- Create: `app/__version__.py`

- [ ] **Step 1: Create the file**

```python
# app/__version__.py
"""Single source of truth for the app version (consumed by the installer build)."""
__version__ = "2.0.0-beta.1"
```

- [ ] **Step 2: Verify it imports**

Run: `venv\Scripts\python -c "from app.__version__ import __version__; print(__version__)"`
Expected: prints `2.0.0-beta.1`

- [ ] **Step 3: Commit**

```bash
git add app/__version__.py
git commit -m "chore(packaging): add app version constant"
```

---

## Task 9: Generated placeholder icon

**Files:**
- Create: `tools/make_icon.py`
- Create (generated): `app/ui/img/tv2mt5.ico`

- [ ] **Step 1: Write the icon generator**

```python
# tools/make_icon.py
"""Generate app/ui/img/tv2mt5.ico — a placeholder using the tray-icon style.

Run: python tools/make_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "app" / "ui" / "img" / "tv2mt5.ico"


def build() -> None:
    size = 256
    img = Image.new("RGBA", (size, size), "#1f2430")
    d = ImageDraw.Draw(img)
    m = size // 4
    d.rounded_rectangle([m, m, size - m, size - m], radius=size // 12, fill="#2d6cdf")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"wrote {OUT}")


if __name__ == "__main__":
    build()
```

- [ ] **Step 2: Generate the icon**

Run: `venv\Scripts\python tools\make_icon.py`
Expected: prints `wrote ...app\ui\img\tv2mt5.ico`; file exists.

- [ ] **Step 3: Commit**

```bash
git add tools/make_icon.py app/ui/img/tv2mt5.ico
git commit -m "chore(packaging): add generated placeholder app icon"
```

---

## Task 10: Tray icon from the bundle

**Files:**
- Modify: `app/tray.py:23-27`

- [ ] **Step 1: Make the change**

Add the import at the top of `app/tray.py`:

```python
from app.resources import resource_path
```

Replace `_icon_image` (lines 23-27):

```python
def _icon_image() -> Image.Image:
    img = Image.new("RGB", (64, 64), "#1f2430")
    d = ImageDraw.Draw(img)
    d.rectangle([18, 18, 46, 46], fill="#2d6cdf")
    return img
```

with:

```python
def _icon_image() -> Image.Image:
    """Tray icon from the bundled .ico; fall back to a drawn glyph if unavailable."""
    try:
        return Image.open(resource_path("app/ui/img/tv2mt5.ico"))
    except Exception:  # noqa: BLE001 — any load failure → drawn fallback
        img = Image.new("RGB", (64, 64), "#1f2430")
        d = ImageDraw.Draw(img)
        d.rectangle([18, 18, 46, 46], fill="#2d6cdf")
        return img
```

- [ ] **Step 2: Verify the tray still builds**

Run: `venv\Scripts\python -c "from app.tray import build_tray; t = build_tray(lambda: None, lambda i: None); print('tray OK', t.icon.size)"`
Expected: prints `tray OK (256, 256)` (or the first embedded size).

- [ ] **Step 3: Commit**

```bash
git add app/tray.py
git commit -m "feat(packaging): load tray icon from bundled .ico"
```

---

## Task 11: Top-level entry with argv dispatch

**Files:**
- Create: `tv2mt5.py`

- [ ] **Step 1: Create the entry**

```python
# tv2mt5.py
"""Top-level entry for TV2MT5 Desktop (PyInstaller target).

Handles the elevated cert-admin re-exec first: a frozen exe cannot run
`python -m app.wizard._cert_admin`, so the elevated relaunch passes the
--run-cert-admin sentinel which we route here before any GUI/engine starts.
Otherwise launches the desktop app.
"""
import sys


def main() -> None:
    if "--run-cert-admin" in sys.argv:
        from app.wizard._cert_admin import main as cert_admin_main
        sys.exit(cert_admin_main())
    from app.desktop import main as desktop_main
    desktop_main()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the dispatch (source mode)**

Run: `venv\Scripts\python tv2mt5.py --run-cert-admin`
Expected: runs the cert generate/install path and exits (it will attempt `certutil -addstore`, which may prompt/fail without admin — that's fine; the point is it routes to the cert helper, not the GUI). Confirm no window opens.

Then run: `venv\Scripts\python tv2mt5.py`
Expected: the desktop window opens (same as `python -m app.desktop`). Quit from the tray.

- [ ] **Step 3: Commit**

```bash
git add tv2mt5.py
git commit -m "feat(packaging): top-level entry with --run-cert-admin dispatch"
```

---

## Task 12: PyInstaller spec

**Files:**
- Create: `tv2mt5.spec`

- [ ] **Step 1: Ensure PyInstaller is available**

Run: `venv\Scripts\pip install pyinstaller==6.10.0`
Expected: installs (or "already satisfied"). Then add it to dev deps:

Append to `requirements-dev.txt`:
```
pyinstaller==6.10.0
```

- [ ] **Step 2: Write the spec**

```python
# tv2mt5.spec
# PyInstaller one-folder build for TV2MT5 Desktop. Build: pyinstaller --noconfirm tv2mt5.spec
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

datas = [
    ('app/ui', 'app/ui'),                                  # html/js/css/img + tv2mt5.ico
    ('data/instruments.json', 'data'),                     # seed default
    ('data/symbol_mappings.template.json', 'data'),        # seed template
]
binaries = []
hiddenimports = [
    'pystray._win32',
    'win32timezone',
    'MetaTrader5',
]

# mitmproxy loads addons/protocols lazily; pywebview ships JS bridge data files.
# Collect everything for both so nothing is missed at runtime.
for pkg in ('mitmproxy', 'webview'):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

hiddenimports += collect_submodules('uvicorn')

a = Analysis(
    ['tv2mt5.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib'],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TV2MT5',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                     # windowed: no console for end users
    icon='app/ui/img/tv2mt5.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='TV2MT5',
)
```

- [ ] **Step 3: Build**

Run: `venv\Scripts\pyinstaller --noconfirm tv2mt5.spec`
Expected: completes; `dist\TV2MT5\TV2MT5.exe` exists. Note any `WARNING: Hidden import "X" not found` — if a runtime crash later points at a missing module, add it to `hiddenimports` and rebuild.

- [ ] **Step 4: Add build artifacts to .gitignore**

Add to `.gitignore`:
```
/build/
/dist/
*.spec.bak
```

- [ ] **Step 5: Commit**

```bash
git add tv2mt5.spec requirements-dev.txt .gitignore
git commit -m "feat(packaging): PyInstaller one-folder spec"
```

---

## Task 13: Frozen-build acceptance (manual)

No code; this is the spike's payoff — verify the built exe end-to-end. Record results in the PR description.

- [ ] **Step 1: Launch the frozen exe**

Run: `dist\TV2MT5\TV2MT5.exe`
Expected: a windowed app opens (no console window); the dashboard UI renders (UI served from the bundle via `_MEIPASS`).

- [ ] **Step 2: Single-instance guard**

With the app running, launch `dist\TV2MT5\TV2MT5.exe` again.
Expected: the second launch focuses the existing window and exits (no second instance).

- [ ] **Step 3: Cert install via elevated re-exec**

In the wizard's certificate step, click install.
Expected: a UAC prompt appears; accepting it runs the `--run-cert-admin` helper, generates the CA in `~/.mitmproxy`, adds it to the Root store; the status polls to "trusted".
Verify: `certutil -store root mitmproxy` shows `CN=mitmproxy`.

- [ ] **Step 4: Engine + mitmproxy start**

Click Start (or finish the wizard).
Expected: no missing-module crash; the proxy binds `127.0.0.1:8080`. Verify with `netstat -ano | findstr :8080`.

- [ ] **Step 5: Data lands in appdata**

Check `%APPDATA%\TV2MT5\data\`.
Expected: `instruments.json` present (seeded and/or synced from broker); after symbol activity, `symbol_mappings.json` appears here — **not** under `dist\TV2MT5\`.

- [ ] **Step 6: Live copy**

Connect MT5 (wizard step 3) and place one small test trade in TradingView's broker panel.
Expected: the trade copies to MT5; the Trades tab shows ✓.

- [ ] **Step 7: Record results**

Note pass/fail for each step. If any hidden-import crash occurred, the fix is to add the module to `tv2mt5.spec` `hiddenimports` and rebuild (Task 12, Step 3), then re-verify.

---

## Self-Review notes (addressed)

- **Spec coverage:** resource resolution (T1,T3), data relocation (T2,T4,T5), CA in-process gen (T6), frozen re-exec (T7), version (T8), icon (T9,T10), entry (T11), spec/build (T12), acceptance checklist (T13). All 6a spec items covered.
- **Type/name consistency:** `resource_path(rel)`, `get_data_file(name, seed_name=None)`, `--run-cert-admin` sentinel, and `app/ui/img/tv2mt5.ico` path are used identically across tasks.
- **No placeholders:** every code step shows full code; every run step states expected output.
