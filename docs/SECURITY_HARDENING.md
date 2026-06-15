# ARIA Security Hardening Changelog

> Summary of security improvements applied to the ARIA platform.  
> Date: 2026-05-22

---

## 1. Rate Limiting

**Package:** `slowapi==0.1.9` (added to `requirements.txt`)  
**Module:** `aria/api/security.py`

### How It Works

- IP-based rate limiting using `slowapi` (built on `limits` library)
- Extracts client IP from `X-Forwarded-For` header (for reverse proxy deployments) or direct connection
- In-memory storage (suitable for single-instance; swap to Redis URI for multi-instance)
- Graceful `429 Too Many Requests` response with `Retry-After` header and user-friendly message

### Rate Limits Applied

| Endpoint | Limit | Rationale |
|----------|-------|-----------|
| `POST /api/auth/register` | 5/min per IP | Prevent mass account creation |
| `POST /api/auth/login` | 5/min per IP | Prevent brute-force password attacks |
| `POST /api/auth/change-password` | 5/min per IP | Prevent brute-force on current password |
| `POST /api/auth/forgot-password` | 3/min per IP | Prevent email flooding |
| `POST /api/auth/reset-password` | 5/min per IP | Prevent token brute-force |
| `POST /api/simulation/suggest` | 15/min per IP | Moderate — triggers LLM call |
| `POST /api/simulation/start` | 10/min per IP | Expensive — triggers full LLM simulation |
| `POST /api/business/analyze` | 15/min per IP | Moderate — triggers LLM analysis |
| All other endpoints | 200/min per IP | Global default DoS protection |

### 429 Response Format

```json
{
  "detail": "Too many requests. Please slow down and try again shortly.",
  "retry_after": "minute"
}
```

---

## 2. Input Validation & Sanitization

### Schema-Level (Pydantic Models)

All request body models now enforce:

- **`extra = "forbid"`** — Rejects any unexpected fields in the request body. Prevents mass assignment and parameter pollution.
- **`max_length`** on all string fields — Prevents memory exhaustion from oversized payloads.
- **`ge` / `le` bounds** on numeric fields — Prevents out-of-range values.
- **`pattern` regex** on constrained fields (e.g., `role` must be `user` or `aria`).

### Field-Level Validators

| Field | Validation |
|-------|-----------|
| `email` | RFC 5322 regex, max 254 chars, normalized to lowercase |
| `business_name`, `business_type`, `location` | XSS/injection pattern detection, null byte removal, length truncation |
| `user_question` | Sanitized (null bytes, whitespace), max 1000 chars |
| `b2b_percentage` | Integer 0–100 |
| `price_range_min/max` | Float 0–1,000,000 |
| `agent_count` | Integer 15–100 |
| `password` | Min 6 chars, max 128 chars (strength validated separately) |

### Sanitization Utilities (`aria/api/security.py`)

| Function | Purpose |
|----------|---------|
| `sanitize_text(text, max_length)` | Strip whitespace, remove null bytes, truncate |
| `validate_uuid(value, field_name)` | Validate UUID v4 format, raise 400 if invalid |
| `check_for_injection(text, field_name)` | Detect `<script>`, `javascript:`, `on*=` patterns |
| `validate_email_format(email)` | RFC 5322 regex validation + normalization |

### Injection Detection Patterns

The following patterns trigger a `400 Bad Request`:

```
<script, javascript:, on*= (event handlers), data:text/html,
<iframe, <object, <embed
```

> Note: This is defense-in-depth. Primary protection remains parameterized queries (Supabase REST API) and output encoding (React's default XSS protection).

---

## 3. Secure API Key Handling

### Changes Made

| Issue | Fix |
|-------|-----|
| Supabase service role key exposed to browser via `NEXT_PUBLIC_SUPABASE_ANON_KEY` | **Removed** from `frontend/next.config.ts`. Only `NEXT_PUBLIC_API_URL` is exposed client-side. |
| Frontend had direct Supabase access | Confirmed frontend only communicates through FastAPI backend — no direct DB access. |
| All secrets in `.env` | Verified: all API keys (Supabase, Ilmu AI, News API, SMTP) loaded via `pydantic-settings`, never hardcoded in source. |

### What's Exposed Client-Side (Safe)

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### What's Backend-Only (Never Sent to Browser)

- `SUPABASE_URL` / `SUPABASE_KEY` / `SUPABASE_DB_PASSWORD`
- `ILMU_API_KEY`
- `NEWS_API_KEY`
- `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD`

### Recommendations for Production

1. **Rotate the Supabase service role key** — it was previously exposed in `next.config.ts`
2. Add `.env` to `.gitignore` (verify it's not tracked in git history)
3. Use a secrets manager (AWS Secrets Manager, HashiCorp Vault) in production
4. Create separate API keys for dev/staging/production environments

---

## 4. Security Headers

**Middleware:** `SecurityHeadersMiddleware` in `aria/api/security.py`

Every API response now includes:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME type sniffing |
| `X-Frame-Options` | `DENY` | Prevent clickjacking |
| `X-XSS-Protection` | `1; mode=block` | Legacy XSS protection |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Don't leak URLs to third parties |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Disable unnecessary browser APIs |
| `Server` | `ARIA` | Hide server technology fingerprint |

---

## 5. CORS Hardening

### Before

```python
allow_methods=["*"]
allow_headers=["*"]
```

### After

```python
allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
allow_headers=["Content-Type", "Authorization", "X-Requested-With"]
```

Only the HTTP methods and headers actually used by the frontend are permitted. This reduces the attack surface for CSRF and preflight abuse.

---

## 6. Password Strength Enforcement

**Module:** `aria/auth/password.py`

All password creation/change flows now enforce:

- Minimum 6 characters
- At least 1 uppercase letter (`[A-Z]`)
- At least 1 number (`[0-9]`)
- At least 1 special character (`!@#$%^&*` etc.)

Applied to:
- `POST /api/auth/register`
- `POST /api/auth/change-password`
- `POST /api/auth/reset-password`
- Frontend registration form (client-side pre-validation)
- Frontend reset password page (client-side pre-validation)

---

## Files Modified

| File | Changes |
|------|---------|
| `aria/api/main.py` | Rate limiting decorators, stricter Pydantic models, security imports |
| `aria/api/security.py` | **New** — Rate limiter, security headers middleware, sanitization utilities |
| `aria/auth/password.py` | **New** — Password strength validation |
| `aria/auth/email.py` | **New** — SMTP email utility for password resets |
| `aria/config.py` | Added SMTP and APP_URL settings |
| `frontend/next.config.ts` | Removed Supabase key exposure |
| `frontend/src/components/auth/AuthModal.tsx` | Client-side password validation |
| `frontend/src/app/auth/reset-password/page.tsx` | **New** — Reset password page |
| `requirements.txt` | Added `slowapi==0.1.9` |
| `.env` | Added SMTP config placeholders |

---

## OWASP References

- [Input Validation Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)
- [Denial of Service Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html)
- [Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [HTTP Headers Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html)
- [Forgot Password Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html)

---

## Remaining Recommendations (Future Work)

1. **JWT-based authentication** — Replace client-supplied `user_id` with server-verified tokens
2. **Ownership checks** — Verify user owns the resource before returning/modifying data
3. **HTTPS enforcement** — Add redirect middleware and HSTS headers in production
4. **Supabase Row-Level Security** — Enable RLS policies as defense-in-depth
5. **Audit logging** — Log auth events (login, failed attempts, password changes)
6. **Redis-backed rate limiting** — For multi-instance deployments
7. **CSRF tokens** — For cookie-based auth flows (if added later)
