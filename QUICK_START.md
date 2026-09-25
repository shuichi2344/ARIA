# 🚀 ARIA Deployment Quick Start

## TL;DR - Fast Track

### What You Need
- GitHub account
- Credit card (for Railway verification - won't charge immediately)
- 30 minutes

### The Plan
1. Backend → Railway (8GB RAM free tier)
2. Frontend → Vercel (free)
3. Database → Supabase (already set up)

---

## 5-Minute Backend Deploy (Railway)

### Step 1: Railway Setup (10 min)

1. Go to **[railway.app](https://railway.app)**
2. Click **"Start a New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your **ARIA** repository
5. Railway will auto-detect Python ✅

### Step 2: Add Environment Variables (5 min)

Go to **Settings → Variables** and add:

```bash
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_service_role_key
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_JWT_SECRET=your_jwt_secret
ILMU_API_KEY=your_ilmu_key
ILMU_BASE_URL=https://api.ilmu.ai/v1
ILMU_MODEL=nemo-super
ENVIRONMENT=production
DEBUG=false
APP_URL=https://your-app.vercel.app
```

### Step 3: Deploy (2 min)

1. Railway automatically starts deploying
2. Wait for build to complete
3. Copy your backend URL (e.g., `https://aria-production.up.railway.app`)

### Step 4: Test (1 min)

Visit: `https://your-railway-url.up.railway.app/api/health`

Should see:
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

✅ Backend deployed!

---

## 5-Minute Frontend Deploy (Vercel)

### Step 1: Vercel Setup (5 min)

1. Go to **[vercel.com](https://vercel.com)**
2. Click **"Add New Project"**
3. Import your **ARIA** repository
4. Framework Preset: **Next.js** (auto-detected)
5. Root Directory: `frontend` ⚠️ **Important!**

### Step 2: Environment Variables (2 min)

In Vercel project settings, add:

```bash
NEXT_PUBLIC_API_URL=https://your-railway-url.up.railway.app
```

(Use the URL from Railway Step 3)

### Step 3: Deploy (3 min)

1. Click **"Deploy"**
2. Wait for build (2-3 minutes)
3. Copy your Vercel URL (e.g., `https://aria.vercel.app`)

✅ Frontend deployed!

---

## Final Steps (5 min)

### Update Backend CORS

1. Go back to **Railway**
2. **Settings → Variables**
3. Update `APP_URL` to your Vercel URL:
   ```
   APP_URL=https://aria.vercel.app
   ```
4. Railway will auto-redeploy

### Update Supabase

1. Go to **Supabase Dashboard** → Authentication → URL Configuration
2. Add redirect URLs:
   ```
   https://aria.vercel.app/auth/reset-password
   https://aria.vercel.app/auth/callback
   ```
3. Site URL:
   ```
   https://aria.vercel.app
   ```

---

## Test Your Deployment

### 1. Frontend Loads
Visit `https://aria.vercel.app` - should see landing page

### 2. API Connection
Open browser console (F12) → Network tab
- Should see calls to your Railway backend
- No CORS errors ✅

### 3. Auth Flow
1. Sign up for account
2. Check email for confirmation
3. Log in
4. Should reach dashboard

### 4. Run Simulation
1. Complete onboarding
2. Ask a question
3. Run simulation
4. Should see agents and results

---

## Troubleshooting (5 min)

### ❌ CORS Error
**Fix:** Make sure `APP_URL` in Railway matches your Vercel URL exactly

### ❌ "Failed to fetch"
**Fix:** Check `NEXT_PUBLIC_API_URL` in Vercel points to Railway URL

### ❌ Auth doesn't work
**Fix:** Verify Supabase redirect URLs are set correctly

### ❌ Backend is slow
**Reason:** Railway free tier sleeps after 30min inactivity (saves credit)
**Fix:** First request takes 10-20 seconds (wakes up server)

---

## Cost Summary

### What's Free
- ✅ Railway: $5 credit = ~500 hours (~20 days uptime)
- ✅ Vercel: Unlimited (hobby plan)
- ✅ Supabase: Up to 500MB data, 50k users

### After Free Credit
- Railway: ~$10/month for always-on
- Vercel: Still free (hobby plan)
- Supabase: Still free (unless >500MB data)
- LLM (Ilmu AI): ~$5-20/month depending on usage

**Total: $15-30/month** for production app

---

## Done! 🎉

Your app is now live:
- Frontend: `https://aria.vercel.app`
- Backend: `https://aria-production.up.railway.app`

Share the Vercel URL with users!

---

## Next Steps

### Want to customize?
- Update frontend code → Auto-deploys on git push
- Update backend code → Auto-deploys on git push

### Want to monitor?
- Railway: Dashboard → Logs
- Vercel: Dashboard → Functions → Logs
- Supabase: Dashboard → Logs

### Want a custom domain?
1. Buy domain (e.g., Namecheap, GoDaddy)
2. Add to Vercel: Settings → Domains
3. Update DNS records as instructed
4. Update `APP_URL` in Railway

---

**Total Time: ~20-30 minutes**

For detailed explanations, see:
- `DEPLOYMENT_GUIDE.md` - Full step-by-step guide
- `DEPLOYMENT_PLATFORMS.md` - Platform comparison
- `DEPLOYMENT_ISSUES.md` - Bug fixes applied
