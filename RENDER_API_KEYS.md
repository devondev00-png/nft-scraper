# How to Add API Keys to Render

## ⚠️ IMPORTANT: API Keys Must Be Set in Render Dashboard

The API keys are **NOT** stored in code or GitHub. They must be added as **Environment Variables** in your Render dashboard.

## Step-by-Step Guide

### 1. Go to Your Render Dashboard
1. Visit: https://render.com/dashboard
2. Find your **nft-scraper** service
3. Click on it to open the service settings

### 2. Navigate to Environment Variables
1. In the left sidebar, click **"Environment"**
2. You'll see a section called **"Environment Variables"**

### 3. Add Your API Keys

Click **"Add Environment Variable"** for each key:

#### Required API Keys:

**1. Helius API Key (for Solana)**
- **Key:** `HELIUS_API_KEY`
- **Value:** Your Helius API key
- **Get it:** https://www.helius.dev/ → Dashboard → API Keys

**2. Alchemy API Key (for Ethereum, Polygon, Arbitrum, Base, etc.)**
- **Key:** `ALCHEMY_API_KEY`
- **Value:** Your Alchemy API key
- **Get it:** https://www.alchemy.com/ → Dashboard → Create App → Copy API Key

**3. Moralis API Key (optional backup for EVM chains)**
- **Key:** `MORALIS_API_KEY`
- **Value:** Your Moralis API key
- **Get it:** https://moralis.io/ → Dashboard → API Keys

### 4. Example Environment Variables

Add these in Render:

```
HELIUS_API_KEY=your_helius_key_here
ALCHEMY_API_KEY=your_alchemy_key_here
MORALIS_API_KEY=your_moralis_key_here
```

### 5. Save and Redeploy

1. After adding all keys, click **"Save Changes"**
2. Render will automatically redeploy your service
3. Wait for deployment to complete (usually 2-3 minutes)

### 6. Verify API Keys Are Working

After deployment, check your service logs:
- Go to **"Logs"** tab in Render
- You should see:
  - ✅ `Helius client initialized` (if Helius key is set)
  - ✅ `Alchemy client initialized` (if Alchemy key is set)
  - ✅ `Moralis client initialized` (if Moralis key is set)

If you see warnings like:
- ❌ `Helius client not available: Helius API keys not configured`
- ❌ `Alchemy client not available: Alchemy API keys not configured`

Then the keys are not set correctly. Double-check:
1. Key names are exactly correct (case-sensitive)
2. No extra spaces before/after the key or value
3. Keys are saved in Render dashboard

## Quick Links to Get API Keys

- **Helius (Solana):** https://www.helius.dev/ → Sign Up → Dashboard → API Keys
- **Alchemy (EVM chains):** https://www.alchemy.com/ → Sign Up → Dashboard → Create App
- **Moralis (EVM backup):** https://moralis.io/ → Sign Up → Dashboard → API Keys

## Security Note

✅ **DO:** Add API keys in Render dashboard (secure, encrypted)
❌ **DON'T:** Commit API keys to GitHub or add them to render.yaml

The `render.yaml` file does NOT contain actual API keys - it only defines the structure. Actual keys must be set in the Render dashboard.

