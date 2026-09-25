-- Grandfather accounts that already existed without a beta expiry when this
-- migration is applied. Users created later still need an explicit beta expiry.

CREATE TABLE IF NOT EXISTS public.beta_access_legacy_exemptions (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.beta_access_legacy_exemptions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.beta_access_legacy_exemptions FROM PUBLIC, anon, authenticated;

INSERT INTO public.beta_access_legacy_exemptions (user_id)
SELECT id
FROM auth.users
WHERE raw_user_meta_data IS NULL
   OR raw_user_meta_data->>'beta_access_expires_at' IS NULL
   OR BTRIM(raw_user_meta_data->>'beta_access_expires_at') = ''
ON CONFLICT (user_id) DO NOTHING;

CREATE OR REPLACE FUNCTION public.is_beta_access_valid(user_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, auth
AS $$
DECLARE
    expiry_text TEXT;
    target_user_id UUID := user_id;
BEGIN
    SELECT raw_user_meta_data->>'beta_access_expires_at'
    INTO expiry_text
    FROM auth.users
    WHERE id = target_user_id;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    -- No beta expiry means legacy access only for users grandfathered above.
    IF expiry_text IS NULL OR BTRIM(expiry_text) = '' THEN
        RETURN EXISTS (
            SELECT 1
            FROM public.beta_access_legacy_exemptions AS legacy
            WHERE legacy.user_id = target_user_id
        );
    END IF;

    RETURN expiry_text::TIMESTAMPTZ > NOW();
END;
$$;

COMMENT ON FUNCTION public.is_beta_access_valid(UUID) IS
'Allow grandfathered legacy accounts without beta expiry; enforce stored expirations for beta users.';
