"""
Security middleware and utilities for ARIA API.

Implements:
- Rate limiting (IP-based + user-based) via slowapi
- Input sanitization helpers
- Secure headers middleware
- Supabase JWT verification dependency

OWASP references:
- Rate Limiting: https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html
- Input Validation: https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html
"""

import re
import logging
from fastapi import Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rate Limiter Configuration
# ---------------------------------------------------------------------------

def _get_client_ip(request: Request) -> str:
    """
    Extract client IP, respecting X-Forwarded-For for reverse proxies.
    Falls back to direct connection IP.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


# Initialize rate limiter with in-memory storage (suitable for single-instance)
# For multi-instance deployments, switch to Redis: "redis://localhost:6379"
limiter = Limiter(
    key_func=_get_client_ip,
    default_limits=["200/minute"],  # Global default: 200 requests/min per IP
    storage_uri="memory://",
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Custom 429 response handler.
    Returns a clear, user-friendly error with Retry-After header.
    """
    retry_after = exc.detail.split("per")[1].strip() if "per" in exc.detail else "60"
    logger.warning(f"Rate limit exceeded for {_get_client_ip(request)}: {exc.detail}")
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests. Please slow down and try again shortly.",
            "retry_after": retry_after,
        },
        headers={"Retry-After": "60"},
    )


# ---------------------------------------------------------------------------
# Rate Limit Presets (use as decorators on endpoints)
# ---------------------------------------------------------------------------

# Auth endpoints: strict limits to prevent brute force
AUTH_RATE_LIMIT = "5/minute"          # 5 attempts per minute per IP
FORGOT_PASSWORD_RATE_LIMIT = "3/minute"  # 3 reset requests per minute

# Simulation endpoints: moderate limits (expensive LLM calls)
SIMULATION_RATE_LIMIT = "10/minute"   # 10 simulation starts per minute
SUGGEST_RATE_LIMIT = "15/minute"      # 15 scenario suggestions per minute

# ---------------------------------------------------------------------------
# Supabase JWT Verification
# ---------------------------------------------------------------------------

_http_bearer = HTTPBearer(auto_error=False)


async def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer)) -> dict:
    """
    FastAPI dependency — validates Supabase JWT from Authorization header
    and checks beta access expiration.

    Usage:
        @app.get("/api/protected")
        async def protected(user: dict = Depends(get_current_user)):
            return {"user_id": user["sub"]}

    Returns the validated user identity with:
        - sub: user UUID (Supabase user id)
        - email: user email
        - role: "authenticated"
        - created_at: account creation timestamp
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    token = credentials.credentials
    # Ask Supabase Auth to validate the token. Supabase projects can use either
    # legacy HS256 secrets or asymmetric signing keys (ES256/RS256); hard-coding
    # HS256 here rejects valid sessions from projects using the newer keys.
    from aria.database.supabase_client import SupabaseClient
    supabase_client = SupabaseClient()
    try:
        user = await supabase_client.get_authenticated_user(token)
    except Exception as exc:
        logger.warning("Supabase JWT validation failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    if not user or not user.get("id"):
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    payload = {
        "sub": user["id"],
        "email": user.get("email", ""),
        "role": "authenticated",
        "created_at": user.get("created_at"),
        "user_metadata": user.get("user_metadata") or {},
        "app_metadata": user.get("app_metadata") or {},
    }

    # Check beta access expiration
    user_id = payload.get("sub")
    if user_id:
        is_valid = await supabase_client.check_beta_access(user_id)
        if not is_valid:
            logger.warning(f"Beta access expired for user {user_id}")
            raise HTTPException(
                status_code=403,
                detail="BETA_ACCESS_EXPIRED"
            )

    return payload


# ---------------------------------------------------------------------------
# Secure Headers Middleware
# ---------------------------------------------------------------------------

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security headers to all responses.
    OWASP: https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # XSS protection (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Don't expose server info
        response.headers["Server"] = "ARIA"

        # Referrer policy — don't leak URLs to third parties
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy — disable unnecessary browser features
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        return response


# ---------------------------------------------------------------------------
# Input Sanitization Utilities
# ---------------------------------------------------------------------------

# Pattern to detect potential injection attempts in free-text fields
_DANGEROUS_PATTERNS = re.compile(
    r'(<script|javascript:|on\w+\s*=|data:text/html|<iframe|<object|<embed)',
    re.IGNORECASE
)

def sanitize_text(text: str, max_length: int = 5000) -> str:
    """
    Sanitize user-provided text input.
    - Strips leading/trailing whitespace
    - Truncates to max_length
    - Removes null bytes
    """
    if not text:
        return ""
    text = text.replace("\x00", "")
    return text.strip()[:max_length]


def check_for_injection(text: str, field_name: str = "input") -> None:
    """
    Check for common injection patterns in user input.
    Raises HTTPException if suspicious content detected.
    """
    if _DANGEROUS_PATTERNS.search(text):
        logger.warning(f"Potential injection attempt in {field_name}: {text[:100]}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid characters detected in {field_name}."
        )


def validate_email_format(email: str) -> str:
    """
    Validate email format. Returns normalized (lowercase, stripped) email.
    Raises HTTPException if invalid.
    """
    email = email.strip().lower()
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email) or len(email) > 254:
        raise HTTPException(
            status_code=400,
            detail="Invalid email address format."
        )
    return email
