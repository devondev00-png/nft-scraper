# Build Electron app for NFT Scraper (PowerShell)

Write-Host "📦 Installing Electron dependencies..." -ForegroundColor Cyan
npm install

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ npm install failed!" -ForegroundColor Red
    exit 1
}

Write-Host "🔨 Building Electron app..." -ForegroundColor Cyan
Write-Host "Choose build target:" -ForegroundColor Yellow
Write-Host "  1. Windows (npm run build:win)" -ForegroundColor White
Write-Host "  2. macOS (npm run build:mac)" -ForegroundColor White
Write-Host "  3. Linux (npm run build:linux)" -ForegroundColor White
Write-Host "  4. All platforms (npm run build:all)" -ForegroundColor White

$choice = Read-Host "Enter choice (1-4)"

switch ($choice) {
    "1" { npm run build:win }
    "2" { npm run build:mac }
    "3" { npm run build:linux }
    "4" { npm run build:all }
    default { 
        Write-Host "Invalid choice. Building for Windows..." -ForegroundColor Yellow
        npm run build:win
    }
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Build complete! Check dist-electron/ folder" -ForegroundColor Green
} else {
    Write-Host "❌ Build failed!" -ForegroundColor Red
    exit 1
}



