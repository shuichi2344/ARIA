-- =============================================================================
-- ARIA — Beta Testing Access Control System
-- =============================================================================
-- Purpose: Implement time-limited beta testing access with invitation-only signup
-- Run in: Supabase Dashboard → SQL Editor → New query → Run
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Add beta access tracking columns to auth.users via user_metadata
-- ─────────────────────────────────────────────────────────────────────────────
-- Note: We store these in auth.users metadata instead of business_profiles
-- because access control must work BEFORE a business profile is created.
-- auth.users.raw_user_meta_data is a JSONB column for custom user data.

-- The metadata structure will be:
-- {
--   "beta_access_expires_at": "2026-10-01T00:00:00Z",
--   "beta_invited_at": "2026-09-23T10:30:00Z"
-- }

-- No schema changes needed - metadata is already JSONB


-- ─────────────────────────────────────────────────────────────────────────────
-- 2. Create helper functions for beta access management
-- ─────────────────────────────────────────────────────────────────────────────

-- Function: Check if a user's beta access is still valid
CREATE OR REPLACE FUNCTION public.is_beta_access_valid(user_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    expires_at TIMESTAMPTZ;
    user_metadata JSONB;
BEGIN
    -- Get user metadata from auth.users
    SELECT raw_user_meta_data INTO user_metadata
    FROM auth.users
    WHERE id = user_id;
    
    -- If no metadata or no expiration set, deny access (invitation-only system)
    IF user_metadata IS NULL OR user_metadata->>'beta_access_expires_at' IS NULL THEN
        RETURN FALSE;
    END IF;
    
    -- Parse expiration timestamp
    expires_at := (user_metadata->>'beta_access_expires_at')::TIMESTAMPTZ;
    
    -- Check if still valid
    RETURN expires_at > NOW();
END;
$$;

COMMENT ON FUNCTION public.is_beta_access_valid IS 
'Check if a user''s beta access period is still valid. Returns FALSE if expired or not set.';


-- Function: Set beta access expiration (called after password setup)
CREATE OR REPLACE FUNCTION public.set_beta_access_expiration(
    user_id UUID,
    days_from_now INTEGER DEFAULT 7
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    new_metadata JSONB;
    current_metadata JSONB;
BEGIN
    -- Get current metadata
    SELECT raw_user_meta_data INTO current_metadata
    FROM auth.users
    WHERE id = user_id;
    
    -- If null, initialize as empty object
    IF current_metadata IS NULL THEN
        current_metadata := '{}'::JSONB;
    END IF;
    
    -- Set expiration timestamp and invited timestamp
    new_metadata := current_metadata || jsonb_build_object(
        'beta_access_expires_at', (NOW() + (days_from_now || ' days')::INTERVAL)::TEXT,
        'beta_invited_at', NOW()::TEXT
    );
    
    -- Update user metadata
    UPDATE auth.users
    SET raw_user_meta_data = new_metadata,
        updated_at = NOW()
    WHERE id = user_id;
    
    RAISE NOTICE 'Beta access set for user % until %', 
        user_id, 
        (NOW() + (days_from_now || ' days')::INTERVAL)::TEXT;
END;
$$;

COMMENT ON FUNCTION public.set_beta_access_expiration IS 
'Set beta access expiration for a user (default 7 days from now). Called after password setup.';


-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Admin management functions (run these from SQL Editor as needed)
-- ─────────────────────────────────────────────────────────────────────────────

-- Function: Extend beta access for a user (by email)
CREATE OR REPLACE FUNCTION public.extend_beta_access(
    user_email TEXT,
    additional_days INTEGER DEFAULT 7
)
RETURNS TABLE(
    user_id UUID,
    email TEXT,
    old_expires_at TIMESTAMPTZ,
    new_expires_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    target_user_id UUID;
    current_metadata JSONB;
    old_expiry TIMESTAMPTZ;
    new_expiry TIMESTAMPTZ;
    new_metadata JSONB;
BEGIN
    -- Find user by email
    SELECT id, raw_user_meta_data INTO target_user_id, current_metadata
    FROM auth.users
    WHERE auth.users.email = user_email;
    
    IF target_user_id IS NULL THEN
        RAISE EXCEPTION 'User with email % not found', user_email;
    END IF;
    
    -- Get current expiration
    IF current_metadata IS NOT NULL AND current_metadata->>'beta_access_expires_at' IS NOT NULL THEN
        old_expiry := (current_metadata->>'beta_access_expires_at')::TIMESTAMPTZ;
        -- Extend from current expiration
        new_expiry := old_expiry + (additional_days || ' days')::INTERVAL;
    ELSE
        -- No expiration set, extend from now
        old_expiry := NULL;
        new_expiry := NOW() + (additional_days || ' days')::INTERVAL;
    END IF;
    
    -- Update metadata
    IF current_metadata IS NULL THEN
        current_metadata := '{}'::JSONB;
    END IF;
    
    new_metadata := current_metadata || jsonb_build_object(
        'beta_access_expires_at', new_expiry::TEXT
    );
    
    UPDATE auth.users
    SET raw_user_meta_data = new_metadata,
        updated_at = NOW()
    WHERE id = target_user_id;
    
    -- Return result
    RETURN QUERY SELECT target_user_id, user_email, old_expiry, new_expiry;
END;
$$;

COMMENT ON FUNCTION public.extend_beta_access IS 
'Extend beta access for a user by email. Usage: SELECT * FROM extend_beta_access(''user@example.com'', 14);';


-- Function: Revoke beta access immediately (by email)
CREATE OR REPLACE FUNCTION public.revoke_beta_access(user_email TEXT)
RETURNS TABLE(
    user_id UUID,
    email TEXT,
    revoked_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    target_user_id UUID;
    current_metadata JSONB;
    new_metadata JSONB;
BEGIN
    -- Find user by email
    SELECT id, raw_user_meta_data INTO target_user_id, current_metadata
    FROM auth.users
    WHERE auth.users.email = user_email;
    
    IF target_user_id IS NULL THEN
        RAISE EXCEPTION 'User with email % not found', user_email;
    END IF;
    
    -- Set expiration to now (immediately expired)
    IF current_metadata IS NULL THEN
        current_metadata := '{}'::JSONB;
    END IF;
    
    new_metadata := current_metadata || jsonb_build_object(
        'beta_access_expires_at', NOW()::TEXT
    );
    
    UPDATE auth.users
    SET raw_user_meta_data = new_metadata,
        updated_at = NOW()
    WHERE id = target_user_id;
    
    -- Return result
    RETURN QUERY SELECT target_user_id, user_email, NOW();
END;
$$;

COMMENT ON FUNCTION public.revoke_beta_access IS 
'Immediately revoke beta access for a user. Usage: SELECT * FROM revoke_beta_access(''user@example.com'');';


-- Function: List all beta users with their expiration status (times in GMT+8)
DROP FUNCTION IF EXISTS public.list_beta_users();

CREATE OR REPLACE FUNCTION public.list_beta_users()
RETURNS TABLE(
    user_id UUID,
    email TEXT,
    created_at_gmt8 TEXT,
    expires_at_gmt8 TEXT,
    is_expired BOOLEAN,
    days_remaining INTEGER,
    invited_at_gmt8 TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        u.id,
        u.email::TEXT,
        TO_CHAR(u.created_at AT TIME ZONE 'Asia/Kuala_Lumpur', 'YYYY-MM-DD HH24:MI:SS') as created_at_gmt8,
        TO_CHAR((u.raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ AT TIME ZONE 'Asia/Kuala_Lumpur', 'YYYY-MM-DD HH24:MI:SS') as expires_at_gmt8,
        CASE 
            WHEN (u.raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ < NOW() THEN TRUE
            WHEN u.raw_user_meta_data->>'beta_access_expires_at' IS NULL THEN TRUE
            ELSE FALSE
        END as is_expired,
        CASE 
            WHEN (u.raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ > NOW() 
            THEN EXTRACT(DAY FROM (u.raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ - NOW())::INTEGER
            ELSE 0
        END as days_remaining,
        TO_CHAR((u.raw_user_meta_data->>'beta_invited_at')::TIMESTAMPTZ AT TIME ZONE 'Asia/Kuala_Lumpur', 'YYYY-MM-DD HH24:MI:SS') as invited_at_gmt8
    FROM auth.users u
    WHERE u.raw_user_meta_data->>'beta_access_expires_at' IS NOT NULL
    ORDER BY 
        CASE 
            WHEN (u.raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ < NOW() THEN 1
            ELSE 0
        END,
        (u.raw_user_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ ASC;
END;
$$;

COMMENT ON FUNCTION public.list_beta_users IS 
'List all beta users with their access status. All times in GMT+8 (Asia/Kuala_Lumpur). Usage: SELECT * FROM list_beta_users();';


-- ─────────────────────────────────────────────────────────────────────────────
-- 4. Update RLS policies to enforce beta access expiration
-- ─────────────────────────────────────────────────────────────────────────────

-- Add beta access check to all existing policies
-- This ensures expired users cannot access ANY data

-- business_profiles policies
DROP POLICY IF EXISTS "Allow users to select their own profiles" ON public.business_profiles;
CREATE POLICY "Allow users to select their own profiles"
ON public.business_profiles
FOR SELECT
USING (
    user_id = auth.uid() 
    AND public.is_beta_access_valid(auth.uid())
);

DROP POLICY IF EXISTS "Allow users to insert their own profiles" ON public.business_profiles;
CREATE POLICY "Allow users to insert their own profiles"
ON public.business_profiles
FOR INSERT
WITH CHECK (
    user_id = auth.uid()
    AND public.is_beta_access_valid(auth.uid())
);

DROP POLICY IF EXISTS "Allow users to update their own profiles" ON public.business_profiles;
CREATE POLICY "Allow users to update their own profiles"
ON public.business_profiles
FOR UPDATE
USING (
    user_id = auth.uid()
    AND public.is_beta_access_valid(auth.uid())
)
WITH CHECK (
    user_id = auth.uid()
    AND public.is_beta_access_valid(auth.uid())
);

DROP POLICY IF EXISTS "Allow users to delete their own profiles" ON public.business_profiles;
CREATE POLICY "Allow users to delete their own profiles"
ON public.business_profiles
FOR DELETE
USING (
    user_id = auth.uid()
    AND public.is_beta_access_valid(auth.uid())
);


-- chat_sessions policies
DROP POLICY IF EXISTS "Allow users to select their own chat sessions" ON public.chat_sessions;
CREATE POLICY "Allow users to select their own chat sessions"
ON public.chat_sessions
FOR SELECT
USING (
    user_id = auth.uid()
    AND public.is_beta_access_valid(auth.uid())
);

DROP POLICY IF EXISTS "Allow users to insert their own chat sessions" ON public.chat_sessions;
CREATE POLICY "Allow users to insert their own chat sessions"
ON public.chat_sessions
FOR INSERT
WITH CHECK (
    user_id = auth.uid()
    AND public.is_beta_access_valid(auth.uid())
);

DROP POLICY IF EXISTS "Allow users to update their own chat sessions" ON public.chat_sessions;
CREATE POLICY "Allow users to update their own chat sessions"
ON public.chat_sessions
FOR UPDATE
USING (
    user_id = auth.uid()
    AND public.is_beta_access_valid(auth.uid())
)
WITH CHECK (
    user_id = auth.uid()
    AND public.is_beta_access_valid(auth.uid())
);

DROP POLICY IF EXISTS "Allow users to delete their own chat sessions" ON public.chat_sessions;
CREATE POLICY "Allow users to delete their own chat sessions"
ON public.chat_sessions
FOR DELETE
USING (
    user_id = auth.uid()
    AND public.is_beta_access_valid(auth.uid())
);


-- chat_messages policies
DROP POLICY IF EXISTS "Allow users to select their own chat messages" ON public.chat_messages;
CREATE POLICY "Allow users to select their own chat messages"
ON public.chat_messages
FOR SELECT
USING (
    session_id IN (
        SELECT session_id FROM public.chat_sessions WHERE user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
);

DROP POLICY IF EXISTS "Allow users to insert their own chat messages" ON public.chat_messages;
CREATE POLICY "Allow users to insert their own chat messages"
ON public.chat_messages
FOR INSERT
WITH CHECK (
    session_id IN (
        SELECT session_id FROM public.chat_sessions WHERE user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
);

DROP POLICY IF EXISTS "Allow users to update their own chat messages" ON public.chat_messages;
CREATE POLICY "Allow users to update their own chat messages"
ON public.chat_messages
FOR UPDATE
USING (
    session_id IN (
        SELECT session_id FROM public.chat_sessions WHERE user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
)
WITH CHECK (
    session_id IN (
        SELECT session_id FROM public.chat_sessions WHERE user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
);

DROP POLICY IF EXISTS "Allow users to delete their own chat messages" ON public.chat_messages;
CREATE POLICY "Allow users to delete their own chat messages"
ON public.chat_messages
FOR DELETE
USING (
    session_id IN (
        SELECT session_id FROM public.chat_sessions WHERE user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
);


-- scenarios policies (all other tables follow same pattern)
DROP POLICY IF EXISTS "Allow users to select their own scenarios" ON public.scenarios;
CREATE POLICY "Allow users to select their own scenarios"
ON public.scenarios
FOR SELECT
USING (
    profile_id IN (
        SELECT profile_id FROM public.business_profiles WHERE user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
);

DROP POLICY IF EXISTS "Allow users to insert their own scenarios" ON public.scenarios;
CREATE POLICY "Allow users to insert their own scenarios"
ON public.scenarios
FOR INSERT
WITH CHECK (
    profile_id IN (
        SELECT profile_id FROM public.business_profiles WHERE user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
);

DROP POLICY IF EXISTS "Allow users to update their own scenarios" ON public.scenarios;
CREATE POLICY "Allow users to update their own scenarios"
ON public.scenarios
FOR UPDATE
USING (
    profile_id IN (
        SELECT profile_id FROM public.business_profiles WHERE user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
)
WITH CHECK (
    profile_id IN (
        SELECT profile_id FROM public.business_profiles WHERE user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
);

DROP POLICY IF EXISTS "Allow users to delete their own scenarios" ON public.scenarios;
CREATE POLICY "Allow users to delete their own scenarios"
ON public.scenarios
FOR DELETE
USING (
    profile_id IN (
        SELECT profile_id FROM public.business_profiles WHERE user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
);


-- simulations policies
DROP POLICY IF EXISTS "Allow users to select their own simulations" ON public.simulations;
CREATE POLICY "Allow users to select their own simulations"
ON public.simulations
FOR SELECT
USING (
    scenario_id IN (
        SELECT s.scenario_id FROM public.scenarios s
        JOIN public.business_profiles bp ON s.profile_id = bp.profile_id
        WHERE bp.user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
);

DROP POLICY IF EXISTS "Allow users to insert their own simulations" ON public.simulations;
CREATE POLICY "Allow users to insert their own simulations"
ON public.simulations
FOR INSERT
WITH CHECK (
    scenario_id IN (
        SELECT s.scenario_id FROM public.scenarios s
        JOIN public.business_profiles bp ON s.profile_id = bp.profile_id
        WHERE bp.user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
);

DROP POLICY IF EXISTS "Allow users to update their own simulations" ON public.simulations;
CREATE POLICY "Allow users to update their own simulations"
ON public.simulations
FOR UPDATE
USING (
    scenario_id IN (
        SELECT s.scenario_id FROM public.scenarios s
        JOIN public.business_profiles bp ON s.profile_id = bp.profile_id
        WHERE bp.user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
)
WITH CHECK (
    scenario_id IN (
        SELECT s.scenario_id FROM public.scenarios s
        JOIN public.business_profiles bp ON s.profile_id = bp.profile_id
        WHERE bp.user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
);

DROP POLICY IF EXISTS "Allow users to delete their own simulations" ON public.simulations;
CREATE POLICY "Allow users to delete their own simulations"
ON public.simulations
FOR DELETE
USING (
    scenario_id IN (
        SELECT s.scenario_id FROM public.scenarios s
        JOIN public.business_profiles bp ON s.profile_id = bp.profile_id
        WHERE bp.user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
);


-- simulation_reports policies
DROP POLICY IF EXISTS "Allow users to select their own simulation reports" ON public.simulation_reports;
CREATE POLICY "Allow users to select their own simulation reports"
ON public.simulation_reports
FOR SELECT
USING (
    simulation_id IN (
        SELECT sim.simulation_id FROM public.simulations sim
        JOIN public.scenarios s ON sim.scenario_id = s.scenario_id
        JOIN public.business_profiles bp ON s.profile_id = bp.profile_id
        WHERE bp.user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
);

DROP POLICY IF EXISTS "Allow users to insert their own simulation reports" ON public.simulation_reports;
CREATE POLICY "Allow users to insert their own simulation reports"
ON public.simulation_reports
FOR INSERT
WITH CHECK (
    simulation_id IN (
        SELECT sim.simulation_id FROM public.simulations sim
        JOIN public.scenarios s ON sim.scenario_id = s.scenario_id
        JOIN public.business_profiles bp ON s.profile_id = bp.profile_id
        WHERE bp.user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
);

DROP POLICY IF EXISTS "Allow users to update their own simulation reports" ON public.simulation_reports;
CREATE POLICY "Allow users to update their own simulation reports"
ON public.simulation_reports
FOR UPDATE
USING (
    simulation_id IN (
        SELECT sim.simulation_id FROM public.simulations sim
        JOIN public.scenarios s ON sim.scenario_id = s.scenario_id
        JOIN public.business_profiles bp ON s.profile_id = bp.profile_id
        WHERE bp.user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
)
WITH CHECK (
    simulation_id IN (
        SELECT sim.simulation_id FROM public.simulations sim
        JOIN public.scenarios s ON sim.scenario_id = s.scenario_id
        JOIN public.business_profiles bp ON s.profile_id = bp.profile_id
        WHERE bp.user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
);

DROP POLICY IF EXISTS "Allow users to delete their own simulation reports" ON public.simulation_reports;
CREATE POLICY "Allow users to delete their own simulation reports"
ON public.simulation_reports
FOR DELETE
USING (
    simulation_id IN (
        SELECT sim.simulation_id FROM public.simulations sim
        JOIN public.scenarios s ON sim.scenario_id = s.scenario_id
        JOIN public.business_profiles bp ON s.profile_id = bp.profile_id
        WHERE bp.user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
);


-- simulation_events policies
DROP POLICY IF EXISTS "Allow users to select their own simulation events" ON public.simulation_events;
CREATE POLICY "Allow users to select their own simulation events"
ON public.simulation_events
FOR SELECT
USING (
    simulation_id IN (
        SELECT sim.simulation_id FROM public.simulations sim
        JOIN public.scenarios s ON sim.scenario_id = s.scenario_id
        JOIN public.business_profiles bp ON s.profile_id = bp.profile_id
        WHERE bp.user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
);

DROP POLICY IF EXISTS "Allow users to insert their own simulation events" ON public.simulation_events;
CREATE POLICY "Allow users to insert their own simulation events"
ON public.simulation_events
FOR INSERT
WITH CHECK (
    simulation_id IN (
        SELECT sim.simulation_id FROM public.simulations sim
        JOIN public.scenarios s ON sim.scenario_id = s.scenario_id
        JOIN public.business_profiles bp ON s.profile_id = bp.profile_id
        WHERE bp.user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
);

DROP POLICY IF EXISTS "Allow users to update their own simulation events" ON public.simulation_events;
CREATE POLICY "Allow users to update their own simulation events"
ON public.simulation_events
FOR UPDATE
USING (
    simulation_id IN (
        SELECT sim.simulation_id FROM public.simulations sim
        JOIN public.scenarios s ON sim.scenario_id = s.scenario_id
        JOIN public.business_profiles bp ON s.profile_id = bp.profile_id
        WHERE bp.user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
)
WITH CHECK (
    simulation_id IN (
        SELECT sim.simulation_id FROM public.simulations sim
        JOIN public.scenarios s ON sim.scenario_id = s.scenario_id
        JOIN public.business_profiles bp ON s.profile_id = bp.profile_id
        WHERE bp.user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
);

DROP POLICY IF EXISTS "Allow users to delete their own simulation events" ON public.simulation_events;
CREATE POLICY "Allow users to delete their own simulation events"
ON public.simulation_events
FOR DELETE
USING (
    simulation_id IN (
        SELECT sim.simulation_id FROM public.simulations sim
        JOIN public.scenarios s ON sim.scenario_id = s.scenario_id
        JOIN public.business_profiles bp ON s.profile_id = bp.profile_id
        WHERE bp.user_id = auth.uid()
    )
    AND public.is_beta_access_valid(auth.uid())
);


-- =============================================================================
-- Admin Quick Reference
-- =============================================================================
-- View all beta users and their status:
--   SELECT * FROM list_beta_users();
--
-- Extend access for a user by 14 days:
--   SELECT * FROM extend_beta_access('user@example.com', 14);
--
-- Revoke access immediately:
--   SELECT * FROM revoke_beta_access('user@example.com');
--
-- Check if a specific user has valid access:
--   SELECT is_beta_access_valid('user-uuid-here');
-- =============================================================================
