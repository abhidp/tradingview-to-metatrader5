@echo off
echo Starting TradingView Proxy Server...
echo.
call venv\Scripts\activate
mitmdump --quiet -s src/proxy_server.py
pause