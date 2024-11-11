Write-Host "Starting MT5 Worker..." -ForegroundColor Green

# Activate virtual environment
& .\venv\Scripts\Activate.ps1

# Set PYTHONPATH
$env:PYTHONPATH = $PWD

# Clear screen
Clear-Host

Write-Host "MT5 Trade Worker" -ForegroundColor Cyan
Write-Host "==============="
Write-Host "Starting worker..."
Write-Host "Press Ctrl+C to stop`n"

try {
    # Start the worker
    python src/start_worker.py
}
catch {
    Write-Host "`nError: $_" -ForegroundColor Red
}
finally {
    Write-Host "`nWorker stopped." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
}