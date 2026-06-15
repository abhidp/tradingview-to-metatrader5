# TV2MT5 Desktop — Plan 6: Packaging Design Spec

**Date:** 2026-06-15
**Status:** Approved for planning
**Author:** Abhi D (with Claude)
**Branch:** `plan-06-packaging` (off `v2-desktop`)
**Parent spec:** `docs/superpowers/specs/2026-06-13-tv2mt5-desktop-design.md`
**Roadmap:** `docs/superpowers/plans/2026-06-13-tv2mt5-desktop-plan-roadmap.md` (row 6)

## Problem

The v2 desktop app runs today only from a Python venv (`python -m app.desktop`).
To ship it to non-technical traders it must become a **single-click Windows
installer**: a frozen executable with no Python/venv/pip, wrapped in an `.exe`
installer. This is the last roadmap plan; Plans 4b (proxy manager) and 5
(monetization seams) are **deferred**.

## Goal

Produce a **locally-built, installable `.exe`** that a non-technical Windows user
can run: install (no admin) → first-run wizard → copy a live trade. Two stages:

- **Plan 6a — Freeze:** a working **PyInstaller one-folder** build that launches
  and proves the risky parts (mitmproxy embedded, UI from the bundle, elevated
  cert re-exec, MT5 connect, live copy).
- **Plan 6b — Installer:** wrap the validated build in an **Inno Setup** per-user
  installer with WebView2 detection and user-data preservation.

## Non-Goals (deferred, consistent with parent spec)

- No code signing (exe/installer ship unsigned; signing is a later concern).
- No CI / GitHub Actions release automation — build is run **manually** by the author.
- No auto-update (the `Updater` seam stays a stub; Plan 5 is deferred).
- No cross-platform packaging (Windows-only).
- No change to trade interception/execution logic.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Freeze tool | PyInstaller **one-folder** (`COLLECT`) | Faster startup than one-file; friendlier to mitmproxy's lazy imports; easier to inspect/debug. |
| Console | **`--windowed`** (no console window) | Consumer app; logs already go to the rotating file. The dev console Ctrl+C path is unaffected when run from source. |
| Frozen re-entry for cert install | **Argv sentinel** (`--run-cert-admin`) | A frozen exe is not a Python interpreter; `sys.executable -m app.wizard._cert_admin` cannot work. One dispatch block works frozen and from source; no second exe. |
| Resource resolution | `app/resources.py` `resource_path()` using `sys._MEIPASS` when frozen | Single helper replaces all source-relative paths (UI dir, xlsx, icon) that break once bundled. |
| Version source of truth | `app/__version__.py` | One constant consumed by the spec and the installer (`ISCC /D`). |
| Installer | **Inno Setup**, per-user | `PrivilegesRequired=lowest`, install to `{localappdata}\Programs\TV2MT5`; no UAC to install/uninstall. |
| WebView2 runtime | **Detect, download if missing** | Registry check; run Microsoft's online bootstrapper only when absent (no-op on Win11). |
| App icon | **Generated placeholder `.ico`** | Derived from the existing in-code tray style; wired into tray, window, exe, installer. Swap real branding later. |
| Uninstall data policy | **Preserve `%APPDATA%\TV2MT5`** | Keep SQLite trades/settings/logs across reinstall/upgrade. |
| Build orchestration | Committed **`build.ps1`** wrapper | One command (PyInstaller → ISCC, version wired in); convenient across many 6a iterations. |

## Architecture / Changes

### Plan 6a — Freeze

**1. `app/resources.py` (new)**
```python
def resource_path(rel: str) -> Path:
    """Path to a bundled resource: sys._MEIPASS when frozen, else the source tree."""
    base = Path(getattr(sys, "_MEIPASS", <source-root>))
    return base / rel
```
Rewire the **read-only bundled** resource readers through it:
- `app/api/server.py:20` `UI_DIR = Path(__file__).parent.parent / "ui"` → `resource_path("app/ui")`.
- Tray/window icon load → `resource_path("app/ui/img/tv2mt5.ico")`.

> `symbol_specifications.xlsx` is **not** bundled — it is output-only (written by
> `src/scripts/symbol_specifications.py`, never read at runtime).

**2. Relocate mutable `data/` to `%APPDATA%\TV2MT5\data` (seed-on-first-run)**

Two runtime files currently live in the source `data/` dir and are **written at
runtime** — they must not live next to the frozen exe, and one uses a broken
CWD-relative path:
- `src/utils/symbol_mapper.py:36` — `Path('data/symbol_mappings.json')`
  (**CWD-relative**, read+write; breaks when launched from a Start Menu shortcut).
  No bundled seed — `SymbolMapper` self-initialises from MT5 when the file is
  absent; seeding the static `data/symbol_mappings.template.json` would suppress
  that and bake in a wrong broker suffix, so it is deliberately not bundled.
- `src/core/interceptor.py:112` and `src/utils/instrument_manager.py:12` —
  `data/instruments.json` (read+written; synced from the broker at runtime).
  Seed default: bundled `data/instruments.json`.

Add data-file path helpers to `app/paths.py` (e.g. `get_data_file(name)` returning
`%APPDATA%\TV2MT5\data\<name>`, creating the dir). On first access, **seed** the
appdata copy from the bundled default via `resource_path(...)` if it does not exist.
Repoint the three call sites at these helpers. This fixes both the frozen-write
problem and the existing CWD-relative bug.

Bundled seed `datas`: `data/instruments.json` only (symbol_mappings is not seeded — see above).

**3. Frozen re-entry for elevated cert install**
- Add an argv dispatch at the very top of the entry module: if `--run-cert-admin`
  is present, run the cert-install routine (current `app/wizard/_cert_admin.py`
  body) and `sys.exit` before any GUI/engine startup.
