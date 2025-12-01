# NFT Scout Startup Script for Windows
# PowerShell script to set up and run the NFT Scout application

Write-Host "🎨 Starting NFT Scout..." -ForegroundColor Cyan

# Check if Python is installed
$pythonCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $pythonCmd = "python3"
} else {
    Write-Host "❌ Python is not installed. Please install Python 3.11+ first." -ForegroundColor Red
    Write-Host "Download from: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# Check Python version
$pythonVersion = & $pythonCmd --version 2>&1
Write-Host "✅ Found $pythonVersion" -ForegroundColor Green

# Check if virtual environment exists
if (-Not (Test-Path "venv")) {
    Write-Host "📦 Creating virtual environment..." -ForegroundColor Yellow
    & $pythonCmd -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
}

# Activate virtual environment
Write-Host "🔌 Activating virtual environment..." -ForegroundColor Yellow
& "venv\Scripts\Activate.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to activate virtual environment" -ForegroundColor Red
    exit 1
}

# Use venv's Python after activation
$venvPython = "venv\Scripts\python.exe"
if (-Not (Test-Path $venvPython)) {
    Write-Host "❌ Virtual environment Python not found" -ForegroundColor Red
    exit 1
}

# Upgrade pip
Write-Host "📥 Upgrading pip..." -ForegroundColor Yellow
& $venvPython -m pip install --upgrade pip --quiet

# Install dependencies
Write-Host "📥 Installing dependencies..." -ForegroundColor Yellow
& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to install dependencies" -ForegroundColor Red
    exit 1
}

# Create .env if it doesn't exist
if (-Not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Write-Host "📝 Creating .env file from .env.example..." -ForegroundColor Yellow
        Copy-Item ".env.example" ".env"
        Write-Host "✅ Created .env file. Please edit it with your API keys." -ForegroundColor Green
    } else {
        Write-Host "⚠️  No .env file found. You may need to create one with your API keys." -ForegroundColor Yellow
    }
}

# Start the web server
Write-Host ""
Write-Host "🚀 Starting web server on http://localhost:8080" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor DarkGray
Write-Host ""
& $venvPython web_server.py

