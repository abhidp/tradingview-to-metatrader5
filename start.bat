@echo off
echo TradingView to MT5 Copier
echo ========================
echo.

REM Check if Python is installed
python --version > nul 2>&1
if errorlevel 1 (
    echo Python not found! Please install Python 3.11 or higher.
    pause
    exit
)

REM Check if MT5 is running
tasklist /FI "IMAGENAME eq terminal64.exe" 2>NUL | find /I /N "terminal64.exe">NUL
if errorlevel 1 (
    echo Please start MetaTrader5 first!
    pause
    exit
)

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate
    python -m pip install -r requirements.txt
)

REM Start proxy server in new window
start "TV Proxy" cmd /c "venv\Scripts\activate && python run.py proxy"

REM Start worker in new window
start "MT5 Worker" cmd /c "venv\Scripts\activate && python run.py worker"

REM Configure Windows Proxy
echo.
echo Configuring Windows Proxy Settings...
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d 1 /f
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer /d "127.0.0.1:8080" /f

echo.
echo ✅ Started successfully!
echo.
echo Please ensure:
echo 1. MetaTrader5 is running
echo 2. Algo Trading is enabled in MT5
echo 3. Log into TradingView
echo.
pause