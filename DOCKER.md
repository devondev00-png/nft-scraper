# 🐳 Docker Deployment Guide

## Quick Start

### Build and Run with Docker Compose (Recommended)

```bash
docker-compose up -d
```

This will:
- Build the Docker image
- Start the container on port 8080
- Automatically restart if it crashes
- Load environment variables from `.env` file

### Access the Application

Open your browser and go to: **http://localhost:8080**

### Stop the Container

```bash
docker-compose down
```

## Manual Docker Commands

### Build the Image

```bash
# Windows
.\build-docker.ps1

# Linux/Mac
chmod +x build-docker.sh
./build-docker.sh

# Or manually
docker build -t nft-scraper:latest .
```

### Run the Container

```bash
docker run -d \
  --name nft-scraper \
  -p 8080:8080 \
  --env-file .env \
  nft-scraper:latest
```

### View Logs

```bash
docker logs -f nft-scraper
```

### Stop Container

```bash
docker stop nft-scraper
docker rm nft-scraper
```

## Environment Variables

Make sure your `.env` file contains all required API keys:

```env
ALCHEMY_API_KEY=your_key
MORALIS_API_KEY=your_key
HELIUS_API_KEY=your_key
QUICKNODE_API_KEY=your_key
MAGICEDEN_PUBLIC_API_KEY=your_key
RESERVOIR_API_KEY=your_key
```

## Production Deployment

### Using Docker Compose

1. Copy `.env` file to your server
2. Run `docker-compose up -d`
3. Set up reverse proxy (nginx/traefik) if needed

### Using Docker Swarm

```bash
docker stack deploy -c docker-compose.yml nft-scraper
```

### Health Checks

The container includes a health check that verifies the server is responding:

```bash
docker ps  # Check health status
```

## Troubleshooting

### Container Won't Start

1. Check logs: `docker logs nft-scraper`
2. Verify `.env` file exists and has correct format
3. Check port 8080 is not already in use

### API Keys Not Working

1. Verify `.env` file is mounted correctly
2. Check container logs for API errors
3. Ensure API keys are valid and have proper permissions

### Static Files Not Loading

The static files are copied into the image during build. If you need to update them:

1. Rebuild the image: `docker-compose build`
2. Restart: `docker-compose up -d`



