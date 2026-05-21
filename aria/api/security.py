"""
Security middleware and utilities for ARIA API.

Implements:
- Rate limiting (IP-based + user-based) via slowapi
- Input sanitization helpers
- Secure headers middleware

OWASP references:
- Rate Limiting: https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html
- Input Validation: https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html
"""

import re
import logging
from typing import Optional
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
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
    # Trust X-Forwarded-For only in production behind a known proxy
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP (client IP) from the chain
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

# General API: generous limits
GENERAL_RATE_LIMIT = "60/minute"      # 60 requests per minute per IP


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

# UUID v4 pattern for validating IDs
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
    re.IGNORECASE
)


def sanitize_text(text: str, max_length: int = 5000) -> str:
    """
    Sanitize user-provided text input.
    - Strips leading/trailing whitespace
    - Truncates to max_length
    - Removes null bytes
    - Does NOT strip HTML (that's for output encoding)
    """
    if not text:
        return ""
    # Remove null bytes (can cause issues in databases)
    text = text.replace("\x00", "")
    # Strip and truncate
    return text.strip()[:max_length]


def validate_uuid(value: str, field_name: str = "id") -> str:
    """
    Validate that a string is a valid UUID v4.
    Raises HTTPException if invalid.
    """
    if not value or not UUID_PATTERN.match(value):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name}: must be a valid UUID."
        )
    return value


def check_for_injection(text: str, field_name: str = "input") -> None:
    """
    Check for common injection patterns in user input.
    Raises HTTPException if suspicious content detected.
    
    Note: This is defense-in-depth. Primary protection should be
    parameterized queries and output encoding.
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
    # Basic email validation — RFC 5322 simplified
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email) or len(email) > 254:
        raise HTTPException(
            status_code=400,
            detail="Invalid email address format."
        )
    return email
