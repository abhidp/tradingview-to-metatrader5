@echo off
echo Starting TradingView Proxy Server...
echo.
call venv\Scripts\activate

rem Start the proxy
mitmdump --quiet -s src/main.py
pause