# 🚀 Complete Setup Guide

## Quick Start (Windows)

1. **Run the startup script:**
   ```powershell
   .\start.ps1
   ```
   Or double-click `LAUNCH_SERVER.bat`

2. **Open your browser:**
   - Go to: **http://localhost:8080**
   - NOT: http://0.0.0.0:8080 (this won't work)

3. **Start scraping:**
   - Enter a collection URL
   - Click "Scrape"
   - Watch NFTs appear in real-time!

## API Keys Configuration

All API keys are already configured in your `.env` file:

- ✅ **Alchemy**: `RMVocen68S9Bu7CKRmVfu`
- ✅ **Moralis**: Configured
- ✅ **Helius**: Configured
- ✅ **QuickNode**: Configured
- ✅ **Magic Eden**: Configured

## Testing Your Setup

Run these commands to verify everything works:

```powershell
# Test all API keys
python test_api_keys.py

# Test Alchemy connection
python test_alchemy_connection.py
```

## Troubleshooting

### Server Won't Start

1. **Check Python is installed:**
   ```powershell
   python --version
   ```
   Should be Python 3.11+

2. **Check virtual environment:**
   ```powershell
   Test-Path venv\Scripts\python.exe
   ```
   If False, run `.\start.ps1` first

3. **Check port 8080:**
   ```powershell
   netstat -ano | findstr :8080
   ```
   If port is busy, stop other servers

### Can't Access Server

- ✅ Use: **http://localhost:8080**
- ❌ Don't use: http://0.0.0.0:8080

### Total Supply Not Showing

- Some collections don't have total supply data
- Check activity log for API responses
- The system tries multiple APIs automatically

## File Structure

**Keep these files:**
- `start.ps1` - Main startup script
- `LAUNCH_SERVER.bat` - Quick launch
- `web_server.py` - Web server
- `main.py` - CLI tool
- `README.md` - Main documentation
- `GET_API_KEYS.md` - API setup guide
- `QUICK_START.md` - Quick reference
- `test_api_keys.py` - Test script

**Deleted (old/duplicate):**
- ❌ `start.bat` - Replaced by `start.ps1`
- ❌ `run.bat` - Replaced by `LAUNCH_SERVER.bat`
- ❌ `MISSING_APIS.md` - Outdated info
- ❌ `test_setup.py` - Old test file

## Need Help?

1. Check `README.md` for full documentation
2. Check `GET_API_KEYS.md` for API setup
3. Check activity log in web UI for errors
4. Run test scripts to verify configuration

---

**Everything is configured and ready to use!** 🎉

