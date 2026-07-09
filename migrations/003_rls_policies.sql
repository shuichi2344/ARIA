-- =============================================================================
-- ARIA — Row-Level Security Policies
-- =============================================================================
-- Run in: Supabase Dashboard → SQL Editor → New query → Run
-- Replaces the combined FOR ALL policy from migration 002.
-- Each table gets four explicit policies: SELECT / INSERT / UPDATE / DELETE
-- =============================================================================


-- ─────────────────────────────────────────────────────────────────────────────
-- business_profiles
-- Direct user_id column → straightforward ownership check
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.business_profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow users to select their own profiles"  ON public.business_profiles;
DROP POLICY IF EXISTS "Allow users to insert their own profiles"  ON public.business_profiles;
DROP POLICY IF EXISTS "Allow users to update their own profiles"  ON public.business_profiles;
DROP POLICY IF EXISTS "Allow users to delete their own profiles"  ON public.business_profiles;
-- also drop the old combined policy if it exists
DROP POLICY IF EXISTS "Users can manage their own profiles"       ON public.business_profiles;

-- Select
CREATE POLICY "Allow users to select their own profiles"
ON public.business_profiles
FOR SELECT
USING (user_id = auth.uid());

-- Insert
CREATE POLICY "Allow users to insert their own profiles"
ON public.business_profiles
FOR INSERT
WITH CHECK (user_id = auth.uid());

-- Update
CREATE POLICY "Allow users to update their own profiles"
ON public.business_profiles
FOR UPDATE
USING     (user_id = auth.uid())
WITH CHECK (user_id = auth.uid());

-- Delete
CREATE POLICY "Allow users to delete their own profiles"
ON public.business_profiles
FOR DELETE
USING (user_id = auth.uid());


-- ─────────────────────────────────────────────────────────────────────────────
-- chat_sessions
-- Direct user_id column
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.chat_sessions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow users to select their own chat sessions"  ON public.chat_sessions;
DROP POLICY IF EXISTS "Allow users to insert their own chat sessions"  ON public.chat_sessions;
DROP POLICY IF EXISTS "Allow users to update their own chat sessions"  ON public.chat_sessions;
DROP POLICY IF EXISTS "Allow users to delete their own chat sessions"  ON public.chat_sessions;
DROP POLICY IF EXISTS "Users can manage their own chat sessions"       ON public.chat_sessions;

-- Select
CREATE POLICY "Allow users to select their own chat sessions"
ON public.chat_sessions
FOR SELECT
USING (user_id = auth.uid());

-- Insert
CREATE POLICY "Allow users to insert their own chat sessions"
ON public.chat_sessions
FOR INSERT
WITH CHECK (user_id = auth.uid());

-- Update
CREATE POLICY "Allow users to update their own chat sessions"
ON public.chat_sessions
FOR UPDATE
USING     (user_id = auth.uid())
WITH CHECK (user_id = auth.uid());

-- Delete
CREATE POLICY "Allow users to delete their own chat sessions"
ON public.chat_sessions
FOR DELETE
USING (user_id = auth.uid());


-- ─────────────────────────────────────────────────────────────────────────────
-- chat_messages
-- No direct user_id — ownership via chat_sessions
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow users to select their own chat messages"  ON public.chat_messages;
DROP POLICY IF EXISTS "Allow users to insert their own chat messages"  ON public.chat_messages;
DROP POLICY IF EXISTS "Allow users to update their own chat messages"  ON public.chat_messages;
DROP POLICY IF EXISTS "Allow users to delete their own chat messages"  ON public.chat_messages;
DROP POLICY IF EXISTS "Users can manage their own chat messages"       ON public.chat_messages;

-- Select
CREATE POLICY "Allow users to select their own chat messages"
ON public.chat_messages
FOR SELECT
USING (
    session_id IN (
        SELECT session_id FROM public.chat_sessions WHERE user_id = auth.uid()
    )
);

-- Insert
CREATE POLICY "Allow users to insert their own chat messages"
ON public.chat_messages
FOR INSERT
WITH CHECK (
    session_id IN (
        SELECT session_id FROM public.chat_sessions WHERE user_id = auth.uid()
    )
);

