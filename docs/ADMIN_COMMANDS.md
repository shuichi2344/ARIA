# ARIA Beta Testing - Admin Quick Reference

Quick reference for managing beta testers via Supabase SQL Editor.

---

## View All Beta Users

```sql
SELECT * FROM list_beta_users();
```

Shows all beta users with expiration status, days remaining, and acceptance timestamps.

---

## Invite a New User

1. Go to Supabase Dashboard → **Authentication → Users**
2. Click **"Invite user"**
3. Enter email address
4. Click **"Send invitation"**

User receives an email with a 6-hour invitation link.

---

## Extend Access (Default 7 Days)

```sql
SELECT * FROM extend_beta_access('user@example.com', 7);
```

---

## Extend Access (Custom Duration)

```sql
-- 14 days
SELECT * FROM extend_beta_access('user@example.com', 14);

-- 30 days
SELECT * FROM extend_beta_access('user@example.com', 30);

-- 90 days
SELECT * FROM extend_beta_access('user@example.com', 90);
```

---

## Revoke Access Immediately

```sql
SELECT * FROM revoke_beta_access('user@example.com');
```

User will be blocked on their next login attempt.

---

## Check Specific User's Status

```sql
-- Get detailed status
SELECT 
  email,
  (raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ as expires_at,
  (raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ > NOW() as is_valid,
  EXTRACT(DAY FROM (raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ - NOW()) as days_remaining
FROM auth.users
WHERE email = 'user@example.com';
```

---

## Find Users Expiring Soon

```sql
-- Expiring in next 3 days
SELECT 
  email,
  (raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ as expires_at,
  EXTRACT(DAY FROM (raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ - NOW()) as days_remaining
FROM auth.users
WHERE 
  (raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ > NOW()
  AND (raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ < NOW() + INTERVAL '3 days'
ORDER BY expires_at ASC;
```

---

## Find Already Expired Users

```sql
SELECT 
  email,
  (raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ as expired_at
FROM auth.users
WHERE 
  (raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ < NOW()
ORDER BY expired_at DESC;
```

---

## Manually Set Custom Expiration Date

```sql
-- Set specific date
UPDATE auth.users
SET raw_user_meta_data = raw_user_meta_data || 
    jsonb_build_object('beta_access_expires_at', '2026-12-31T23:59:59Z')
WHERE email = 'user@example.com';
```

---

## Remove Beta Access Entirely (Make Permanent)

```sql
-- Remove expiration (not recommended for beta)
UPDATE auth.users
SET raw_user_meta_data = raw_user_meta_data - 'beta_access_expires_at'
WHERE email = 'user@example.com';
```

⚠️ **Warning:** This removes access control. Only use for transitioning out of beta phase.

---

## Batch Operations

### Extend All Active Users by 7 Days

```sql
-- Extend everyone who hasn't expired yet
UPDATE auth.users
SET raw_user_meta_data = raw_user_meta_data || 
    jsonb_build_object(
        'beta_access_expires_at',
        ((raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ + INTERVAL '7 days')::TEXT
    )
WHERE 
    raw_user_meta_data->>'beta_access_expires_at' IS NOT NULL
    AND (raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ > NOW();
```

### Revoke All Expired Access (Cleanup)

```sql
-- Already blocked by RLS, but this makes it explicit
UPDATE auth.users
SET raw_user_meta_data = raw_user_meta_data || 
    jsonb_build_object('beta_access_expires_at', NOW()::TEXT)
WHERE 
    raw_user_meta_data->>'beta_access_expires_at' IS NOT NULL
    AND (raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ < NOW();
```

---

## Export User List for Email Campaign

```sql
-- Export active users (for bulk email)
SELECT 
  email,
  (raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ as expires_at,
  EXTRACT(DAY FROM (raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ - NOW()) as days_remaining
FROM auth.users
WHERE 
  (raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ > NOW()
ORDER BY expires_at ASC;
```

Copy to CSV via Supabase SQL Editor → Results → Export.

---

## Common Scenarios

### Scenario: User Requests Extension

