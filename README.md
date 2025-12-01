# 🎨 NFT Scout - Multi-Chain NFT Scraper

A production-ready, multi-chain NFT data scraper with real-time web UI and live scraping capabilities.

## ✨ Features

- ✅ **Multi-Chain Support**: Ethereum, Polygon, Arbitrum, Optimism, Base, and Solana
- ✅ **Multiple API Providers**: Alchemy, Moralis, Helius, QuickNode, Magic Eden, Reservoir
- ✅ **Real-Time Web UI**: Live scraping with WebSocket updates
- ✅ **Live NFT Display**: Watch NFTs appear in real-time as they're scraped
- ✅ **Collection Stats**: Floor price, volume, owners, market cap
- ✅ **Normalized Data Models**: Consistent Pydantic models across all chains
- ✅ **Smart Caching**: In-memory or Redis caching with TTL
- ✅ **Rate Limiting**: Automatic rate limit handling with key rotation
- ✅ **Retry Logic**: Exponential backoff with tenacity
- ✅ **CLI Tool**: Command-line interface for batch operations
- 🐳 **Docker Support**: Containerized deployment ready
- 🖥️ **Electron App**: Cross-platform desktop application

## 🚀 Quick Start

### Option 1: Docker (Recommended for Production)

**Build and Run with Docker Compose:**
```bash
docker-compose up -d
```

**Or build manually:**
```bash
# Windows
.\build-docker.ps1

# Linux/Mac
chmod +x build-docker.sh
./build-docker.sh

# Then run
docker run -p 8080:8080 --env-file .env nft-scraper:latest
```

Access at: `http://localhost:8080`

### Option 2: Electron Desktop App

**Build Electron App:**
```bash
# Windows
.\build-electron.ps1

# Linux/Mac
chmod +x build-electron.sh
./build-electron.sh
```

**Run in Development:**
```bash
npm install
npm run electron:dev
```

**Build Installers:**
```bash
npm run build:win    # Windows
npm run build:mac    # macOS
npm run build:linux  # Linux
npm run build:all    # All platforms
```

### Option 3: Local Development

**Windows (Recommended)**
```powershell
.\start.ps1
```

**Or use Batch File:**
```batch
LAUNCH_SERVER.bat
```

### Linux/Mac

```bash
chmod +x start.sh
./start.sh
```

### Manual Start

```bash
# Activate virtual environment
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Start server
python web_server.py
```

Then open **http://localhost:8080** in your browser.

## 📋 API Configuration

All API keys are configured in the `.env` file. The following APIs are currently set up:

- ✅ **Alchemy** - EVM chains (Ethereum, Polygon, Arbitrum, Optimism, Base)
- ✅ **Moralis** - EVM chains backup
- ✅ **Helius** - Solana (primary)
- ✅ **QuickNode** - Solana fallback
- ✅ **Magic Eden** - Solana marketplace data
- ✅ **Reservoir** - EVM marketplace data

See `GET_API_KEYS.md` for detailed API key setup instructions.

## 🎯 Usage

### Web UI

1. **Enter Collection URL**: 
   - OpenSea: `https://opensea.io/collection/collection-name`
   - Magic Eden: `https://magiceden.io/marketplace/collection-name`
   - Direct address: `0x...` (Ethereum) or base58 address (Solana)

2. **Click "Scrape"**: The system will:
   - Detect the collection
   - Fetch collection info (total supply, floor price, etc.)
   - Show confirmation modal
   - Start live scraping

3. **Watch Real-Time**: NFTs appear live with:
   - Images
   - Names and token IDs
   - Collection information
   - Progress tracking (X/Y format)

### CLI Usage

```bash
# Get NFTs owned by a wallet
python main.py wallet 0x... --chains ethereum,polygon,solana

# Get all NFTs in a collection
python main.py collection 0x... --chain ethereum

# Get collection statistics
python main.py stats 0x... --chain ethereum

# Start webhook server
python main.py serve-webhooks --port 8000
```

## 🔧 Configuration

### Environment Variables (.env)

```env
# Required APIs
ALCHEMY_API_KEY=your_key_here
MORALIS_API_KEY=your_key_here
HELIUS_API_KEY=your_key_here

# Optional APIs
QUICKNODE_API_KEY=your_key_here
MAGICEDEN_PUBLIC_API_KEY=your_key_here
RESERVOIR_API_KEY=your_key_here

# Settings
CACHE_TTL=900
CACHE_TYPE=memory
MAX_WORKERS=20
BATCH_SIZE=1000
```

### Supported Chains

- **Ethereum**: Alchemy (primary), Moralis (fallback)
- **Polygon**: Alchemy (primary), Moralis (fallback)
- **Arbitrum**: Alchemy (primary), Moralis (fallback)
- **Optimism**: Alchemy (primary), Moralis (fallback)
- **Base**: Alchemy (primary), Moralis (fallback)
- **Solana**: Helius (primary), QuickNode (fallback)

## 📁 Project Structure

```
nft-scout/
├── src/nft_scout/          # Core scraper library
│   ├── clients/            # API clients (Alchemy, Moralis, Helius, etc.)
│   ├── storage/            # Caching adapters
│   └── webhooks/           # Webhook endpoints
├── ui/                     # Web UI
│   └── index.html          # Main interface
├── static/                 # Static assets
├── main.py                 # CLI entrypoint
├── web_server.py           # Web UI server
├── start.ps1               # Windows startup script
├── LAUNCH_SERVER.bat       # Quick launch script
└── requirements.txt        # Dependencies
```

## 🐍 Python API Usage

```python
from src.nft_scout import NFTScout, Chain

scout = NFTScout()

# Get wallet NFTs
response = await scout.get_wallet_nfts(
    "0x...",
    [Chain.ETHEREUM, Chain.SOLANA]
)

# Get collection NFTs
response = await scout.get_collection_nfts(
    "0x...",
    Chain.ETHEREUM
)

# Get collection stats
stats = await scout.get_collection_stats(
    "0x...",
    Chain.ETHEREUM
)
```

## 📚 Documentation

- **GET_API_KEYS.md** - How to get and configure API keys
- **FREE_API_ALTERNATIVES.md** - Free API options and alternatives
- **QUICK_START.md** - Quick setup guide
- **ACCESS_SERVER.md** - How to access the web server

## 🔍 Troubleshooting

### Server Not Starting

1. Check if port 8080 is available
2. Verify virtual environment is activated
3. Check `.env` file exists and has API keys
4. Run `python test_api_keys.py` to verify configuration

### Total Supply Not Showing

- The system tries multiple APIs to get total supply
- Some collections may not have this data available
- Check activity log for detailed API responses

### Collection URL Issues

- Make sure URL is complete and valid
- For Solana, use full collection address (not Magic Eden symbol)
- For EVM, use contract address or OpenSea URL

## 🛠️ Development

### Testing

```bash
# Test API keys
python test_api_keys.py

# Test Alchemy connection
python test_alchemy_connection.py
```

### Requirements

- Python 3.11+
- All dependencies in `requirements.txt`
- API keys in `.env` file

## 📝 License

MIT

## 🤝 Contributing

Contributions welcome! Please open an issue or PR.

---

**Made with ❤️ for the NFT community**
