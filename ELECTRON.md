# 🖥️ Electron Desktop App Guide

## Development

### Install Dependencies

```bash
npm install
```

### Run in Development Mode

```bash
npm run electron:dev
```

This will:
- Start the Python server automatically
- Open the Electron window
- Load the web UI from localhost:8080

## Building Installers

### Windows

```bash
npm run build:win
```

Creates:
- `dist-electron/NFT Scraper Setup x.x.x.exe` - NSIS installer

### macOS

```bash
npm run build:mac
```

Creates:
- `dist-electron/NFT Scraper-x.x.x.dmg` - DMG installer

### Linux

```bash
npm run build:linux
```

Creates:
- `dist-electron/NFT Scraper-x.x.x.AppImage` - AppImage

### All Platforms

```bash
npm run build:all
```

## Using Build Scripts

### Windows

```powershell
.\build-electron.ps1
```

Interactive script that lets you choose the build target.

### Linux/Mac

```bash
chmod +x build-electron.sh
./build-electron.sh
```

## Requirements

### For Development

- Node.js 18+ and npm
- Python 3.11+ installed and in PATH
- All Python dependencies installed (run `pip install -r requirements.txt`)

### For Building

- Node.js 18+ and npm
- Electron Builder dependencies:
  - Windows: Requires Windows build tools
  - macOS: Requires Xcode (for signing)
  - Linux: Requires standard build tools

## How It Works

1. **Main Process** (`electron/main.js`):
   - Starts the Python web server automatically
   - Creates the Electron window
   - Manages the application lifecycle

2. **Preload Script** (`electron/preload.js`):
   - Provides secure bridge between web content and Node.js
   - Exposes limited Electron APIs to the renderer

3. **Web UI**:
   - Runs in the Electron renderer process
   - Connects to localhost:8080 (Python server)
   - Full functionality of the web version

## Distribution

### Windows

The NSIS installer can be distributed to users. They need:
- Windows 10/11
- Python 3.11+ installed (or bundle Python in the installer)

### macOS

The DMG can be distributed. Users need:
- macOS 10.15+
- May need to allow unsigned apps in Security settings

### Linux

The AppImage is portable and doesn't require installation. Users need:
- Linux distribution with AppImage support
- Execute permissions: `chmod +x NFT\ Scraper-x.x.x.AppImage`

## Troubleshooting

### Python Server Won't Start

1. Ensure Python is installed and in PATH
2. Check that all dependencies are installed: `pip install -r requirements.txt`
3. Verify `.env` file exists with API keys

### Build Fails

1. Clear node_modules: `rm -rf node_modules && npm install`
2. Clear Electron cache: `rm -rf ~/.cache/electron-builder`
3. Check Node.js version: `node --version` (should be 18+)

### App Won't Open

1. Check console for errors
2. Verify Python server is running on port 8080
3. Check firewall isn't blocking localhost:8080

## Future Improvements

- Bundle Python runtime in the Electron app
- Auto-update functionality
- System tray integration
- Offline mode support



