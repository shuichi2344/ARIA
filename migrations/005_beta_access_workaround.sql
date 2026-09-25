-- =============================================================================
-- ARIA — Beta Access Management (Workaround for Trigger Limitation)
-- =============================================================================
-- Purpose: Since we can't create triggers on auth.users (permission denied),
--          we use a helper function that you call manually or via API
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- Helper function: Grant beta access to newly invited user
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.grant_beta_access_to_new_user(user_email TEXT)
RETURNS TABLE(
    user_id UUID,
    email TEXT,
    expires_at TIMESTAMPTZ,
    message TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    target_user_id UUID;
    current_metadata JSONB;
    new_metadata JSONB;
    new_expiry TIMESTAMPTZ;
BEGIN
    -- Find user by email
    SELECT id, raw_user_meta_data INTO target_user_id, current_metadata
    FROM auth.users
    WHERE auth.users.email = user_email;
    
    IF target_user_id IS NULL THEN
        RAISE EXCEPTION 'User with email % not found', user_email;
    END IF;
    
    -- Check if already has beta access
    IF current_metadata IS NOT NULL 
       AND current_metadata->>'beta_access_expires_at' IS NOT NULL THEN
        RETURN QUERY SELECT 
            target_user_id,
            user_email,
            (current_metadata->>'beta_access_expires_at')::TIMESTAMPTZ,
            'User already has beta access'::TEXT;
        RETURN;
    END IF;
    
    -- Grant 7-day beta access
    IF current_metadata IS NULL THEN
        current_metadata := '{}'::JSONB;
    END IF;
    
    new_expiry := NOW() + INTERVAL '7 days';
    
    new_metadata := current_metadata || jsonb_build_object(
        'beta_access_expires_at', new_expiry::TEXT,
        'beta_invited_at', NOW()::TEXT
    );
    
    UPDATE auth.users
    SET raw_user_meta_data = new_metadata,
        updated_at = NOW()
    WHERE id = target_user_id;
    
    -- Return result
    RETURN QUERY SELECT 
        target_user_id,
        user_email,
        new_expiry,
        'Beta access granted for 7 days'::TEXT;
END;
$$;

COMMENT ON FUNCTION public.grant_beta_access_to_new_user IS 
'Grant 7-day beta access to a newly invited user. Call manually after user signs up.';


-- =============================================================================
-- Usage Instructions
-- =============================================================================
-- After a user accepts invitation and sets password, run:
--
--   SELECT * FROM grant_beta_access_to_new_user('user@example.com');
--
-- This will:
-- 1. Find the user by email
-- 2. Check if they already have beta access (skip if yes)
-- 3. Grant 7-day beta access
-- 4. Return confirmation
--
-- To check all beta users:
--   SELECT * FROM list_beta_users();
--
-- To extend existing user's access:
--   SELECT * FROM extend_beta_access('user@example.com', 14);
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- Bonus: View users who need beta access granted
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.list_users_without_beta_access()
RETURNS TABLE(
    user_id UUID,
    email TEXT,
    created_at TIMESTAMPTZ,
    confirmed_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        u.id,
        u.email::TEXT,
        u.created_at,
        u.confirmed_at
    FROM auth.users u
    WHERE (u.raw_user_meta_data IS NULL 
           OR u.raw_user_meta_data->>'beta_access_expires_at' IS NULL)
      AND u.confirmed_at IS NOT NULL  -- Only show confirmed users
    ORDER BY u.created_at DESC;
END;
$$;

COMMENT ON FUNCTION public.list_users_without_beta_access IS 
'List confirmed users who do not have beta access yet';


-- =============================================================================
-- Quick Workflow for Managing Beta Users
-- =============================================================================
-- 
-- 1. INVITE USER (via Supabase Dashboard):
--    Authentication → Users → "Invite user" button
--
-- 2. WAIT FOR USER TO CONFIRM
--    User clicks invitation link and sets password
--
-- 3. CHECK WHO NEEDS ACCESS:
--    SELECT * FROM list_users_without_beta_access();
--
-- 4. GRANT ACCESS:
--    SELECT * FROM grant_beta_access_to_new_user('user@example.com');
--
-- 5. VERIFY:
--    SELECT * FROM list_beta_users();
--
-- =============================================================================
