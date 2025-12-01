#!/bin/bash
# Build and run Docker container for NFT Scraper

echo "🐳 Building NFT Scraper Docker image..."
docker build -t nft-scraper:latest .

echo "✅ Build complete!"
echo ""
echo "To run the container:"
echo "  docker run -p 8080:8080 --env-file .env nft-scraper:latest"
echo ""
echo "Or use docker-compose:"
echo "  docker-compose up -d"



