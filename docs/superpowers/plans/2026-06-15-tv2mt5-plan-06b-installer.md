# TV2MT5 Plan 6b — Inno Setup Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap the validated PyInstaller one-folder build (from Plan 6a) into a per-user Windows `.exe` installer that requires no admin to install, detects and (if absent) fetches the WebView2 runtime, creates Start Menu / optional desktop shortcuts, and preserves user data on uninstall — produced by a single `build.ps1` command.

**Architecture:** An Inno Setup script (`installer/tv2mt5.iss`) installs `dist\TV2MT5\*` to `{localappdata}\Programs\TV2MT5` with `PrivilegesRequired=lowest`. A `[Code]` section checks the WebView2 Evergreen registry key and uses Inno's built-in download page to fetch Microsoft's bootstrapper only when missing. Uninstall removes only the program folder, leaving `%APPDATA%\TV2MT5` intact. `build.ps1` reads the version from `app/__version__.py`, runs PyInstaller, then ISCC with the version wired in.

**Tech Stack:** Inno Setup 6.1+ (for `CreateDownloadPage`), PowerShell, PyInstaller (from 6a).

**Spec:** `docs/superpowers/specs/2026-06-15-tv2mt5-plan-06-packaging-design.md`
**Prerequisite:** Plan 6a complete and its acceptance checklist passing (`dist\TV2MT5\TV2MT5.exe` runs).

---

## File Structure

- Create `installer/tv2mt5.iss` — Inno Setup script (per-user, WebView2 detection, shortcuts).
- Create `build.ps1` — one-command build: PyInstaller → ISCC with version.
- Modify `.gitignore` — ignore `installer/Output/`.
- Modify `ReadMe.md` — document the build command and the manual cert-removal note.

> Requires Inno Setup 6 installed (provides `ISCC.exe`). Download: https://jrsoftware.org/isdl.php

---

## Task 1: Inno Setup script

**Files:**
- Create: `installer/tv2mt5.iss`

- [ ] **Step 1: Write the script**

```iss
; installer/tv2mt5.iss — per-user installer for TV2MT5 Desktop.
; Build via build.ps1, or: ISCC.exe /DAppVersion=2.0.0-beta.1 installer\tv2mt5.iss
#define AppName "TV2MT5 Desktop"
#define AppExe "TV2MT5.exe"
#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif

[Setup]
AppId={{A7E9C4F2-3B61-4D8E-9F2A-6C1B2D5E7F90}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Abhi D
AppPublisherURL=https://github.com/abhidp/tradingview-to-metatrader5
DefaultDirName={localappdata}\Programs\TV2MT5
DefaultGroupName=TV2MT5
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=TV2MT5-Setup-{#AppVersion}
SetupIconFile=..\app\ui\img\tv2mt5.ico
UninstallDisplayIcon={app}\{#AppExe}
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "..\dist\TV2MT5\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\TV2MT5"; Filename: "{app}\{#AppExe}"
Name: "{userdesktop}\TV2MT5"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; \
  Check: WV2Needed; Flags: waituntilterminated; StatusMsg: "Installing WebView2 Runtime..."
Filename: "{app}\{#AppExe}"; Description: "Launch TV2MT5"; Flags: nowait postinstall skipifsilent

[Code]
const
  WV2_CLIENT = '{F3017226-FA46-457B-9129-E1B887D33167}';

var
  DownloadPage: TDownloadWizardPage;
  gWV2Needed: Boolean;

function WV2RegHas(RootKey: Integer; SubKey: String): Boolean;
var
  pv: String;
begin
  Result := RegQueryStringValue(RootKey, SubKey, 'pv', pv) and (pv <> '') and (pv <> '0.0.0.0');
end;

function WebView2Installed(): Boolean;
begin
  Result :=
    WV2RegHas(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\' + WV2_CLIENT) or
    WV2RegHas(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + WV2_CLIENT) or
    WV2RegHas(HKCU, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + WV2_CLIENT);
end;

function WV2Needed(): Boolean;
begin
  Result := gWV2Needed;
end;

function OnDownloadProgress(const Url, FileName: String; const Progress, ProgressMax: Int64): Boolean;
begin
  Result := True;
end;

procedure InitializeWizard();
begin
  gWV2Needed := not WebView2Installed();
  DownloadPage := CreateDownloadPage(
    'Downloading WebView2 Runtime',
    'TV2MT5 needs the Microsoft WebView2 runtime. Downloading the installer...',
    @OnDownloadProgress);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = wpReady) and gWV2Needed then
  begin
    DownloadPage.Clear;
    DownloadPage.Add(
      'https://go.microsoft.com/fwlink/p/?LinkId=2124703',
      'MicrosoftEdgeWebview2Setup.exe', '');
    DownloadPage.Show;
    try
      try
        DownloadPage.Download;
      except
        SuppressibleMsgBox(
          'Could not download the WebView2 runtime. The app may not display ' +
          'correctly until it is installed.' + #13#10 + GetExceptionMessage,
          mbError, MB_OK, IDOK);
        gWV2Needed := False;  { skip the [Run] step; let install proceed }
      end;
    finally
      DownloadPage.Hide;
    end;
  end;
end;
```

