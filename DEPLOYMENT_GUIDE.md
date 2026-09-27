# 🚀 ARIA Deployment Guide

## Quick Start

Your ARIA app has **TWO separate parts** that need to be deployed:

1. **Frontend (Next.js)** → Deploy to Vercel
2. **Backend (FastAPI Python)** → Deploy to Railway/Render/Fly.io

You **CANNOT** deploy the Python backend to Vercel. Follow this guide step-by-step.

---

## Step 1: Deploy Backend (Python FastAPI)

⚠️ **Important**: Your app uses data science libraries (pandas, numpy, mesa) which need **~1-2GB RAM**. Render's free tier (512MB) won't work.

### Option A: Railway (⭐ RECOMMENDED)

**Why Railway:**
- ✅ Gives you **8GB RAM** on free tier (more than enough)
- ✅ $5 free credit per month (enough for ~500 hours)
- ✅ Easiest setup (auto-detects Python)
- ✅ Great for data science apps

**Steps:**

1. **Sign up at [railway.app](https://railway.app)**

2. **Create New Project**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Connect your GitHub account
   - Select your ARIA repository

3. **Configure Build**
   - Railway will auto-detect Python
   - Add environment variables (see list below)
   - Set start command: `python start_api.py`

4. **Add Environment Variables** (Settings → Variables):
   ```
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_service_role_key
   SUPABASE_ANON_KEY=your_anon_key
   SUPABASE_JWT_SECRET=your_jwt_secret
   ILMU_API_KEY=your_ilmu_key
   ILMU_BASE_URL=https://api.ilmu.ai/v1
   ILMU_MODEL=nemo-super
   ENVIRONMENT=production
   DEBUG=false
   APP_URL=https://your-vercel-app.vercel.app
   TRUSTED_PROXY_IPS=<comma-separated CIDRs for the backend's trusted ingress proxies>
   ```

   `TRUSTED_PROXY_IPS` is optional for direct/local access. For a proxied production
   deployment, configure it with the exact proxy addresses or CIDRs used by the
   backend host. The API ignores `X-Forwarded-For` unless the direct connection
   peer matches this allowlist. Do not use `*` or a broad network range.

5. **Generate Domain**
   - Railway will give you a URL like: `https://aria-production.up.railway.app`
   - **Copy this URL** - you'll need it for frontend

6. **Test Backend**
   - Visit: `https://your-railway-url.up.railway.app/api/health`
   - Should return: `{"status": "healthy", ...}`

### Option B: Render.com (⚠️ NOT FREE)

**Why NOT free tier:**
- ❌ Free tier = 512MB RAM (NOT enough for your app)
- ❌ Your app needs ~1-2GB RAM (pandas, numpy, mesa)
- ✅ Starter plan = $7/month (1GB RAM) - might work but tight

**If you want to use Render, you need the $7/month plan:**

1. Go to [render.com](https://render.com)
2. New → Web Service
3. Connect GitHub repo
4. Select **Starter ($7/month)** or higher
5. Settings:
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python start_api.py`
6. Add environment variables (same as Railway)

### Option C: Fly.io (Complex but Flexible)

**Pros:**
- Generous free tier (3 shared-cpu-1x machines)
- Pay only for what you use beyond that

**Cons:**
- More complex setup
- Requires Dockerfile

**Steps:**

1. Install Fly CLI: `npm install -g flyctl`
2. Login: `fly auth login`
3. Create app: `fly launch`
4. Set secrets: `fly secrets set KEY=value`
5. Deploy: `fly deploy`

### Option D: PythonAnywhere (Not Recommended)

- Free tier is very limited
- Doesn't support FastAPI well
- Better for Flask apps

### 💰 Cost Comparison

| Platform | Free Tier RAM | Cost | Best For |
|----------|---------------|------|----------|
| **Railway** | 8GB | $5 credit → ~500 hours free | ⭐ Your app |
| Render Free | 512MB | Free | ❌ Too small |
| Render Starter | 1GB | $7/month | Your app (tight) |
| Fly.io | 256MB × 3 | Free → Pay | Advanced users |
| Heroku | 512MB | $7/month | Simple apps |

**Recommendation: Use Railway** - Best free tier for data science apps.

---

## Step 2: Update Backend for Production

Your backend has been automatically updated with:
- ✅ Dynamic CORS based on environment
- ✅ Reload disabled in production
- ✅ Proper logging instead of print statements
- ✅ Environment-aware configuration

Make sure your `.env` on the backend server has:
```bash
ENVIRONMENT=production
DEBUG=false
APP_URL=https://your-frontend.vercel.app
```

---

## Step 3: Deploy Frontend (Next.js to Vercel)

### 3.1: Configure Environment Variables

1. **Go to [vercel.com](https://vercel.com)**

2. **Import Project** from GitHub

3. **Add Environment Variables** (Settings → Environment Variables):
   ```
   NEXT_PUBLIC_API_URL=https://your-railway-backend.up.railway.app
   ```
   ⚠️ **Important**: This must be your deployed backend URL from Step 1

4. **Deploy**
   - Vercel will automatically build and deploy
   - You'll get a URL like: `https://aria-frontend.vercel.app`

### 3.2: Update Backend CORS

After getting your Vercel URL, **go back to your backend** and:

1. Update `.env` on Railway/Render:
   ```bash
   APP_URL=https://aria-frontend.vercel.app
   ```

2. Redeploy backend

3. Test CORS by visiting your frontend and making API calls

---

## Step 4: Configure Supabase

1. **Go to Supabase Dashboard** → Authentication → URL Configuration

2. **Add Redirect URLs**:
   ```
   https://your-vercel-app.vercel.app/auth/reset-password
   https://your-vercel-app.vercel.app/auth/callback
   ```

3. **Site URL**:
   ```
   https://your-vercel-app.vercel.app
   ```

4. **Test Authentication**:
   - Sign up for a new account
   - Check email confirmation works
   - Test login flow

---

## Step 5: Test Everything

### Backend Health
```bash
curl https://your-backend.railway.app/api/health
```
Should return:
```json
{
  "status": "healthy",
  "services": {
    "api": "operational",
    "database": "operational",
    "llm": "operational"
  }
}
```

### Frontend → Backend Connection
1. Open browser console
2. Visit your Vercel app
3. Check Network tab - API calls should go to your Railway backend
4. No CORS errors should appear

### Full User Flow
1. Sign up → Should receive email
2. Confirm email → Should redirect to dashboard
3. Complete onboarding → Should analyze business
4. Run simulation → Should see agents and results

---

## Common Issues & Fixes

### ❌ "CORS policy: No 'Access-Control-Allow-Origin' header"
**Fix**: 
- Make sure `APP_URL` in backend `.env` matches your Vercel URL exactly
- Redeploy backend after changing
- Check: `ENVIRONMENT=production` is set

### ❌ "Failed to fetch" or connection errors
**Fix**:
- Verify `NEXT_PUBLIC_API_URL` in Vercel environment variables
- Make sure backend is actually running (check Railway logs)
- Test backend health endpoint directly

### ❌ "Unauthorized" or auth errors
**Fix**:
- Check `SUPABASE_JWT_SECRET` is set correctly on backend
- Verify `SUPABASE_ANON_KEY` is set on frontend (if using client-side auth)
- Check Supabase redirect URLs are configured

### ❌ Build fails on Vercel
**Fix**:
- Check `frontend/package.json` for errors
- Make sure `npm run build` works locally
- Check Vercel build logs for specific error

### ❌ Backend crashes or "Module not found"
**Fix**:
- Verify `requirements.txt` has all dependencies
- Check backend logs for Python errors
- Make sure Python version matches (3.11+)

---

## Environment Variables Checklist

### Backend (Railway/Render)
- [ ] `SUPABASE_URL`
- [ ] `SUPABASE_KEY` (service role key)
- [ ] `SUPABASE_ANON_KEY`
- [ ] `SUPABASE_JWT_SECRET`
- [ ] `ILMU_API_KEY`
- [ ] `ILMU_BASE_URL`
- [ ] `ILMU_MODEL`
- [ ] `ENVIRONMENT=production`
- [ ] `DEBUG=false`
- [ ] `APP_URL` (your Vercel frontend URL)

### Frontend (Vercel)
- [ ] `NEXT_PUBLIC_API_URL` (your Railway/Render backend URL)

---

## Cost Estimates

### Free Tier (Testing & Low Traffic)
- **Railway**: $5 free credit/month = ~500 hours (~20 days) of runtime ⭐
- **Vercel**: Free for hobby projects (100GB bandwidth)
- **Supabase**: Free tier (500MB database, 50k auth users)
- **Ilmu AI**: Pay per use (~$0.001-0.01 per request)

**Monthly cost for free tier: $0** (until Railway credit runs out)

### Paid (Production with Regular Traffic)
- **Railway**: ~$5-10/month (after free credit, depends on uptime)
- **Vercel**: Free to $20/month (Pro if you need more bandwidth)
- **Supabase**: Free to $25/month (upgrade if >500MB data)
- **Ilmu AI**: ~$10-50/month (depends on LLM usage)

**Estimated monthly cost: $15-85/month** (Railway + potential Supabase/Vercel upgrades)

### 💡 Tips to Stay Free Longer

**Railway credit optimization:**
- Your app uses ~$0.01/hour when running
- $5 credit = 500 hours = 20 days continuous uptime
- **To extend:** Set up sleep mode (pause when inactive)
- Railway auto-sleeps apps after 30 min inactivity (saves credit!)

**Vercel (always free for hobby):**
- 100GB bandwidth/month
- Unlimited sites
- Perfect for frontend

**Supabase free tier:**
- 500MB database (plenty for 100s of users)
- 50k monthly active users
- 2GB file storage

### 🎯 Realistic Costs

**Scenario 1: Testing/Demo (Low Traffic)**
- Railway: Free ($5 credit lasts weeks)
- Vercel: Free
- Supabase: Free
- Ilmu AI: ~$5/month
- **Total: ~$5/month**

**Scenario 2: Live Product (100 users/day)**
- Railway: ~$10/month (always-on)
- Vercel: Free
- Supabase: Free
- Ilmu AI: ~$20-30/month
- **Total: ~$30-40/month**

**Scenario 3: Popular Product (1000+ users/day)**
- Railway: ~$15-20/month
- Vercel: $20/month (Pro)
- Supabase: $25/month (Pro)
- Ilmu AI: ~$50-100/month
- **Total: ~$110-165/month**

---

## Monitoring & Maintenance

### Logs
- **Backend logs**: Railway/Render dashboard
- **Frontend logs**: Vercel dashboard → Functions tab
- **Database**: Supabase → Logs & Monitoring

### Health Checks
- Set up uptime monitoring (e.g., UptimeRobot)
- Monitor: `https://your-backend.up.railway.app/api/health`

### Updates
1. Push to GitHub
2. Railway auto-deploys backend
3. Vercel auto-deploys frontend

---

## Need Help?

Check the logs first:
1. Backend logs (Railway dashboard)
2. Frontend logs (Vercel dashboard)
3. Browser console (F12 → Console tab)
4. Network tab (F12 → Network tab)

Most issues are:
- Wrong environment variables
- CORS misconfiguration
- Backend not running
- Supabase redirect URLs not set

---

**Ready to deploy?** Start with Step 1 above! 🚀
