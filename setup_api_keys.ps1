# NFT Scraper API Keys Setup Script
# This script helps you get all required API keys

Write-Host "`n🚀 NFT Scraper API Keys Setup" -ForegroundColor Cyan
Write-Host "=" * 50 -ForegroundColor Cyan

# Check current .env status
Write-Host "`n📋 Current API Keys Status:" -ForegroundColor Yellow
if (Test-Path ".env") {
    $envContent = Get-Content .env
    
    $alchemy = $envContent | Select-String -Pattern "^ALCHEMY_API_KEY=(.+)$" | ForEach-Object { $_.Matches.Groups[1].Value }
    $moralis = $envContent | Select-String -Pattern "^MORALIS_API_KEY=(.+)$" | ForEach-Object { $_.Matches.Groups[1].Value }
    $helius = $envContent | Select-String -Pattern "^HELIUS_API_KEY=(.+)$" | ForEach-Object { $_.Matches.Groups[1].Value }
    $magiceden = $envContent | Select-String -Pattern "^MAGICEDEN" | Select-Object -First 1
    
    if ($alchemy -and $alchemy.Trim() -ne "") {
        Write-Host "  ✅ Alchemy API Key: Configured" -ForegroundColor Green
    } else {
        Write-Host "  ❌ Alchemy API Key: MISSING" -ForegroundColor Red
    }
    
    if ($moralis -and $moralis.Trim() -ne "") {
        Write-Host "  ✅ Moralis API Key: Configured" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  Moralis API Key: Optional (not configured)" -ForegroundColor Yellow
    }
    
    if ($helius -and $helius.Trim() -ne "") {
        Write-Host "  ✅ Helius API Key: Configured" -ForegroundColor Green
    } else {
        Write-Host "  ❌ Helius API Key: MISSING" -ForegroundColor Red
    }
    
    if ($magiceden) {
        Write-Host "  ✅ Magic Eden API Key: Configured" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  Magic Eden API Key: Optional (not configured)" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ❌ .env file not found!" -ForegroundColor Red
}

Write-Host "`n🌐 Opening API Provider Websites..." -ForegroundColor Cyan
Write-Host "  Please sign up and get your API keys, then come back here." -ForegroundColor Gray

# Open all signup pages
Write-Host "`n1️⃣ Opening Alchemy (FREE - Required for EVM chains)..." -ForegroundColor Yellow
Start-Sleep -Seconds 1
Start-Process "https://www.alchemy.com/"

Write-Host "2️⃣ Opening Moralis (FREE - Optional backup)..." -ForegroundColor Yellow
Start-Sleep -Seconds 1
Start-Process "https://moralis.io/"

Write-Host "`n📝 Instructions:" -ForegroundColor Cyan
Write-Host "  1. Sign up for Alchemy (free, no credit card)" -ForegroundColor White
Write-Host "  2. Create an app in Alchemy dashboard" -ForegroundColor White
Write-Host "  3. Copy your API key" -ForegroundColor White
Write-Host "  4. (Optional) Sign up for Moralis as backup" -ForegroundColor White
Write-Host "`n💡 After getting your keys, run this script again with -AddKeys parameter" -ForegroundColor Yellow
Write-Host "   Example: .\setup_api_keys.ps1 -AddKeys" -ForegroundColor Gray

# If -AddKeys parameter is provided, help add keys
if ($args -contains "-AddKeys" -or $args -contains "-addkeys") {
    Write-Host "`n🔑 Adding API Keys to .env file..." -ForegroundColor Cyan
    
    if (-not (Test-Path ".env")) {
        Write-Host "  Creating .env file..." -ForegroundColor Yellow
        New-Item -Path ".env" -ItemType File | Out-Null
    }
    
    $envContent = Get-Content .env -ErrorAction SilentlyContinue
    
    # Add Alchemy key
    Write-Host "`n1️⃣ Alchemy API Key:" -ForegroundColor Yellow
    $alchemyKey = Read-Host "  Enter your Alchemy API key (or press Enter to skip)"
    if ($alchemyKey -and $alchemyKey.Trim() -ne "") {
        if ($envContent -match "^ALCHEMY_API_KEY=") {
            $envContent = $envContent -replace "^ALCHEMY_API_KEY=.*", "ALCHEMY_API_KEY=$alchemyKey"
        } else {
            $envContent += "ALCHEMY_API_KEY=$alchemyKey"
        }
        Write-Host "  ✅ Alchemy key added!" -ForegroundColor Green
    }
    
    # Add Moralis key
    Write-Host "`n2️⃣ Moralis API Key (Optional):" -ForegroundColor Yellow
    $moralisKey = Read-Host "  Enter your Moralis API key (or press Enter to skip)"
    if ($moralisKey -and $moralisKey.Trim() -ne "") {
        if ($envContent -match "^MORALIS_API_KEY=") {
            $envContent = $envContent -replace "^MORALIS_API_KEY=.*", "MORALIS_API_KEY=$moralisKey"
        } else {
            $envContent += "MORALIS_API_KEY=$moralisKey"
        }
        Write-Host "  ✅ Moralis key added!" -ForegroundColor Green
    }
    
    # Save .env file
    $envContent | Set-Content .env
    Write-Host "`n✅ .env file updated!" -ForegroundColor Green
    Write-Host "`n🔄 Please restart your server for changes to take effect." -ForegroundColor Yellow
}

Write-Host "`n" -NoNewline