- `app/wizard/cert.py:_launch_elevated_cert_install()` builds the elevated re-exec
  from `sys.executable`:
  - **frozen:** `ShellExecute("runas", sys.executable, "--run-cert-admin", ...)`
  - **source:** keep the existing `-m app.wizard._cert_admin` form (detect via
    `getattr(sys, "frozen", False)`).
- **CA generation must not shell out to `mitmdump`** (`install_certificate.py:51`):
  no `mitmdump.exe` ships beside the frozen exe. Replace `generate_certificate()`'s
  subprocess with mitmproxy's in-process API:
  `mitmproxy.certs.CertStore.from_store(Path("~/.mitmproxy"), "mitmproxy", 2048)`
  (verified to write `mitmproxy-ca-cert.cer`). Works frozen and from source.

**4. Entry point**
- New top-level `tv2mt5.py`: performs the argv dispatch, then calls
  `app.desktop.main()`. PyInstaller targets this file.
- Keep `app/desktop.py:main()` and `app/__main__.py` working for source runs.

**5. `tv2mt5.spec` (PyInstaller)**
- `datas`: `app/ui/**` (html/js/css/img), `data/instruments.json`, the `.ico`.
- `collect_all("mitmproxy")`; hidden imports for `MetaTrader5`, `pystray._win32`,
  `win32*` (pywin32), `uvicorn` (loggers/protocols), `fastapi`/`pydantic` as needed.
- `EXE(... console=False, icon=<ico>)`; `COLLECT(...)` → `dist/TV2MT5/`.

**6. `app/__version__.py` (new)** — `__version__ = "2.0.0-beta.1"`; consumed by the
spec build metadata and the installer.

### Plan 6b — Installer

**`installer/tv2mt5.iss` (Inno Setup)**
- `[Setup]`: `PrivilegesRequired=lowest`, `DefaultDirName={localappdata}\Programs\TV2MT5`,
  fixed `AppId` GUID, `AppVersion` from `ISCC /DAppVersion=...`, `SetupIconFile` = the `.ico`,
  `OutputBaseFilename=TV2MT5-Setup-{#AppVersion}`, `OutputDir=Output`.
- `[Files]`: `Source: "dist\TV2MT5\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs`.
- `[Icons]`: Start Menu shortcut (always); desktop shortcut behind a `[Tasks]` checkbox.
- `[Run]`: optional "launch now" checkbox post-install.

**WebView2 detection (`[Code]`)**
- Check the Evergreen runtime registry value `pv` under client GUID
  `{F3017226-FA46-457B-9129-E1B887D33167}` across
  `HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\...`,
  `HKLM\...\Microsoft\EdgeUpdate\Clients\...`, and the `HKCU` variant.
  Present iff a value exists and is not empty/`0.0.0.0`.
- If absent: download `https://go.microsoft.com/fwlink/p/?LinkId=2124703`
  (`MicrosoftEdgeWebview2Setup.exe`) to `{tmp}`, run `/silent /install`.

**Uninstall**
- Remove only `{app}`. **Do not** delete `%APPDATA%\TV2MT5` (trades/settings/logs).
- The mitmproxy CA in the Root store is left in place (avoids uninstall-time UAC);
  documented in the README with manual-removal instructions.

**`build.ps1` (new)**
1. Read version from `app/__version__.py`.
2. `pyinstaller --noconfirm tv2mt5.spec`.
3. `ISCC.exe /DAppVersion=<version> installer\tv2mt5.iss`.
4. Print the path to `installer/Output/TV2MT5-Setup-<version>.exe`.

## Error Handling / Risks

- **mitmproxy freeze (highest risk):** lazy/plugin imports may be missed by
  PyInstaller. Mitigation: `collect_all("mitmproxy")` + iterate on `ModuleNotFound`
  at runtime; this is exactly what 6a's spike validates before any installer work.
- **`sys._MEIPASS` not present from source:** `resource_path` falls back to the
  source root, so source runs and tests are unaffected.
- **WebView2 missing on non-Evergreen machines:** handled by the installer's
  detect-and-fetch; on the author's Win11 it's a no-op.
- **First-run still needs UAC for the cert** — by design; install itself stays
  admin-free. The wizard already drives that prompt.

## Testing / Acceptance

**Plan 6a — from `dist/TV2MT5/TV2MT5.exe`:**
1. Launches windowed (no console); single-instance guard holds (second launch focuses first).
2. UI loads from the bundle (`_MEIPASS`), all tabs render.
3. **Start** binds `:8080` and mitmproxy runs (no missing-module crash).
4. Cert step's UAC re-exec (`--run-cert-admin`) installs the CA; status flips trusted.
5. MT5 connects; one live TV→MT5 trade copies end-to-end.
6. Mutable data lands in `%APPDATA%\TV2MT5\data` (seeded `symbol_mappings.json`;
   broker instrument sync writes `instruments.json` there, **not** under the install dir).

**Plan 6b — from the produced `TV2MT5-Setup-<version>.exe`:**
1. Installs with **no admin prompt**; lands in `{localappdata}\Programs\TV2MT5`.
2. Start Menu + (opted-in) desktop shortcuts launch the app.
3. WebView2 check passes (or installs the runtime when absent).
4. Full wizard → live trade copy works from the **installed** location.
5. Uninstall removes the program folder but **leaves `%APPDATA%\TV2MT5` intact**;
   reinstall retains prior trades/settings.

## Out of scope / follow-ups

- Code signing of exe + installer.
- GitHub Releases + `version.json` auto-update (wires into the deferred `Updater` seam).
- Offline-bundled WebView2 bootstrapper (only if online fetch proves unreliable).
- Promote `v2-desktop` → `main` as the v2.0 release (separate release task).
