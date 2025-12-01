# How to Get Webhook Secret and Reservoir API Key

## 1. Webhook Secret

### What is a Webhook Secret?
A webhook secret is a security token used to verify that incoming webhook requests are authentic and come from the expected service (Alchemy, Moralis, Helius, etc.). It's used to prevent unauthorized webhook calls.

### How to Get Webhook Secrets

#### Option A: Generate Your Own Secret (Recommended)
You can generate your own webhook secret - it's just a random string that you'll use to verify webhooks.

**Generate a secure secret:**
```bash
# On Windows PowerShell:
[Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes([System.Guid]::NewGuid().ToString() + [System.Guid]::NewGuid().ToString()))

# Or use an online generator:
# https://www.random.org/strings/
# Generate a 32+ character random string
```

**Or use Python:**
```python
import secrets
print(secrets.token_urlsafe(32))
```

#### Option B: Get from Service Providers

**Alchemy Webhook Secret:**
1. Go to https://dashboard.alchemy.com/
2. Sign in to your account
3. Go to **Webhooks** section
4. When creating a webhook, you'll set a secret
5. Copy the secret you set (or generate one)

**Moralis Webhook Secret:**
1. Go to https://admin.moralis.io/
2. Sign in to your account
3. Go to **Webhooks** section
4. When creating a webhook, you'll set a secret
5. Copy the secret you set

**Helius Webhook Secret:**
1. Go to https://dashboard.helius.dev/
2. Sign in to your account
3. Go to **Webhooks** section
4. When creating a webhook, you'll set a secret
5. Copy the secret you set

### Add to .env:
```env
WEBHOOK_SECRET=your_generated_secret_here
```

**Note:** The webhook secret is optional. Your webhook server will work without it, but it's recommended for security.

---

## 2. Reservoir API Key

### What is Reservoir?
Reservoir is a decentralized NFT liquidity protocol that provides marketplace data for EVM chains (Ethereum, Polygon, Base, etc.). Your scraper uses it to get marketplace statistics like floor price, volume, sales, etc.

### Current Status
✅ **Reservoir works WITHOUT an API key** - You can use it for free with rate limits.

❌ **With an API key** - You get higher rate limits and better performance.

### How to Get Reservoir API Key

#### Step 1: Visit Reservoir
Go to: **https://reservoir.tools/**

#### Step 2: Sign Up / Log In
1. Click **"Sign Up"** or **"Log In"** in the top right
2. Create an account (or log in if you have one)
3. You can use GitHub, Google, or email to sign up

#### Step 3: Access Developer Dashboard
1. Once logged in, look for **"Developers"** or **"API"** section
2. Navigate to **"API Keys"** or **"Developer Dashboard"**

#### Step 4: Generate API Key
1. Click **"Create API Key"** or **"Generate New Key"**
2. Give it a name (e.g., "NFT Scraper")
3. Copy the API key immediately (you might not be able to see it again)

#### Alternative: Check Documentation
- **Reservoir Docs:** https://docs.reservoir.tools/
- **API Reference:** https://docs.reservoir.tools/reference/overview
- **Support:** Check their Discord or GitHub for API access

### Add to .env:
```env
RESERVOIR_API_KEY=your_reservoir_api_key_here
```

---

## Quick Setup Guide

### Step 1: Generate Webhook Secret
```bash
# Use Python (if you have it):
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Or use online generator:
# https://www.random.org/strings/
# Generate: 32+ characters, alphanumeric
```

### Step 2: Get Reservoir API Key
1. Visit: https://reservoir.tools/
2. Sign up / Log in
3. Go to Developer Dashboard → API Keys
4. Generate new key
5. Copy the key

### Step 3: Update .env File
Open your `.env` file and add:

```env
# Webhook Secret (generate your own)
WEBHOOK_SECRET=your_generated_secret_here

# Reservoir API Key (optional but recommended)
RESERVOIR_API_KEY=your_reservoir_api_key_here
```

### Step 4: Restart Your Server
After adding the keys, restart your webhook server:

```bash
python main.py serve-webhooks --port 8000
```

---

## Verification

### Check if Webhook Secret is Working:
1. Start your webhook server
2. Check logs - you should see webhook endpoints available
3. Test with a webhook call (if you have webhooks set up)

### Check if Reservoir API Key is Working:
1. Restart your scraper
2. Check server logs - you should see:
   - ✅ "Reservoir client initialized" (if key is set)
   - ⚠️ "Reservoir client not available" (if key is missing - but it still works without key)

3. Try scraping an EVM collection (Ethereum, Polygon, etc.)
4. Check if marketplace data (floor price, volume) is being fetched

---

## Important Notes

### Webhook Secret:
- ✅ **Optional** - Your webhooks will work without it
- ✅ **Recommended** - For security and verification
- ✅ **You generate it** - It's your own secret, not provided by services
- ✅ **Use same secret** - Use the same secret when configuring webhooks in Alchemy/Moralis/Helius

### Reservoir API Key:
- ✅ **Optional** - Works without key (free tier)
- ✅ **Recommended** - For higher rate limits
- ✅ **Free tier available** - No payment required
- ✅ **Better performance** - With key, you get more requests per minute

---

## Troubleshooting

### Webhook Secret Issues:
- **Problem:** Webhooks not verifying
- **Solution:** Make sure you use the same secret in your .env and when configuring webhooks in service providers

### Reservoir API Key Issues:
- **Problem:** Can't find where to get API key
- **Solution:** 
  1. Check Reservoir Discord: https://discord.gg/reservoir
  2. Check GitHub: https://github.com/reservoirprotocol
  3. Contact their support
  4. **Note:** You can use Reservoir without a key - it works fine!

- **Problem:** Rate limited
- **Solution:** Get an API key for higher limits, or wait a bit between requests

---

## Quick Links

- **Reservoir Website:** https://reservoir.tools/
- **Reservoir Docs:** https://docs.reservoir.tools/
- **Reservoir Discord:** https://discord.gg/reservoir
- **Reservoir GitHub:** https://github.com/reservoirprotocol

- **Alchemy Dashboard:** https://dashboard.alchemy.com/
- **Moralis Dashboard:** https://admin.moralis.io/
- **Helius Dashboard:** https://dashboard.helius.dev/

---

## Summary

1. **Webhook Secret:** Generate your own random string (32+ characters)
2. **Reservoir API Key:** Sign up at reservoir.tools → Developer Dashboard → Generate API Key
3. **Both are optional** but recommended for better security and performance
4. **Add both to .env** file
5. **Restart server** after adding

Your scraper will work fine without these, but having them improves security and performance!

