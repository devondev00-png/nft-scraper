# 🚀 Quick Deploy to FREE Server - 5 Minutes!

## ✅ Easiest: Render.com (Recommended)

### Step 1: Push to GitHub
```bash
# If not already on GitHub:
git init
git add .
git commit -m "Initial commit"
git remote add origin YOUR_GITHUB_REPO_URL
git push -u origin main
```

### Step 2: Deploy on Render
1. Go to **https://render.com**
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub account
4. Select your scraper repository
5. Settings:
   - **Name**: `nft-scraper` (or any name)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn web_server:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: **Free** (512 MB RAM)
6. Click **"Create Web Service"**

### Step 3: Get Your URL
- Render gives you: `https://nft-scraper.onrender.com` (or similar)
- **Copy this URL!**

### Step 4: Update Paywall
Update `public/app.js` in paywall project:
```javascript
const scraperUrl = 'https://nft-scraper.onrender.com'; // Your Render URL
```

---

## 🎯 That's It!

Your scraper is now live at: `https://your-app.onrender.com`

**Note**: Free tier spins down after 15 min inactivity (first request may be slow)

---

## 📱 Update Mobile Apps

After deployment, update the paywall mobile apps with the scraper URL!

