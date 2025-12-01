# Build and run Docker container for NFT Scraper (PowerShell)

Write-Host "🐳 Building NFT Scraper Docker image..." -ForegroundColor Cyan
docker build -t nft-scraper:latest .

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Build complete!" -ForegroundColor Green
    Write-Host ""
    Write-Host "To run the container:" -ForegroundColor Yellow
    Write-Host "  docker run -p 8080:8080 --env-file .env nft-scraper:latest" -ForegroundColor White
    Write-Host ""
    Write-Host "Or use docker-compose:" -ForegroundColor Yellow
    Write-Host "  docker-compose up -d" -ForegroundColor White
} else {
    Write-Host "❌ Build failed!" -ForegroundColor Red
    exit 1
}



