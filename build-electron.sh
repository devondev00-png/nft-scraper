#!/bin/bash
# Build Electron app for NFT Scraper

echo "📦 Installing Electron dependencies..."
npm install

echo "🔨 Building Electron app..."
npm run build:all

echo "✅ Build complete! Check dist-electron/ folder"



