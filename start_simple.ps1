# Simple startup script that avoids venv activation issues
Write-Host "🎨 Starting NFT Scout..." -ForegroundColor Cyan

$ErrorActionPreference = "Continue"

# Check if Python is installed
if (-Not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Python is not installed. Please install Python 3.11+ first." -ForegroundColor Red
    Write-Host "Download from: https://www.python.org/downloads/" -ForegroundColor Yellow
    pause
    exit 1
}

$pythonVersion = python --version 2>&1
Write-Host "✅ Found $pythonVersion" -ForegroundColor Green

# Try to use venv Python if it exists, otherwise use system Python
$pythonExe = "python"
if (Test-Path "venv\Scripts\python.exe") {
    $pythonExe = "venv\Scripts\python.exe"
    Write-Host "✅ Using virtual environment Python" -ForegroundColor Green
} else {
    Write-Host "⚠️  Using system Python (venv not found)" -ForegroundColor Yellow
}

# Check if dependencies are installed
Write-Host "🔍 Checking dependencies..." -ForegroundColor Yellow
try {
    & $pythonExe -c "import fastapi, uvicorn" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Dependencies not installed"
    }
    Write-Host "✅ Dependencies OK" -ForegroundColor Green
} catch {
    Write-Host "📥 Installing dependencies..." -ForegroundColor Yellow
    & $pythonExe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to install dependencies" -ForegroundColor Red
        pause
        exit 1
    }
}

# Start the web server
Write-Host ""
Write-Host "🚀 Starting web server on http://localhost:8080" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor DarkGray
Write-Host ""

try {
    & $pythonExe web_server.py
} catch {
    Write-Host "❌ Error starting server: $_" -ForegroundColor Red
    pause
    exit 1
}