-- Update
CREATE POLICY "Allow users to update their own chat messages"
ON public.chat_messages
FOR UPDATE
USING (
    session_id IN (
        SELECT session_id FROM public.chat_sessions WHERE user_id = auth.uid()
    )
)
WITH CHECK (
    session_id IN (
        SELECT session_id FROM public.chat_sessions WHERE user_id = auth.uid()
    )
);

-- Delete
CREATE POLICY "Allow users to delete their own chat messages"
ON public.chat_messages
FOR DELETE
USING (
    session_id IN (
        SELECT session_id FROM public.chat_sessions WHERE user_id = auth.uid()
    )
);


-- ─────────────────────────────────────────────────────────────────────────────
-- scenarios
-- Ownership via business_profiles
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.scenarios ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow users to select their own scenarios"  ON public.scenarios;
DROP POLICY IF EXISTS "Allow users to insert their own scenarios"  ON public.scenarios;
DROP POLICY IF EXISTS "Allow users to update their own scenarios"  ON public.scenarios;
DROP POLICY IF EXISTS "Allow users to delete their own scenarios"  ON public.scenarios;
DROP POLICY IF EXISTS "Users can manage their own scenarios"       ON public.scenarios;

-- Select
CREATE POLICY "Allow users to select their own scenarios"
ON public.scenarios
FOR SELECT
USING (
    profile_id IN (
        SELECT profile_id FROM public.business_profiles WHERE user_id = auth.uid()
    )
);

-- Insert
CREATE POLICY "Allow users to insert their own scenarios"
ON public.scenarios
FOR INSERT
WITH CHECK (
    profile_id IN (
        SELECT profile_id FROM public.business_profiles WHERE user_id = auth.uid()
    )
);

-- Update
CREATE POLICY "Allow users to update their own scenarios"
ON public.scenarios
FOR UPDATE
USING (
    profile_id IN (
        SELECT profile_id FROM public.business_profiles WHERE user_id = auth.uid()
    )
)
WITH CHECK (
    profile_id IN (
        SELECT profile_id FROM public.business_profiles WHERE user_id = auth.uid()
    )
);

-- Delete
CREATE POLICY "Allow users to delete their own scenarios"
ON public.scenarios
FOR DELETE
USING (
    profile_id IN (
        SELECT profile_id FROM public.business_profiles WHERE user_id = auth.uid()
    )
);


-- ─────────────────────────────────────────────────────────────────────────────
-- simulations
-- Ownership via scenarios → business_profiles
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.simulations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow users to select their own simulations"  ON public.simulations;
DROP POLICY IF EXISTS "Allow users to insert their own simulations"  ON public.simulations;
DROP POLICY IF EXISTS "Allow users to update their own simulations"  ON public.simulations;
DROP POLICY IF EXISTS "Allow users to delete their own simulations"  ON public.simulations;
DROP POLICY IF EXISTS "Users can manage their own simulations"       ON public.simulations;

-- Select
CREATE POLICY "Allow users to select their own simulations"
ON public.simulations
FOR SELECT
USING (
    scenario_id IN (
        SELECT s.scenario_id FROM public.scenarios s
        JOIN public.business_profiles bp ON s.profile_id = bp.profile_id
        WHERE bp.user_id = auth.uid()
    )
);

-- Insert
CREATE POLICY "Allow users to insert their own simulations"
ON public.simulations
FOR INSERT
WITH CHECK (
    scenario_id IN (
        SELECT s.scenario_id FROM public.scenarios s
        JOIN public.business_profiles bp ON s.profile_id = bp.profile_id
        WHERE bp.user_id = auth.uid()
    )
);

-- Update
CREATE POLICY "Allow users to update their own simulations"
ON public.simulations
FOR UPDATE
USING (
    scenario_id IN (
        SELECT s.scenario_id FROM public.scenarios s
        JOIN public.business_profiles bp ON s.profile_id = bp.profile_id
        WHERE bp.user_id = auth.uid()
    )
)
WITH CHECK (
    scenario_id IN (
        SELECT s.scenario_id FROM public.scenarios s
        JOIN public.business_profiles bp ON s.profile_id = bp.profile_id
        WHERE bp.user_id = auth.uid()
    )
);

