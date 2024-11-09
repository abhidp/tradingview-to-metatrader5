# Function to print banner
function Write-Banner {
    Clear-Host
    Write-Host "TradingView Proxy Server" -ForegroundColor Cyan
    Write-Host "======================"
    Write-Host "Starting proxy server..."
    Write-Host "Listening for trades..."
    Write-Host "Press Ctrl+C to stop`n"
}

# Function to cleanup processes
function Stop-ExistingProcesses {
    Write-Host "Checking for existing processes..." -ForegroundColor Yellow
    
    # Kill existing mitmproxy processes
    Get-Process | Where-Object { $_.ProcessName -like "*mitm*" } | ForEach-Object {
        Write-Host "Stopping process: $($_.ProcessName) (PID: $($_.Id))"
        Stop-Process -Id $_.Id -Force
    }

    # Free up port 8080
    $netstatOutput = netstat -ano | Select-String ":8080"
    $netstatOutput | ForEach-Object {
        $processId = ($_ -split ' +')[-1]
        Write-Host "Freeing port 8080 (PID: $processId)"
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
    Write-Host ""
}

# Main execution
try {
    # Initialize
    Stop-ExistingProcesses
    
    # Activate virtual environment
    & .\venv\Scripts\Activate.ps1
    $env:RUNNING_MODE = "proxy"
    # Set PYTHONPATH
    $env:PYTHONPATH = $PWD
    
    # Print banner
    Write-Banner
    
    # Start mitmproxy with minimal output
    $mitmArgs = @(
        "--quiet",
        "--listen-host", "127.0.0.1",
        "--listen-port", "8080",
        "--mode", "regular",
        "--ssl-insecure",
        "--set", "console_output_level=error",
        "--set", "flow_detail=0",
        "-s", "src/main.py",
        "~u orders\?locale=\w+&requestId=\w+ | ~u executions\?locale=\w+&instrument=\w+"
    )
    
    # Remove the banner from main.py output by setting an environment variable
    $env:HIDE_BANNER = "true"
    
    mitmdump $mitmArgs
}
catch {
    Write-Host "`nError: $_" -ForegroundColor Red
}
finally {
    Write-Host "`nProxy server stopped." -ForegroundColor Yellow
    Write-Host "Press Enter to exit: " -ForegroundColor Gray -NoNewline
    Read-Host
}