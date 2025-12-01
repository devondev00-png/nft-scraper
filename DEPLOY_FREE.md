# 🚀 Free Deployment Guide - NFT Scraper

Deploy your scraper to a **FREE** hosting service!

---

## 🎯 Recommended: Render.com (Easiest & Free)

### Step 1: Create Account
1. Go to https://render.com
2. Sign up (free tier available)
3. Connect your GitHub account

### Step 2: Deploy
1. Click **"New"** → **"Web Service"**
2. Connect your GitHub repository
3. Select the repository with your scraper
4. Settings:
   - **Name**: `nft-scraper` (or any name)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn web_server:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Free (512 MB RAM)
5. Click **"Create Web Service"**

### Step 3: Get Your URL
- Render will give you a URL like: `https://nft-scraper.onrender.com`
- **Note**: Free tier spins down after 15 minutes of inactivity (first request may be slow)

---

## 🚂 Alternative: Railway.app (Also Free)

### Step 1: Create Account
1. Go to https://railway.app
2. Sign up with GitHub
3. Get $5 free credit (enough for months)

### Step 2: Deploy
1. Click **"New Project"**
2. Select **"Deploy from GitHub repo"**
3. Select your scraper repository
4. Railway auto-detects Python and deploys
5. Get your URL: `https://your-app.railway.app`

---

## 🔧 Update Paywall to Use Scraper URL

After deployment, update the paywall:

### 1. Update `app.js` in paywall:

```javascript
const scraperUrl = isMobileApp 
  ? 'https://your-scraper-url.onrender.com' // Your deployed URL
  : 'http://localhost:8000';
```

### 2. Update `capacitor.config.json`:

```json
"allowNavigation": [
  "https://your-scraper-url.onrender.com"
]
```

---

## 📋 Quick Deploy Commands

### Render.com
1. Push code to GitHub
2. Connect to Render
3. Deploy!

### Railway.app
1. Push code to GitHub
2. Connect to Railway
3. Deploy!

---

## ✅ What You Get

- ✅ Free hosting
- ✅ HTTPS URL
- ✅ Auto-deploy from GitHub
- ✅ Environment variables support
- ✅ Logs and monitoring

---

## 🎯 Recommended Setup

**Use Render.com** - It's the easiest:
- Free tier available
- Simple setup
- Auto-deploys from GitHub
- HTTPS included

**Your scraper will be at:**
`https://your-app-name.onrender.com`

---

## 📝 Environment Variables (Optional)

If you need API keys, add them in Render/Railway dashboard:
- `ALCHEMY_API_KEY`
- `HELIUS_API_KEY`
- etc.

---

**Ready to deploy!** 🚀

