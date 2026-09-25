-- Move beta access control data from user-editable user_metadata to
-- admin-controlled app_metadata. Run after migrations 004, 005 and 006.

-- Preserve existing expirations and invitation timestamps. Prefer values that
-- are already in app_metadata, then remove the user-editable copies.
UPDATE auth.users
SET raw_app_meta_data =
        COALESCE(raw_app_meta_data, '{}'::jsonb)
        || jsonb_strip_nulls(jsonb_build_object(
            'beta_access_expires_at', COALESCE(
                raw_app_meta_data->>'beta_access_expires_at',
                raw_user_meta_data->>'beta_access_expires_at'
            ),
            'beta_invited_at', COALESCE(
                raw_app_meta_data->>'beta_invited_at',
                raw_user_meta_data->>'beta_invited_at'
            )
        )),
    raw_user_meta_data = COALESCE(raw_user_meta_data, '{}'::jsonb)
        - 'beta_access_expires_at' - 'beta_invited_at',
    updated_at = NOW()
WHERE raw_user_meta_data ? 'beta_access_expires_at'
   OR raw_user_meta_data ? 'beta_invited_at';

CREATE OR REPLACE FUNCTION public.is_beta_access_valid(user_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, auth
AS $$
DECLARE
    expiry_text TEXT;
BEGIN
    SELECT raw_app_meta_data->>'beta_access_expires_at'
    INTO expiry_text
    FROM auth.users
    WHERE auth.users.id = $1;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    IF expiry_text IS NULL OR BTRIM(expiry_text) = '' THEN
        RETURN EXISTS (
            SELECT 1
            FROM public.beta_access_legacy_exemptions AS legacy
            WHERE legacy.user_id = $1
        );
    END IF;

    RETURN expiry_text::TIMESTAMPTZ > NOW();
EXCEPTION
    WHEN invalid_datetime_format OR datetime_field_overflow THEN
        RETURN FALSE;
END;
$$;

COMMENT ON FUNCTION public.is_beta_access_valid(UUID) IS
'Validate beta expiry from admin-controlled auth.users.raw_app_meta_data; allow existing legacy exemptions.';
REVOKE ALL ON FUNCTION public.is_beta_access_valid(UUID) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.is_beta_access_valid(UUID) TO authenticated, service_role;

CREATE OR REPLACE FUNCTION public.set_beta_access_expiration(
    user_id UUID,
    days_from_now INTEGER DEFAULT 7
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, auth
AS $$
DECLARE
    new_expiry TIMESTAMPTZ;
BEGIN
    IF $2 < 1 OR $2 > 3650 THEN
        RAISE EXCEPTION 'days_from_now must be between 1 and 3650';
    END IF;

    new_expiry := NOW() + make_interval(days => $2);
    UPDATE auth.users
    SET raw_app_meta_data = COALESCE(raw_app_meta_data, '{}'::jsonb)
            || jsonb_build_object(
                'beta_access_expires_at', new_expiry::TEXT,
                'beta_invited_at', COALESCE(raw_app_meta_data->>'beta_invited_at', NOW()::TEXT)
            ),
        updated_at = NOW()
    WHERE auth.users.id = $1;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'User % not found', $1;
    END IF;
END;
$$;
REVOKE ALL ON FUNCTION public.set_beta_access_expiration(UUID, INTEGER) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.set_beta_access_expiration(UUID, INTEGER) TO service_role;

CREATE OR REPLACE FUNCTION public.set_beta_access_expiry(
    user_email TEXT,
    expires_at TIMESTAMPTZ
)
RETURNS TABLE(user_id UUID, email TEXT, new_expires_at TIMESTAMPTZ)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, auth
AS $$
DECLARE
    target_user_id UUID;
BEGIN
    SELECT u.id INTO target_user_id
    FROM auth.users AS u
    WHERE lower(u.email) = lower($1);

    IF target_user_id IS NULL THEN
        RAISE EXCEPTION 'User with email % not found', $1;
    END IF;

    UPDATE auth.users AS u
    SET raw_app_meta_data = COALESCE(u.raw_app_meta_data, '{}'::jsonb)
            || jsonb_build_object(
                'beta_access_expires_at', $2::TEXT,
                'beta_invited_at', COALESCE(u.raw_app_meta_data->>'beta_invited_at', NOW()::TEXT)
            ),
        updated_at = NOW()
    WHERE u.id = target_user_id;

    RETURN QUERY SELECT target_user_id, $1, $2;
END;
$$;
REVOKE ALL ON FUNCTION public.set_beta_access_expiry(TEXT, TIMESTAMPTZ) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.set_beta_access_expiry(TEXT, TIMESTAMPTZ) TO service_role;

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
SET search_path = pg_catalog, public, auth
AS $$
DECLARE
    target_user_id UUID;
    app_metadata JSONB;
    old_expiry TIMESTAMPTZ;
    new_expiry TIMESTAMPTZ;
BEGIN
    IF $2 < 1 OR $2 > 3650 THEN
        RAISE EXCEPTION 'additional_days must be between 1 and 3650';
    END IF;

    SELECT u.id, COALESCE(u.raw_app_meta_data, '{}'::jsonb)
    INTO target_user_id, app_metadata
    FROM auth.users AS u
    WHERE lower(u.email) = lower($1);

    IF target_user_id IS NULL THEN
        RAISE EXCEPTION 'User with email % not found', $1;
    END IF;

    IF NULLIF(BTRIM(app_metadata->>'beta_access_expires_at'), '') IS NOT NULL THEN
        old_expiry := (app_metadata->>'beta_access_expires_at')::TIMESTAMPTZ;
        new_expiry := old_expiry + make_interval(days => $2);
    ELSE
        new_expiry := NOW() + make_interval(days => $2);
    END IF;

    UPDATE auth.users AS u
    SET raw_app_meta_data = app_metadata || jsonb_build_object(
            'beta_access_expires_at', new_expiry::TEXT,
            'beta_invited_at', COALESCE(app_metadata->>'beta_invited_at', NOW()::TEXT)
        ),
        updated_at = NOW()
    WHERE u.id = target_user_id;

    RETURN QUERY SELECT target_user_id, $1, old_expiry, new_expiry;
END;
$$;
REVOKE ALL ON FUNCTION public.extend_beta_access(TEXT, INTEGER) FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION public.revoke_beta_access(user_email TEXT)
RETURNS TABLE(user_id UUID, email TEXT, revoked_at TIMESTAMPTZ)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, auth
AS $$
DECLARE
    target_user_id UUID;
BEGIN
    SELECT u.id INTO target_user_id
    FROM auth.users AS u
    WHERE lower(u.email) = lower($1);

    IF target_user_id IS NULL THEN
        RAISE EXCEPTION 'User with email % not found', $1;
    END IF;

    UPDATE auth.users AS u
    SET raw_app_meta_data = COALESCE(u.raw_app_meta_data, '{}'::jsonb)
            || jsonb_build_object('beta_access_expires_at', NOW()::TEXT),
        updated_at = NOW()
    WHERE u.id = target_user_id;

    RETURN QUERY SELECT target_user_id, $1, NOW();
END;
$$;
REVOKE ALL ON FUNCTION public.revoke_beta_access(TEXT) FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION public.grant_beta_access_to_new_user(user_email TEXT)
RETURNS TABLE(user_id UUID, email TEXT, expires_at TIMESTAMPTZ, message TEXT)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, auth
AS $$
DECLARE
    target_user_id UUID;
    app_metadata JSONB;
    new_expiry TIMESTAMPTZ;
BEGIN
    SELECT u.id, COALESCE(u.raw_app_meta_data, '{}'::jsonb)
    INTO target_user_id, app_metadata
    FROM auth.users AS u
    WHERE lower(u.email) = lower($1);

    IF target_user_id IS NULL THEN
        RAISE EXCEPTION 'User with email % not found', $1;
    END IF;

    IF NULLIF(BTRIM(app_metadata->>'beta_access_expires_at'), '') IS NOT NULL THEN
        RETURN QUERY SELECT target_user_id, $1,
            (app_metadata->>'beta_access_expires_at')::TIMESTAMPTZ,
            'User already has beta access'::TEXT;
        RETURN;
    END IF;

    new_expiry := NOW() + INTERVAL '7 days';
    UPDATE auth.users AS u
    SET raw_app_meta_data = app_metadata || jsonb_build_object(
            'beta_access_expires_at', new_expiry::TEXT,
            'beta_invited_at', NOW()::TEXT
        ),
        updated_at = NOW()
    WHERE u.id = target_user_id;

    RETURN QUERY SELECT target_user_id, $1, new_expiry,
        'Beta access granted for 7 days'::TEXT;
END;
$$;
REVOKE ALL ON FUNCTION public.grant_beta_access_to_new_user(TEXT) FROM PUBLIC, anon, authenticated;

DROP FUNCTION IF EXISTS public.list_beta_users();
CREATE FUNCTION public.list_beta_users()
RETURNS TABLE(
    user_id UUID,
    email TEXT,
    created_at_gmt8 TEXT,
    expires_at_gmt8 TEXT,
    is_expired BOOLEAN,
    days_remaining INTEGER,
    invited_at_gmt8 TEXT
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, public, auth
AS $$
    SELECT u.id,
        u.email::TEXT,
        TO_CHAR(u.created_at AT TIME ZONE 'Asia/Kuala_Lumpur', 'YYYY-MM-DD HH24:MI:SS'),
        TO_CHAR((u.raw_app_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ AT TIME ZONE 'Asia/Kuala_Lumpur', 'YYYY-MM-DD HH24:MI:SS'),
        (u.raw_app_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ < NOW(),
        GREATEST(0, EXTRACT(DAY FROM ((u.raw_app_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ - NOW()))::INTEGER),
        TO_CHAR((u.raw_app_meta_data->>'beta_invited_at')::TIMESTAMPTZ AT TIME ZONE 'Asia/Kuala_Lumpur', 'YYYY-MM-DD HH24:MI:SS')
    FROM auth.users AS u
    WHERE NULLIF(BTRIM(u.raw_app_meta_data->>'beta_access_expires_at'), '') IS NOT NULL
    ORDER BY (u.raw_app_meta_data->>'beta_access_expires_at')::TIMESTAMPTZ ASC;
$$;
REVOKE ALL ON FUNCTION public.list_beta_users() FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION public.list_users_without_beta_access()
RETURNS TABLE(user_id UUID, email TEXT, created_at TIMESTAMPTZ, confirmed_at TIMESTAMPTZ)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, public, auth
AS $$
    SELECT u.id, u.email::TEXT, u.created_at, u.confirmed_at
    FROM auth.users AS u
    WHERE NULLIF(BTRIM(u.raw_app_meta_data->>'beta_access_expires_at'), '') IS NULL
      AND NOT EXISTS (
          SELECT 1
          FROM public.beta_access_legacy_exemptions AS legacy
          WHERE legacy.user_id = u.id
      )
      AND u.confirmed_at IS NOT NULL
    ORDER BY u.created_at DESC;
$$;
REVOKE ALL ON FUNCTION public.list_users_without_beta_access() FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.extend_beta_access(TEXT, INTEGER) TO service_role;
GRANT EXECUTE ON FUNCTION public.revoke_beta_access(TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION public.grant_beta_access_to_new_user(TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION public.list_beta_users() TO service_role;
GRANT EXECUTE ON FUNCTION public.list_users_without_beta_access() TO service_role;

COMMENT ON FUNCTION public.extend_beta_access(TEXT, INTEGER) IS
'Extend beta access from the current expiry (or now) using admin-controlled app_metadata.';
