# How to Get Missing API Keys

## Current Status
Based on your server logs, you currently have:
- ✅ **Helius API** - Configured (for Solana)
- ✅ **Magic Eden API** - Configured (for Solana marketplace)
- ✅ **Reservoir API** - Configured (for EVM marketplace)
- ❌ **Alchemy API** - Missing (for EVM chains: Ethereum, Polygon, Arbitrum, Optimism, Base)
- ❌ **Moralis API** - Missing (for EVM chains backup)

## Required API Keys

### 1. Alchemy API Key (HIGH PRIORITY - For EVM Chains)
**Why you need it:** Primary data source for Ethereum, Polygon, Arbitrum, Optimism, and Base chains.

**How to get it:**
1. Go to https://www.alchemy.com/
2. Click "Sign Up" or "Log In"
3. Create a free account
4. Go to Dashboard → Create App
5. Select your chain (Ethereum, Polygon, etc.)
6. Select "Mainnet" network
7. Copy your API Key from the app dashboard
8. **Free tier:** 300M compute units/month (plenty for NFT scraping)

**Add to .env:**
```
ALCHEMY_API_KEY=your_alchemy_api_key_here
```

**For multiple chains, you can use the same key or add multiple keys (comma-separated):**
```
ALCHEMY_API_KEY=key1,key2,key3
```

---

### 2. Moralis API Key (OPTIONAL - Backup for EVM Chains)
**Why you need it:** Backup data source when Alchemy is unavailable or rate-limited.

**How to get it:**
1. Go to https://moralis.io/
2. Click "Sign Up" or "Log In"
3. Create a free account
4. Go to Dashboard → API Keys
5. Copy your API Key
6. **Free tier:** 40,000 requests/month

**Add to .env:**
```
MORALIS_API_KEY=your_moralis_api_key_here
```

---

### 3. QuickNode API Key (OPTIONAL - Advanced)
**Why you need it:** Additional RPC provider for better reliability.

**How to get it:**
1. Go to https://www.quicknode.com/
2. Sign up for free account
3. Create an endpoint
4. Copy your API key
5. **Free tier:** Limited requests

**Add to .env:**
```
QUICKNODE_API_KEY=your_quicknode_api_key_here
```

---

## Optional API Keys (Already Working, but can be enhanced)

### 4. Magic Eden Public API Key (OPTIONAL)
**Current status:** Working without API key, but rate-limited.

**How to get it (if you need higher limits):**
1. Go to https://www.magiceden.io/
2. Contact their API team or check their docs
3. **Note:** Public API works without key for basic usage

**Add to .env (optional):**
```
MAGICEDEN_PUBLIC_API_KEY=your_magiceden_key_here
# OR
MAGICEDEN_API_KEY=your_magiceden_key_here
```

---

### 5. Reservoir API Key (OPTIONAL)
**Current status:** Working without API key on free tier.

**How to get it (if you need higher limits):**
1. Go to https://reservoir.tools/
2. Sign up for API access
3. Get your API key from dashboard
4. **Free tier:** Available without key

**Add to .env (optional):**
```
RESERVOIR_API_KEY=your_reservoir_api_key_here
```

---

## How to Add API Keys to Your Project

### Step 1: Open your `.env` file
The `.env` file is in the root directory of your project.

### Step 2: Add your API keys
Add the keys in this format:
```env
# Required for EVM chains (Ethereum, Polygon, etc.)
ALCHEMY_API_KEY=your_alchemy_key_here

# Optional backup for EVM chains
MORALIS_API_KEY=your_moralis_key_here

# Already configured (Solana)
HELIUS_API_KEY=your_helius_key_here

# Optional - for higher rate limits
MAGICEDEN_PUBLIC_API_KEY=your_magiceden_key_here
RESERVOIR_API_KEY=your_reservoir_key_here
QUICKNODE_API_KEY=your_quicknode_key_here
```

### Step 3: Restart your server
After adding the keys, restart the web server for changes to take effect.

---

## Priority Order

### Must Have (for full functionality):
1. **Alchemy API Key** - Essential for scraping EVM chains (Ethereum, Polygon, etc.)

### Nice to Have:
2. **Moralis API Key** - Backup for EVM chains
3. **Magic Eden Public API Key** - Higher rate limits for Solana marketplace data
4. **Reservoir API Key** - Higher rate limits for EVM marketplace data

### Optional:
5. **QuickNode API Key** - Additional RPC provider

---

## Quick Links

- **Alchemy:** https://www.alchemy.com/ → Sign Up → Dashboard
- **Moralis:** https://moralis.io/ → Sign Up → API Keys
- **QuickNode:** https://www.quicknode.com/ → Sign Up → Endpoints
- **Magic Eden API Docs:** https://docs.magiceden.io/
- **Reservoir API Docs:** https://docs.reservoir.tools/

---

## Testing Your API Keys

After adding your keys, you can test them by:
1. Restarting the server
2. Checking the server logs - you should see:
   - ✅ "Alchemy client initialized" (if Alchemy key is added)
   - ✅ "Moralis client initialized" (if Moralis key is added)
3. Try scraping a collection from an EVM chain (Ethereum, Polygon, etc.)

---

## Need Help?

If you encounter issues:
1. Make sure there are no spaces around the `=` sign in `.env`
2. Don't use quotes around the API key values
3. Restart the server after making changes
4. Check server logs for initialization messages

