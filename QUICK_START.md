# 🚀 ARIA Deployment Quick Start

## TL;DR - Fast Track

### What You Need
- GitHub account
- Credit card (for Railway verification - won't charge immediately)
- 30 minutes

### The Plan
1. Backend → Railway (Free is limited to 0.5 GB RAM after trial; check whether your simulation workload fits)
2. Frontend → Vercel (Hobby is for personal, non-commercial use)
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

The app reads Railway's injected `PORT` automatically. `SUPABASE_DB_PASSWORD` is not required because the backend does not use a direct PostgreSQL connection.
Configure `ILMU_API_KEY` for the hosted LLM provider. The default Ollama URL points to the Railway container itself; if you need Ollama fallback, set `OLLAMA_BASE_URL` to a reachable hosted Ollama service.

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
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
```

Use the Railway URL from Step 3 and the Supabase anon/public key only. Never expose the service-role key in frontend variables. Set Vercel's Root Directory to `frontend`; redeploy after changing variables. Check [Vercel's Hobby terms](https://vercel.com/docs/plans/hobby) before offering ARIA for commercial use.

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
**Fix:** Check Railway resource usage and deployment logs; startup and simulation latency depend on the selected plan and workload.

---

## Cost Summary

### Plan notes
- Railway provides limited Free resources after its trial; check current limits and usage.
- Vercel Hobby is for personal, non-commercial use. Commercial usage may require a paid plan.
- Check current Supabase and Ilmu AI pricing and usage in their dashboards.

Review provider billing dashboards before making ARIA available to users; costs depend on resource use and LLM calls.

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
