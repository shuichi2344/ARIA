"""
Email sending for ARIA.

Password-reset and confirmation emails are now handled entirely by
Supabase Auth (Authentication > Settings > SMTP in the Dashboard).
This module is kept as a stub in case custom transactional emails
are needed in future.
"""

import logging

logger = logging.getLogger(__name__)


async def send_password_reset_email(to_email: str, reset_token: str) -> bool:  # noqa: ARG001
    """
    No-op stub — password reset emails are sent by Supabase SMTP automatically
    when ``request_password_reset`` is called on the SupabaseClient.

    This function is intentionally a no-op so existing call-sites don't break
    while the transition to Supabase Auth is in progress.
    """
    logger.debug(
        "send_password_reset_email called for %s — "
        "email delivery is handled by Supabase SMTP.",
        to_email,
    )
    return True