- [ ] **Step 2: Verify the script compiles**

Run (PowerShell):
```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DAppVersion=0.0.0-dev installer\tv2mt5.iss
```
Expected: compiles to `installer\Output\TV2MT5-Setup-0.0.0-dev.exe` (assuming `dist\TV2MT5\` exists from 6a). If ISCC reports `[Files] ... no files found`, run the 6a build first (`pyinstaller --noconfirm tv2mt5.spec`).

- [ ] **Step 3: Commit**

```bash
git add installer/tv2mt5.iss
git commit -m "feat(packaging): per-user Inno Setup installer with WebView2 detection"
```

---

## Task 2: One-command build script

**Files:**
- Create: `build.ps1`

- [ ] **Step 1: Write `build.ps1`**

```powershell
# build.ps1 — freeze with PyInstaller, then build the Inno Setup installer.
# Usage:  powershell -ExecutionPolicy Bypass -File .\build.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# Single source of truth for the version.
$verMatch = Select-String -Path (Join-Path $root 'app\__version__.py') `
  -Pattern '__version__\s*=\s*"([^"]+)"'
$version = $verMatch.Matches[0].Groups[1].Value
Write-Host "==> Building TV2MT5 $version"

# 1) Freeze.
& (Join-Path $root 'venv\Scripts\pyinstaller.exe') --noconfirm (Join-Path $root 'tv2mt5.spec')
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }

# 2) Locate ISCC.
$iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
  $cand = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
  if (Test-Path $cand) { $iscc = $cand } else { throw 'ISCC.exe not found. Install Inno Setup 6.' }
}

# 3) Build installer.
& $iscc "/DAppVersion=$version" (Join-Path $root 'installer\tv2mt5.iss')
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup failed' }

Write-Host "==> Installer: installer\Output\TV2MT5-Setup-$version.exe"
```

- [ ] **Step 2: Run the full build**

Run: `powershell -ExecutionPolicy Bypass -File .\build.ps1`
Expected: prints `==> Building TV2MT5 2.0.0-beta.1`, runs PyInstaller, then ISCC, and ends with `==> Installer: installer\Output\TV2MT5-Setup-2.0.0-beta.1.exe`. Confirm the file exists.

- [ ] **Step 3: Commit**

```bash
git add build.ps1
git commit -m "feat(packaging): build.ps1 one-command freeze + installer"
```

---

## Task 3: Ignore installer output

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add the ignore rule**

Append to `.gitignore`:
```
/installer/Output/
```

- [ ] **Step 2: Verify the built installer is untracked**

Run: `git status --porcelain installer/Output`
Expected: no output (the Output dir is ignored).

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore(packaging): ignore installer/Output"
```

---

## Task 4: Document the build + cert-removal note

**Files:**
- Modify: `ReadMe.md`

- [ ] **Step 1: Add a "Building the installer" section**

Append to `ReadMe.md`:

```markdown
## Building the Windows installer (v2 desktop)

Prerequisites: the project venv with dev deps (`pip install -r requirements-dev.txt`,
includes PyInstaller) and [Inno Setup 6](https://jrsoftware.org/isdl.php).

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

Output: `installer\Output\TV2MT5-Setup-<version>.exe` (per-user install, no admin
required). The version comes from `app/__version__.py`.

### Notes
- **WebView2:** the installer detects the Microsoft Edge WebView2 runtime and
  downloads it only if missing (preinstalled on Windows 11).
- **App data** lives in `%APPDATA%\TV2MT5` and is **kept on uninstall** (trades,
  settings, logs).
- **Security certificate:** the app installs a local mitmproxy CA into the Windows
  Root store during onboarding. Uninstalling the app does **not** remove it. To
  remove it manually: run `certutil -delstore root mitmproxy` from an elevated
  prompt, or remove "mitmproxy" under certmgr.msc → Trusted Root Certification
  Authorities.
```

- [ ] **Step 2: Commit**

```bash
git add ReadMe.md
git commit -m "docs(packaging): document installer build and cert removal"
```

---

## Task 5: Installer acceptance (manual)

No code; verify the produced installer end-to-end. Record results in the PR.

- [ ] **Step 1: Install with no admin prompt**

Run `installer\Output\TV2MT5-Setup-<version>.exe`.
Expected: **no UAC prompt** for the install itself; installs to `%LocalAppData%\Programs\TV2MT5`. If WebView2 was absent, the download/install step runs; on Win11 it is skipped.

- [ ] **Step 2: Shortcuts**

Expected: Start Menu shows "TV2MT5"; if the desktop-icon task was checked, a desktop shortcut exists. Both launch the app.

- [ ] **Step 3: Full run from the installed location**

Launch from the Start Menu shortcut, complete the wizard (cert UAC prompt appears at the cert step only), connect MT5, and place one small test trade in TradingView.
Expected: trade copies TV→MT5; Trades tab shows ✓. Confirms `_MEIPASS` resources and appdata data both resolve from the installed copy.

- [ ] **Step 4: Data location**

Check `%APPDATA%\TV2MT5\`.
Expected: `tv2mt5.db`, `logs\tv2mt5.log`, `data\instruments.json` (and `data\symbol_mappings.json` after symbol activity) — none of these under `%LocalAppData%\Programs\TV2MT5`.

- [ ] **Step 5: Uninstall preserves user data**

Uninstall via Settings → Apps (or the uninstaller in the install dir).
Expected: `%LocalAppData%\Programs\TV2MT5` is removed; `%APPDATA%\TV2MT5` (DB/settings/logs/data) **remains**. Reinstall and confirm prior trades/settings are still present.

- [ ] **Step 6: Record results**

Note pass/fail per step in the PR description. Then merge Plan 6 to `v2-desktop` (base `v2-desktop`, merge commit), completing the roadmap.

---

## Self-Review notes (addressed)

- **Spec coverage:** per-user install + shortcuts (T1), WebView2 detect-and-fetch (T1 `[Code]`), uninstall data preservation (T1 has no `%APPDATA%` removal; verified T5), build.ps1 (T2), version wiring from `app/__version__.py` (T2), docs incl. cert-removal caveat (T4), acceptance (T5). All 6b spec items covered.
- **Consistency:** `AppVersion` define, `installer\Output\TV2MT5-Setup-<version>.exe` output name, and `app/__version__.py` version source are used identically across the `.iss`, `build.ps1`, and docs.
- **No placeholders:** the `.iss` and `build.ps1` are complete; every run step states expected output.
- **Dependency note:** the WebView2 download page requires Inno Setup **6.1+** (`CreateDownloadPage`/`TDownloadWizardPage`); documented in the header and ReadMe.
```
