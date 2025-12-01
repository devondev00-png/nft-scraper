# 🚀 Quick Start Guide - Get All API Keys Running

## Current Status
- ✅ **Helius API** - Configured (Solana)
- ✅ **Magic Eden API** - Configured (Solana marketplace)
- ❌ **Alchemy API** - MISSING (Required for EVM chains)
- ⚠️  **Moralis API** - Optional (not configured)

## ⚡ Quick Setup (5 minutes)

### Step 1: Get Alchemy API Key (REQUIRED - 2 minutes)
1. **Website is already open in your browser** (opened by setup script)
2. Click **"Sign Up"** (top right)
3. Enter your email and create password
4. Verify your email
5. Click **"Create App"** button
6. Select:
   - **Chain:** Ethereum (or Polygon, Arbitrum, etc.)
   - **Network:** Mainnet
7. Click **"Create"**
8. **Copy your API Key** (it looks like: `abc123def456...`)

### Step 2: Add Alchemy Key to Your Project
Run this command:
```powershell
.\setup_api_keys.ps1 -AddKeys
```

Then paste your Alchemy API key when prompted.

**OR** manually edit `.env` file:
```
ALCHEMY_API_KEY=your_alchemy_key_here
```

### Step 3: (Optional) Get Moralis API Key
1. **Website is already open** (opened by setup script)
2. Click **"Sign Up"**
3. Create account
4. Go to **Dashboard → API Keys**
5. Copy your API key
6. Add to `.env`:
```
MORALIS_API_KEY=your_moralis_key_here
```

### Step 4: Test Your Setup
```powershell
venv\Scripts\python.exe test_api_keys.py
```

### Step 5: Restart Server
```powershell
# Stop current server (Ctrl+C if running)
venv\Scripts\python.exe web_server.py
```

## ✅ Verification

After adding keys, you should see:
- ✅ Alchemy client initialized
- ✅ All required API keys configured
- Server running on http://localhost:8080

## 🆘 Need Help?

1. **Can't find API key?**
   - Alchemy: Dashboard → Your App → View Key
   - Moralis: Dashboard → API Keys

2. **Key not working?**
   - Make sure no spaces around `=` in `.env`
   - Don't use quotes around the key
   - Restart server after adding keys

3. **Test your keys:**
   ```powershell
   venv\Scripts\python.exe test_api_keys.py
   ```

## 📝 Files Created

- `setup_api_keys.ps1` - Interactive setup script
- `test_api_keys.py` - Test your API keys
- `GET_API_KEYS.md` - Detailed instructions
- `FREE_API_ALTERNATIVES.md` - Free API options

## 🎯 What You Get

Once configured, you'll be able to scrape:
- ✅ **Ethereum** NFTs (via Alchemy)
- ✅ **Polygon** NFTs (via Alchemy)
- ✅ **Arbitrum** NFTs (via Alchemy)
- ✅ **Optimism** NFTs (via Alchemy)
- ✅ **Base** NFTs (via Alchemy)
- ✅ **Solana** NFTs (via Helius - already working!)
- ✅ **Marketplace data** (via Reservoir & Magic Eden - already working!)

---

**All APIs are FREE - No credit card required!** 🎉

