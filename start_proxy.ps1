Write-Host "Starting TradingView Proxy Server..." -ForegroundColor Green

# Activate virtual environment
& .\venv\Scripts\Activate.ps1

# Set PYTHONPATH
$env:PYTHONPATH = $PWD

# Clear screen
Clear-Host

Write-Host "TradingView Proxy Server" -ForegroundColor Cyan
Write-Host "======================"
Write-Host "Starting proxy server..."
Write-Host "Listening for trades..."
Write-Host "Press Ctrl+C to stop`n"

try {
    # Start mitmproxy with filter as last argument
    mitmdump `
        --listen-host 127.0.0.1 `
        --listen-port 8080 `
        --mode regular `
        --ssl-insecure `
        --flow-detail 3 `
        -s src/main.py `
        '~u "orders\?locale=\w+&requestId=\w+" | ~u "executions\?locale=\w+&instrument=\w+"'
}
catch {
    Write-Host "`nError: $_" -ForegroundColor Red
}
finally {
    Write-Host "`nProxy server stopped." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
}