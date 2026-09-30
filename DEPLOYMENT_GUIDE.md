# 🚀 ARIA Deployment Guide

## Quick Start

Your ARIA app has **TWO separate parts** that need to be deployed:

1. **Frontend (Next.js)** → Deploy to Vercel
2. **Backend (FastAPI Python)** → Deploy to Railway/Render/Fly.io

You **CANNOT** deploy the Python backend to Vercel. Follow this guide step-by-step.

---

## Step 1: Deploy Backend (Python FastAPI)

⚠️ **Important**: This backend uses data science libraries and runs simulations. Measure memory use under a representative workload before choosing a small instance; the old 1–2 GB estimate was not measured under production load.

### Option A: Railway (⭐ RECOMMENDED)

**Railway plan note:** Railway Free provides 0.5 GB RAM per service after the trial. New accounts may receive a one-time trial credit; it is not a recurring $5 monthly credit. Hobby has a $5 monthly minimum that counts toward usage. Check [current Railway pricing](https://railway.com/pricing) before choosing a plan. Measure memory under simulation load before relying on Free.

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
   - The app reads Railway's injected `PORT`; do not hard-code a separate port.

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
   ```

   `SUPABASE_DB_PASSWORD` is not needed; the app does not use a direct PostgreSQL connection.
   Configure `ILMU_API_KEY` for the hosted LLM provider. The default Ollama URL points to `localhost`, which is the Railway container itself; set `OLLAMA_BASE_URL` to a reachable hosted Ollama service if you need that fallback.
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
- Plan limits and prices change; verify current memory and pricing with Render before choosing it.

If you want to use Render, configure it as a Python web service:

1. Go to [render.com](https://render.com)
2. New → Web Service
3. Connect GitHub repo
4. Choose a plan with enough memory for your measured simulation workload
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
| **Railway Free** | 0.5GB | $0 after trial; limited resources | Test deployments |
| **Railway Hobby** | Configure to workload | $5/month minimum usage | Small always-on backend |
| Other providers | Check current limits | Varies | Compare against measured workload |

Choose a Railway plan based on measured memory and runtime. Free is useful for a test deployment, but may not be enough for ARIA simulations.

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

   Set **Root Directory** to `frontend`. Leave framework, build command, and output directory at their Next.js defaults. `vercel-config.json` is not the recognized Vercel configuration filename and is not used by this setup.

3. **Add Environment Variables** (Settings → Environment Variables):
   ```
   NEXT_PUBLIC_API_URL=https://your-railway-backend.up.railway.app
   NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
   ```
   ⚠️ Set these for Production (and Preview if needed). `NEXT_PUBLIC_*` values are included in the browser build; use only the Supabase anon/public key, never the service-role key. Redeploy after changing a variable.

   Vercel Hobby is for personal, non-commercial use. Check [Vercel's plan terms](https://vercel.com/docs/plans/hobby) against your intended use; commercial usage requires an eligible paid plan under its [fair use guidelines](https://vercel.com/docs/limits/fair-use-guidelines).

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
- [ ] `NEXT_PUBLIC_SUPABASE_URL`
- [ ] `NEXT_PUBLIC_SUPABASE_ANON_KEY` (anon/public key only)

---

## Cost Estimates

### Free Tier (Testing & Low Traffic)
- **Railway**: $1/month of free resource credit after trial; 0.5 GB RAM per service. Check current limits and pricing.
- **Vercel**: Hobby is free for personal, non-commercial projects; commercial usage requires an eligible paid plan.
- **Supabase**: Free tier (500MB database, 50k auth users)
- **Ilmu AI**: Pay per use (~$0.001-0.01 per request)

Check provider pricing and your account's usage for current cost estimates.

### Cost planning

**Railway costs** depend on memory, CPU, and uptime. Trial credit is one-time and Free-plan monthly credit is limited. Use Railway's usage dashboard; do not assume the service automatically sleeps while idle.

Use the current [Railway pricing](https://railway.com/pricing), [Vercel plan terms](https://vercel.com/docs/plans), and your Supabase/LLM billing dashboards for estimates. Costs vary with uptime, resources, and model usage; the old estimates in this guide are not reliable.

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