```sql
-- Check current status
SELECT * FROM list_beta_users() WHERE email = 'user@example.com';

-- Extend by 14 days
SELECT * FROM extend_beta_access('user@example.com', 14);
```

### Scenario: User Reports Access Issue

```sql
-- Verify they have access set
SELECT 
  email,
  raw_user_meta_data->>'beta_access_expires_at' as expires_at,
  is_beta_access_valid(id) as is_valid
FROM auth.users
WHERE email = 'user@example.com';

-- If null or invalid, set new expiration
SELECT set_beta_access_expiration(
    (SELECT id FROM auth.users WHERE email = 'user@example.com'),
    7
);
```

### Scenario: Week-Long Beta Test Event

```sql
-- Day 1: Send invitations via Supabase Dashboard UI

-- Day 4: Check participation
SELECT COUNT(*) FROM auth.users 
WHERE raw_user_meta_data->>'beta_invited_at' IS NOT NULL;

-- Day 6: Remind expiring users (export emails)
SELECT email FROM auth.users
WHERE (raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ < NOW() + INTERVAL '2 days';

-- Day 7: Extend active users
SELECT * FROM extend_beta_access(email, 7)
FROM auth.users
WHERE (raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ > NOW();
```

---

## Troubleshooting Commands

### User Can't Login - Check Why

```sql
SELECT 
  email,
  email_confirmed_at,
  (raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ as expires_at,
  CASE 
    WHEN email_confirmed_at IS NULL THEN 'Email not confirmed'
    WHEN (raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ < NOW() THEN 'Beta access expired'
    WHEN raw_user_meta_data->>'beta_access_expires_at' IS NULL THEN 'No beta access set'
    ELSE 'Should be able to login'
  END as issue
FROM auth.users
WHERE email = 'user@example.com';
```

### Fix: User Invitation Expired Before Setting Password

```sql
-- Re-invite via Dashboard, or manually set password + expiration
-- First, set their password (user must give you password securely)
-- Then set expiration:
SELECT set_beta_access_expiration(
    (SELECT id FROM auth.users WHERE email = 'user@example.com'),
    7
);
```

---

## Monitoring Queries (Run Daily)

### Daily Summary

```sql
SELECT 
  COUNT(*) FILTER (WHERE (raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ > NOW()) as active_users,
  COUNT(*) FILTER (WHERE (raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ < NOW()) as expired_users,
  COUNT(*) FILTER (WHERE (raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ BETWEEN NOW() AND NOW() + INTERVAL '3 days') as expiring_soon
FROM auth.users
WHERE raw_user_meta_data->>'beta_access_expires_at' IS NOT NULL;
```

### Engagement Tracking

```sql
-- Users who set up password but never logged in
SELECT 
  email,
  (raw_user_meta_data->>'beta_invited_at')::TIMESTAMPTZ as invited_at,
  last_sign_in_at
FROM auth.users
WHERE 
  raw_user_meta_data->>'beta_invited_at' IS NOT NULL
  AND last_sign_in_at IS NULL;
```

---

## Safety Tips

✅ **Always check user status** before revoking access  
✅ **Extend in small increments** (7-14 days) to maintain control  
✅ **Export user list regularly** for backup  
✅ **Test commands on a test user** first for batch operations  
❌ **Never delete users from auth.users** (data loss is permanent)  
❌ **Don't remove expiration entirely** during beta phase  

---

## Emergency: Disable Beta Access System

If you need to temporarily disable access control (production transition, emergency):

```sql
-- OPTION 1: Extend everyone by 365 days
UPDATE auth.users
SET raw_user_meta_data = raw_user_meta_data || 
    jsonb_build_object('beta_access_expires_at', (NOW() + INTERVAL '365 days')::TEXT)
WHERE raw_user_meta_data->>'beta_access_expires_at' IS NOT NULL;

-- OPTION 2: Remove expiration check from RLS policies (requires migration)
-- See migration 005_disable_beta_access.sql (create if needed)
```

---

## Contact

For issues with these commands or access control questions, check:
- Supabase Logs: Dashboard → Logs → Postgres Logs
- API Logs: Backend server logs
- Frontend Console: Browser DevTools

Or refer to the full guide: `docs/BETA_TESTING_SETUP.md`