-- Delete
CREATE POLICY "Allow users to delete their own simulations"
ON public.simulations
FOR DELETE
USING (
    scenario_id IN (
        SELECT s.scenario_id FROM public.scenarios s
        JOIN public.business_profiles bp ON s.profile_id = bp.profile_id
        WHERE bp.user_id = auth.uid()
    )
);


-- ─────────────────────────────────────────────────────────────────────────────
-- simulation_reports
-- Ownership via simulations → scenarios → business_profiles
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.simulation_reports ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow users to select their own simulation reports"  ON public.simulation_reports;
DROP POLICY IF EXISTS "Allow users to insert their own simulation reports"  ON public.simulation_reports;
DROP POLICY IF EXISTS "Allow users to update their own simulation reports"  ON public.simulation_reports;
DROP POLICY IF EXISTS "Allow users to delete their own simulation reports"  ON public.simulation_reports;
DROP POLICY IF EXISTS "Users can manage their own simulation reports"       ON public.simulation_reports;

-- Select
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
);

-- Insert
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
);

-- Update
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
)
WITH CHECK (
    simulation_id IN (
        SELECT sim.simulation_id FROM public.simulations sim
        JOIN public.scenarios s ON sim.scenario_id = s.scenario_id
        JOIN public.business_profiles bp ON s.profile_id = bp.profile_id
        WHERE bp.user_id = auth.uid()
    )
);

-- Delete
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
);


-- ─────────────────────────────────────────────────────────────────────────────
-- simulation_events
-- Ownership via simulations → scenarios → business_profiles
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.simulation_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow users to select their own simulation events"  ON public.simulation_events;
DROP POLICY IF EXISTS "Allow users to insert their own simulation events"  ON public.simulation_events;
DROP POLICY IF EXISTS "Allow users to update their own simulation events"  ON public.simulation_events;
DROP POLICY IF EXISTS "Allow users to delete their own simulation events"  ON public.simulation_events;
DROP POLICY IF EXISTS "Users can manage their own simulation events"       ON public.simulation_events;

-- Select
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
);

-- Insert
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
);

-- Update
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
)
WITH CHECK (
    simulation_id IN (
        SELECT sim.simulation_id FROM public.simulations sim
        JOIN public.scenarios s ON sim.scenario_id = s.scenario_id
        JOIN public.business_profiles bp ON s.profile_id = bp.profile_id
        WHERE bp.user_id = auth.uid()
    )
);

-- Delete
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
);


-- ─────────────────────────────────────────────────────────────────────────────
-- sales_records
-- Ownership via business_profiles
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.sales_records ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow users to select their own sales records"  ON public.sales_records;
DROP POLICY IF EXISTS "Allow users to insert their own sales records"  ON public.sales_records;
DROP POLICY IF EXISTS "Allow users to update their own sales records"  ON public.sales_records;
DROP POLICY IF EXISTS "Allow users to delete their own sales records"  ON public.sales_records;
DROP POLICY IF EXISTS "Users can manage their own sales records"       ON public.sales_records;

-- Select
CREATE POLICY "Allow users to select their own sales records"
ON public.sales_records
FOR SELECT
USING (
    profile_id IN (
        SELECT profile_id FROM public.business_profiles WHERE user_id = auth.uid()
    )
);

-- Insert
CREATE POLICY "Allow users to insert their own sales records"
ON public.sales_records
FOR INSERT
WITH CHECK (
    profile_id IN (
        SELECT profile_id FROM public.business_profiles WHERE user_id = auth.uid()
    )
);

-- Update
CREATE POLICY "Allow users to update their own sales records"
ON public.sales_records
FOR UPDATE
USING (
    profile_id IN (
        SELECT profile_id FROM public.business_profiles WHERE user_id = auth.uid()
    )
)
WITH CHECK (
    profile_id IN (
        SELECT profile_id FROM public.business_profiles WHERE user_id = auth.uid()
    )
);

-- Delete
CREATE POLICY "Allow users to delete their own sales records"
ON public.sales_records
FOR DELETE
USING (
    profile_id IN (
        SELECT profile_id FROM public.business_profiles WHERE user_id = auth.uid()
    )
);

-- =============================================================================
-- Verify: list all active policies
-- =============================================================================
-- SELECT tablename, policyname, cmd
-- FROM pg_policies
-- WHERE schemaname = 'public'
-- ORDER BY tablename, cmd;
