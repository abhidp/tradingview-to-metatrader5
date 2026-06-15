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
