"""
Email sending utility for ARIA.
Used for password reset emails.
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from aria.config import get_settings

logger = logging.getLogger(__name__)


async def send_password_reset_email(to_email: str, reset_token: str) -> bool:
    """
    Send a password reset email with a link containing the reset token.
    
    Args:
        to_email: Recipient email address
        reset_token: The unique reset token
    
    Returns:
        True if email sent successfully, False otherwise
    """
    settings = get_settings()
    
    smtp_host = settings.smtp_host
    smtp_port = settings.smtp_port
    smtp_user = settings.smtp_user
    smtp_password = settings.smtp_password
    from_email = settings.smtp_from_email or smtp_user
    app_url = settings.app_url

    if not smtp_host or not smtp_user:
        logger.warning("SMTP not configured — cannot send password reset email")
        # In development, log the reset link instead
        reset_link = f"{app_url}/auth/reset-password?token={reset_token}"
        logger.info(f"[DEV] Password reset link for {to_email}: {reset_link}")
        print(f"\n{'='*60}")
        print(f"📧 PASSWORD RESET (SMTP not configured — dev mode)")
        print(f"   Email: {to_email}")
        print(f"   Link:  {reset_link}")
        print(f"{'='*60}\n")
        return True  # Return True in dev so the flow continues

    reset_link = f"{app_url}/auth/reset-password?token={reset_token}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "ARIA — Reset Your Password"
    msg["From"] = from_email
    msg["To"] = to_email

    text_body = f"""Hi,

You requested a password reset for your ARIA account.

Click the link below to set a new password:
{reset_link}

This link expires in 1 hour. If you didn't request this, you can safely ignore this email.

— ARIA Team
"""

    html_body = f"""
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 480px; margin: 0 auto; padding: 2rem;">
  <h2 style="color: #1a1a2e; margin-bottom: 0.5rem;">Reset Your Password</h2>
  <p style="color: #555; line-height: 1.6;">
    You requested a password reset for your ARIA account. Click the button below to set a new password.
  </p>
  <a href="{reset_link}" style="display: inline-block; background: #7c2d3e; color: #fff; padding: 0.75rem 1.5rem; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 1.5rem 0;">
    Reset Password
  </a>
  <p style="color: #888; font-size: 0.85rem; margin-top: 1.5rem;">
    This link expires in 1 hour. If you didn't request this, you can safely ignore this email.
  </p>
  <hr style="border: none; border-top: 1px solid #eee; margin: 1.5rem 0;" />
  <p style="color: #aaa; font-size: 0.75rem;">ARIA — Agentic Retail Intelligence & Analytics</p>
</div>
"""

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, to_email, msg.as_string())
        logger.info(f"Password reset email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send password reset email to {to_email}: {e}")
        return False
