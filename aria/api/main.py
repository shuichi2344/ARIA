"""
FastAPI main application for ARIA platform.
"""

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
import uuid
from datetime import datetime, timezone
import logging
import sys

from aria.agents.customer_profiler import CustomerProfiler
from aria.database.supabase_client import SupabaseClient
from aria.auth.password import validate_password_strength
from aria.simulation.monte_carlo_cv import MonteCarloConfig
from aria.config import get_settings
from aria.api.security import (
    limiter,
    rate_limit_exceeded_handler,
    SecurityHeadersMiddleware,
    sanitize_text,
    validate_uuid,
    check_for_injection,
    validate_email_format,
    get_current_user,
    AUTH_RATE_LIMIT,
    FORGOT_PASSWORD_RATE_LIMIT,
    SIMULATION_RATE_LIMIT,
    SUGGEST_RATE_LIMIT,
    GENERAL_RATE_LIMIT,
)
from slowapi.errors import RateLimitExceeded

# Configure logging to show INFO level messages
# Force output to stdout so it appears in the terminal
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:     %(name)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True  # Override any existing configuration
)

# Set specific logger levels
logging.getLogger('aria.agents.scenario_suggestion').setLevel(logging.INFO)
logging.getLogger('aria.external.news_api').setLevel(logging.INFO)
logging.getLogger('aria.external.dosm').setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="ARIA API",
    description="Agentic Retail Intelligence & Analytics Platform",
    version="1.0.0"
)

# ---------------------------------------------------------------------------
# Security: Rate Limiting
# ---------------------------------------------------------------------------
# Attach rate limiter state to the app (required by slowapi)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# Security: Secure Response Headers
# ---------------------------------------------------------------------------
app.add_middleware(SecurityHeadersMiddleware)

# ---------------------------------------------------------------------------
# CORS: Restrict to known origins only
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",   # old vanilla web UI
        "http://127.0.0.1:8080",
        "http://localhost:3000",   # Next.js dev server
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)

# ---------------------------------------------------------------------------
# Pydantic models — strict validation, reject unexpected fields (OWASP Input Validation)
# ---------------------------------------------------------------------------

class UserRegister(BaseModel):
    """Registration request — email + strong password required."""
    model_config = {"extra": "forbid"}  # Reject unexpected fields
    email: str = Field(..., min_length=3, max_length=254, description="Valid email address")
    password: str = Field(..., min_length=6, max_length=128, description="Strong password")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return validate_email_format(v)


class UserLogin(BaseModel):
    """Login request — email + password."""
    model_config = {"extra": "forbid"}
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return validate_email_format(v)


class UserResponse(BaseModel):
    id: str
    email: str
    created_at: datetime
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    email_confirmed: Optional[bool] = None


class IncomeGroupInfo(BaseModel):
    """Income group information with percentage and description."""
    percentage: float
    description: str


class AgeGroupInfo(BaseModel):
    """Age group information with percentage."""
    percentage: float


class DemographicsResponse(BaseModel):
    """Response model for district demographics endpoint."""
    district: str
    income_distribution: Dict[str, IncomeGroupInfo]
    age_distribution: Dict[str, AgeGroupInfo]


class BusinessAnalyzeRequest(BaseModel):
    """Request model for AI customer analysis only (no user_id needed)."""
    model_config = {"extra": "forbid"}
    business_name: str = Field(..., min_length=1, max_length=200)
    business_type: str = Field(..., min_length=1, max_length=200)
    business_category_id: Optional[str] = Field(None, max_length=100)
    location: str = Field(..., min_length=1, max_length=200)
    district: Optional[str] = Field(None, max_length=100)
    years_operating: Optional[int] = Field(None, ge=0, le=200)
    unique_selling_points: Optional[str] = Field(None, max_length=2000)

    @field_validator("business_name", "business_type", "location")
    @classmethod
    def sanitize_fields(cls, v: str) -> str:
        check_for_injection(v, "business field")
        return sanitize_text(v, max_length=200)


class BusinessProfileCreate(BaseModel):
    """Request model for creating and saving a business profile (user_id required)."""
    model_config = {"extra": "forbid"}
    user_id: str = Field(..., min_length=1, max_length=100, description="ID of the authenticated user")
    business_name: str = Field(..., min_length=1, max_length=200)
    business_type: str = Field(..., min_length=1, max_length=200)
    business_category_id: Optional[str] = Field(None, max_length=100)
    location: str = Field(..., min_length=1, max_length=200)
    district: Optional[str] = Field(None, max_length=100)
    years_operating: Optional[int] = Field(None, ge=0, le=200)
    unique_selling_points: Optional[str] = Field(None, max_length=2000)
    price_range_min: Optional[float] = Field(None, ge=0, le=1000000)
    price_range_max: Optional[float] = Field(None, ge=0, le=1000000)
    customer_profile: Optional[Dict[str, Any]] = None


class CustomerProfileResponse(BaseModel):
    """Response model for customer profile analysis."""
    customer_type: str
    target_customers: str = ""
    price_range: Optional[Dict[str, float]] = None
    b2c_profile: Optional[Dict[str, Any]] = None
    b2b_profile: Optional[Dict[str, Any]] = None
    reasoning: str = ""


class BusinessProfileResponse(BaseModel):
    """Response model for business profile."""
    id: str
    business_name: str
    business_type: str
    location: str
    district: Optional[str]
    years_operating: Optional[int]
    unique_selling_points: Optional[str]
    price_range_min: Optional[float] = None
    price_range_max: Optional[float] = None
    customer_profile: Optional[Dict[str, Any]]
    created_at: datetime


# Health check endpoint
@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "ARIA API",
        "version": "1.0.0"
    }


@app.get("/api/health")
async def health_check():
    """Detailed health check."""
    # Check Supabase connection
    supabase_client = SupabaseClient()
    supabase_healthy = await supabase_client.health_check()
    
    return {
        "status": "healthy" if supabase_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "api": "operational",
            "database": "operational" if supabase_healthy else "unavailable",
            "llm": "operational"  # TODO: Add actual Ollama check
        }
    }


# ---------------------------------------------------------------------------
# Demographics endpoint
# ---------------------------------------------------------------------------

@app.get("/api/demographics/{district}", response_model=DemographicsResponse)
async def get_demographics(district: str) -> DemographicsResponse:
    """Return income and age distribution percentages for a Penang district."""
    from aria.external.dosm import DOSMClient

    dosm = DOSMClient()

    # Normalize kebab-case slugs (e.g. "timur-laut") to title case ("Timur Laut")
    if district not in dosm.PENANG_DISTRICTS:
        normalized = district.replace("-", " ").title()
        if normalized in dosm.PENANG_DISTRICTS:
            district = normalized
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid district '{district}'. Available: {dosm.PENANG_DISTRICTS}"
            )

    data = await dosm.get_demographics(district)

    return DemographicsResponse(
        district=district,
        income_distribution={
            level: IncomeGroupInfo(
                percentage=info["percentage"],
                description=info["description"]
            )
            for level, info in data["income_distribution"].items()
        },
        age_distribution={
            group: AgeGroupInfo(percentage=info["percentage"])
            for group, info in data["age_distribution"].items()
        }
    )


# ---------------------------------------------------------------------------
# Malaysia Holidays endpoint
# ---------------------------------------------------------------------------

@app.get("/api/holidays")
async def get_holidays(state: str = "pulau-pinang", year: Optional[int] = None):
    """
    Get Malaysian public holidays, school holidays, and exam schedules for a state.
    Defaults to Pulau Pinang. Returns upcoming holidays, school calendar, and exams.
    """
    from aria.external.malaysia_calendar import MalaysiaCalendarClient
    
    client = MalaysiaCalendarClient(state=state)
    try:
        upcoming = await client.get_upcoming_holidays(limit=5)
        all_holidays = await client.get_holidays(year=year)
        school_holidays = await client.get_school_holidays(year=year, group="B")
        exams = await client.get_exam_schedule(year=year)
        return {
            "state": state,
            "upcoming": upcoming,
            "holidays": all_holidays,
            "total": len(all_holidays),
            "school_holidays": school_holidays,
            "exams": exams,
        }
    except Exception as e:
        logger.error(f"Holiday API error: {e}")
        raise HTTPException(status_code=502, detail="Could not fetch holiday data")
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.post("/api/auth/register", response_model=UserResponse, status_code=201)
@limiter.limit(AUTH_RATE_LIMIT)
async def register(request: Request, body: UserRegister):
    """Register a new user account via Supabase Auth."""
    is_valid, error_msg = validate_password_strength(body.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    try:
        supabase_client = SupabaseClient()
        user = await supabase_client.register_user(body.email, body.password)
        return UserResponse(
            id=user["id"],
            email=user["email"],
            created_at=datetime.fromisoformat(user["created_at"].replace("Z", "+00:00")),
            access_token=user.get("access_token"),
            refresh_token=user.get("refresh_token"),
            email_confirmed=user.get("email_confirmed"),
        )
    except Exception as e:
        if "EMAIL_TAKEN" in str(e):
            raise HTTPException(status_code=409, detail="An account with this email already exists.")
        print(f"[ERROR] Registration failed: {e}")
        raise HTTPException(status_code=500, detail="Registration failed. Please try again.")


@app.post("/api/auth/login", response_model=UserResponse)
@limiter.limit(AUTH_RATE_LIMIT)
async def login(request: Request, body: UserLogin):
    """Login with email and password. Returns Supabase JWT tokens."""
    try:
        supabase_client = SupabaseClient()
        user = await supabase_client.login_user(body.email, body.password)
        return UserResponse(
            id=user["id"],
            email=user["email"],
            created_at=datetime.fromisoformat(user["created_at"].replace("Z", "+00:00")),
            access_token=user.get("access_token"),
            refresh_token=user.get("refresh_token"),
        )
    except Exception as e:
        if "INVALID_CREDENTIALS" in str(e):
            raise HTTPException(status_code=401, detail="Incorrect email or password.")
        if "EMAIL_NOT_CONFIRMED" in str(e):
            raise HTTPException(status_code=403, detail="EMAIL_NOT_CONFIRMED")
        print(f"[ERROR] Login failed: {e}")
        raise HTTPException(status_code=500, detail="Login failed. Please try again.")


class ChangePasswordRequest(BaseModel):
    model_config = {"extra": "forbid"}
    new_password: str = Field(..., min_length=6, max_length=128)


@app.post("/api/auth/change-password")
@limiter.limit(AUTH_RATE_LIMIT)
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Change the authenticated user's password.
    Requires a valid Supabase JWT in the Authorization header.
    The Bearer token is forwarded to Supabase Auth to perform the update.
    """
    is_valid, error_msg = validate_password_strength(body.new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # Extract the raw token from the request — Supabase needs it to update the user
    auth_header = request.headers.get("Authorization", "")
    access_token = auth_header.removeprefix("Bearer ").strip()

    try:
        supabase_client = SupabaseClient()
        await supabase_client.change_password(access_token, body.new_password)
        return {"success": True, "message": "Password updated successfully."}
    except Exception as e:
        if "INVALID_CREDENTIALS" in str(e):
            raise HTTPException(status_code=401, detail="Current session is invalid. Please log in again.")
        print(f"[ERROR] Change password failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to change password. Please try again.")


class ForgotPasswordRequest(BaseModel):
    model_config = {"extra": "forbid"}
    email: str = Field(..., min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return validate_email_format(v)


@app.post("/api/auth/forgot-password")
@limiter.limit(FORGOT_PASSWORD_RATE_LIMIT)
async def forgot_password(request: Request, body: ForgotPasswordRequest):
    """
    Trigger Supabase Auth to send a password-reset email via Supabase SMTP.
    Always returns success to prevent email enumeration.
    The reset link in the email contains a short-lived JWT that the frontend
    must extract and pass to /api/auth/reset-password.
    """
    settings = get_settings()
    reset_redirect = f"{settings.app_url}/auth/reset-password"

    try:
        supabase_client = SupabaseClient()
        await supabase_client.request_password_reset(
            email=body.email.strip().lower(),
            redirect_to=reset_redirect,
        )
    except Exception as e:
        logger.error(f"Forgot password error: {e}")

    # Always return success to prevent email enumeration
    return {"success": True, "message": "If an account with that email exists, a reset link has been sent."}


@app.get("/api/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user info from the JWT (no DB round-trip needed)."""
    return UserResponse(
        id=current_user["sub"],
        email=current_user.get("email", ""),
        created_at=datetime.fromtimestamp(current_user.get("iat", 0), tz=timezone.utc),
    )


@app.post("/api/business/analyze", response_model=CustomerProfileResponse)
@limiter.limit(SUGGEST_RATE_LIMIT)
async def analyze_customer_profile(request: Request, business_data: BusinessAnalyzeRequest):
    """
    Analyze business information and infer customer profile using AI.
    
    This endpoint runs the Customer Profiler agent to generate a customer
    profile based on the business information provided.
    """
    try:
        print(f"[DEBUG] Analyzing: {business_data.business_name} ({business_data.business_type})")
        
        # Initialize customer profiler
        profiler = CustomerProfiler()
        
        # Prepare business info for profiler
        business_info = {
            "business_type": business_data.business_type,
            "location": business_data.location,
            "district": business_data.district or "Unknown",
            "unique_selling_points": business_data.unique_selling_points or "Not specified"
        }
        
        print(f"[DEBUG] Calling LLM for analysis...")
        
        # Run AI analysis
        profile = await profiler.infer_profile(business_info)
        
        # Normalize customer_type: LLM may return "Both" but frontend expects "HYBRID"
        if profile.get('customer_type', '').lower() in ('both', 'mixed', 'hybrid'):
            profile['customer_type'] = 'HYBRID'
        
        # Compatibility: LLM might still return customer_description instead of target_customers
        if 'customer_description' in profile and 'target_customers' not in profile:
            profile['target_customers'] = profile.pop('customer_description')
        elif 'customer_description' in profile:
            profile.pop('customer_description')
        
        # Ensure target_customers exists
        if not profile.get('target_customers'):
            # Derive from b2c/b2b profile segments
            if profile.get('b2c_profile') and profile['b2c_profile'].get('target_segments'):
                profile['target_customers'] = ', '.join(profile['b2c_profile']['target_segments'])
            elif profile.get('b2b_profile') and profile['b2b_profile'].get('target_business_types'):
                profile['target_customers'] = ', '.join(profile['b2b_profile']['target_business_types'])
            else:
                profile['target_customers'] = 'general customers'
        
        # Remove deprecated fields
        profile.pop('confidence_level', None)
        
        print(f"[DEBUG] Analysis complete: {profile.get('customer_type')}")
        
        # Return the profile
        return CustomerProfileResponse(**profile)
        
    except Exception as e:
        print(f"[ERROR] Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze customer profile: {str(e)}"
        )


@app.post("/api/business/profile", response_model=BusinessProfileResponse)
async def create_business_profile(
    business_data: BusinessProfileCreate
):
    """
    Create a new business profile with AI-generated customer analysis.
    
    This endpoint:
    1. Runs customer profile analysis
    2. Saves the business profile to the database via Supabase REST API
    3. Returns the complete profile with AI analysis
    """
    try:
        # Initialize customer profiler
        profiler = CustomerProfiler()
        
        # Prepare business info for profiler
        business_info = {
            "business_type": business_data.business_type,
            "location": business_data.location,
            "district": business_data.district or "Unknown",
            "unique_selling_points": business_data.unique_selling_points or "Not specified"
        }
        
        print(f"[DEBUG] Running AI analysis for: {business_data.business_name}")
        
        # Run AI analysis
        customer_profile = await profiler.infer_profile(business_info)
        
        print(f"[DEBUG] AI analysis complete. Customer type: {customer_profile.get('customer_type')}")
        
        print(f"[DEBUG] Saving to database via Supabase REST API...")
        
        supabase_client = SupabaseClient()
        saved_profile = await supabase_client.create_business_profile(
            user_id=business_data.user_id,
            business_name=business_data.business_name,
            business_type=business_data.business_type,
            location=business_data.location,
            district=business_data.district,
            years_operating=business_data.years_operating,
            unique_selling_points=business_data.unique_selling_points,
            price_range_min=business_data.price_range_min,
            price_range_max=business_data.price_range_max,
            data_source="web_ui",
            customer_profile=business_data.customer_profile,
        )
        
        print(f"[DEBUG] Profile saved with ID: {saved_profile['profile_id']}")
        
        # Return response
        return BusinessProfileResponse(
            id=str(saved_profile['profile_id']),
            business_name=saved_profile['business_name'],
            business_type=saved_profile['business_type'],
            location=saved_profile['location'],
            district=saved_profile.get('district'),
            years_operating=saved_profile.get('years_operating'),
            unique_selling_points=saved_profile.get('unique_selling_points'),
            price_range_min=saved_profile.get('price_range_min'),
            price_range_max=saved_profile.get('price_range_max'),
            customer_profile=customer_profile,
            created_at=datetime.fromisoformat(saved_profile['created_at'].replace('Z', '+00:00'))
        )
        
    except Exception as e:
        print(f"[ERROR] Failed to create business profile: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create business profile: {str(e)}"
        )


@app.get("/api/business/profile/user/{user_id}", response_model=Optional[BusinessProfileResponse])
async def get_profile_by_user(user_id: str):
    """
    Return the most recent business profile for a user, or 404 if none exists.
    Used after login to decide whether to show onboarding or go straight to dashboard.
    """
    try:
        supabase_client = SupabaseClient()
        profiles = await supabase_client.list_business_profiles(user_id)
        if not profiles:
            raise HTTPException(status_code=404, detail="No profile found for this user")
        profile = profiles[0]
        
        # Reconstruct customer_profile from flat DB columns
        from aria.database.supabase_client import _reconstruct_customer_profile
        customer_profile = _reconstruct_customer_profile(profile)
        
        return BusinessProfileResponse(
            id=str(profile['profile_id']),
            business_name=profile['business_name'],
            business_type=profile['business_type'],
            location=profile['location'],
            district=profile.get('district'),
            years_operating=profile.get('years_operating'),
            unique_selling_points=profile.get('unique_selling_points'),
            price_range_min=profile.get('price_range_min'),
            price_range_max=profile.get('price_range_max'),
            customer_profile=customer_profile,
            created_at=datetime.fromisoformat(profile['created_at'].replace('Z', '+00:00'))
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/business/profile/{profile_id}", response_model=BusinessProfileResponse)
async def get_business_profile(profile_id: str):
    """Retrieve a business profile by ID."""
    try:
        supabase_client = SupabaseClient()
        profile = await supabase_client.get_business_profile(profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Business profile not found")
        return BusinessProfileResponse(
            id=str(profile['profile_id']),
            business_name=profile['business_name'],
            business_type=profile['business_type'],
            location=profile['location'],
            district=profile.get('district'),
            years_operating=profile.get('years_operating'),
            unique_selling_points=profile.get('unique_selling_points'),
            price_range_min=profile.get('price_range_min'),
            price_range_max=profile.get('price_range_max'),
            customer_profile=profile.get('customer_profile'),
            created_at=datetime.fromisoformat(profile['created_at'].replace('Z', '+00:00'))
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/business/profile/{profile_id}", response_model=BusinessProfileResponse)
async def update_business_profile(profile_id: str, business_data: BusinessProfileCreate):
    """Update an existing business profile."""
    try:
        supabase_client = SupabaseClient()
        updated = await supabase_client.update_business_profile(
            profile_id=profile_id,
            business_name=business_data.business_name,
            business_type=business_data.business_type,
            location=business_data.location,
            district=business_data.district,
            years_operating=business_data.years_operating,
            unique_selling_points=business_data.unique_selling_points,
            price_range_min=business_data.price_range_min,
            price_range_max=business_data.price_range_max,
            customer_profile=business_data.customer_profile,
        )
        return BusinessProfileResponse(
            id=str(updated['profile_id']),
            business_name=updated['business_name'],
            business_type=updated['business_type'],
            location=updated['location'],
            district=updated.get('district'),
            years_operating=updated.get('years_operating'),
            unique_selling_points=updated.get('unique_selling_points'),
            price_range_min=updated.get('price_range_min'),
            price_range_max=updated.get('price_range_max'),
            customer_profile=None,
            created_at=datetime.fromisoformat(updated['created_at'].replace('Z', '+00:00'))
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Chat History endpoints
# ---------------------------------------------------------------------------

class ChatMessageSave(BaseModel):
    model_config = {"extra": "forbid"}
    user_id: str = Field(..., min_length=1, max_length=100)
    profile_id: Optional[str] = Field(None, max_length=100)
    session_id: Optional[str] = Field(None, max_length=100)
    role: str = Field(..., pattern="^(user|aria)$")
    content: str = Field(..., min_length=1, max_length=50000)
    metadata: Optional[Dict[str, Any]] = None


@app.post("/api/chat/message")
async def save_chat_message(body: ChatMessageSave):
    """Save a chat message. Creates a session if session_id is not provided."""
    try:
        supabase = SupabaseClient()
        
        session_id = body.session_id
        if not session_id:
            session_id = await supabase.create_chat_session(body.user_id, body.profile_id)
        
        if session_id:
            await supabase.save_chat_message(
                session_id=session_id,
                role=body.role,
                content=body.content,
                metadata=body.metadata,
            )
        
        return {"session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat/session/{session_id}/messages")
async def get_chat_messages(session_id: str):
    """Retrieve all messages for a chat session."""
    try:
        supabase = SupabaseClient()
        messages = await supabase.list_chat_messages(session_id)
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


# ---------------------------------------------------------------------------
# Simulation endpoints
# ---------------------------------------------------------------------------

import asyncio
import json
from fastapi.responses import StreamingResponse
from aria.agents.scenario_suggestion import ScenarioSuggestionAgent

# In-memory store for active simulations (keyed by simulation_id string)
_active_sims: Dict[str, Dict[str, Any]] = {}

# Agent personality cache: reuse generated agents within the same session/profile
# Keyed by profile_id, stores agents with their LLM-generated personalities
# Invalidated when: demographics change, target segments change, or user starts new chat
_agent_cache: Dict[str, Dict[str, Any]] = {}


def _agent_cache_key(
    profile_id: str,
    agent_count: int,
    income_constraints: Optional[List[str]],
    age_constraints: Optional[List[str]],
    target_customer_constraints: Optional[List[str]],
    business_size_constraints: Optional[List[str]],
    b2b_percentage: Optional[int],
) -> str:
    """Build a cache fingerprint from simulation parameters that affect agent generation."""
    import hashlib
    parts = [
        profile_id,
        str(agent_count),
        ",".join(sorted(income_constraints or [])),
        ",".join(sorted(age_constraints or [])),
        ",".join(sorted(target_customer_constraints or [])),
        ",".join(sorted(business_size_constraints or [])),
        str(b2b_percentage or 0),
    ]
    return hashlib.md5("|".join(parts).encode()).hexdigest()


class ScenarioSuggestRequest(BaseModel):
    model_config = {"extra": "forbid"}
    user_question: str = Field(..., min_length=1, max_length=1000)
    business_profile: Dict[str, Any]
    use_external_context: bool = Field(default=False)
    chat_session_id: Optional[str] = Field(None, max_length=100)

    @field_validator("user_question")
    @classmethod
    def sanitize_question(cls, v: str) -> str:
        return sanitize_text(v, max_length=1000)


class SimulationStartRequest(BaseModel):
    model_config = {"extra": "forbid"}
    user_id: str = Field(..., min_length=1, max_length=100)
    profile_id: Optional[str] = Field(None, max_length=100)
    chat_session_id: Optional[str] = Field(None, max_length=100)
    scenario: Dict[str, Any]
    agent_count: int = Field(default=25, ge=15, le=100)
    income_constraints: Optional[List[str]] = None
    age_constraints: Optional[List[str]] = None
    target_customer_constraints: Optional[List[str]] = None
    business_size_constraints: Optional[List[str]] = None
    b2b_percentage: Optional[int] = Field(None, ge=0, le=100)
    
    # Monte Carlo CV parameters
    monte_carlo_enabled: bool = Field(default=True, description="Enable Monte Carlo convergence-based stopping")
    monte_carlo_min_runs: int = Field(default=5, ge=3, le=10, description="Minimum Monte Carlo runs before checking convergence")
    monte_carlo_max_runs: int = Field(default=30, ge=5, le=50, description="Maximum Monte Carlo runs (cost control)")
    monte_carlo_cv_threshold: float = Field(default=5.0, ge=1.0, le=15.0, description="CV threshold for convergence (%)")

    @field_validator("scenario")
    @classmethod
    def validate_scenario_parameters(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate scenario parameters, especially hours_extension for Extended Operating Hours."""
        scenario_type = v.get("scenario_type", "")
        parameters = v.get("parameters", {})
        
        # Validate Extended Operating Hours scenario
        if scenario_type == "operating_hours_change" and "hours_extension" in parameters:
            hours = parameters["hours_extension"]
            
            # Must be a number
            if not isinstance(hours, (int, float)):
                raise ValueError("hours_extension must be a number")
            
            # Must be a positive integer
            if hours <= 0:
                raise ValueError("hours_extension must be a positive number (greater than 0)")
            
            if not float(hours).is_integer():
                raise ValueError("hours_extension must be a whole number (integer)")
            
            # Convert to int to ensure it's stored as integer
            parameters["hours_extension"] = int(hours)
        
        return v


@app.post("/api/simulation/suggest")
@limiter.limit(SUGGEST_RATE_LIMIT)
async def suggest_scenarios(request: Request, body: ScenarioSuggestRequest):
    """
    Analyse the user's question and return suggested simulation scenarios.
    """
    try:
        agent = ScenarioSuggestionAgent()

        result = await agent.analyze_question(
            business_profile=body.business_profile,
            user_question=body.user_question,
            use_external_context=body.use_external_context,
        )
        
        logger.info(f"Scenario analysis complete - {len(result.get('scenarios', []))} scenarios generated")
        
        return result
    except Exception as e:
        logger.error(f"Scenario analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/simulation/start")
@limiter.limit(SIMULATION_RATE_LIMIT)
async def start_simulation(request: Request, body: SimulationStartRequest):
    """
    Create agents from the business profile and start the simulation.
    Returns simulation_id and initial agent list.
    """
    try:
        sim_id = str(uuid.uuid4())

        # Get business profile — always prefer database (authoritative source)
        profile = {}
        
        if body.profile_id:
            # Fetch from database when profile_id is provided
            print(f"[INFO] Fetching business profile from database: {body.profile_id}")
            supabase_client = SupabaseClient()
            db_profile = await supabase_client.get_business_profile(body.profile_id)
            if db_profile:
                print(f"[DEBUG] Raw DB customer_type: {db_profile.get('customer_type')}")
                print(f"[DEBUG] Reconstructed customer_profile: {db_profile.get('customer_profile')}")
                profile = {
                    "business_name": db_profile.get("business_name", "Unknown Business"),
                    "name": db_profile.get("business_name", "Unknown Business"),  # Alias for consistency
                    "business_type": db_profile.get("business_type", "retail"),
                    "type": db_profile.get("business_type", "retail"),  # Alias for consistency
                    "location": db_profile.get("location", "Georgetown"),
                    "district": db_profile.get("district", "Timur Laut"),
                    "price_range_min": db_profile.get("price_range_min", 0.0),
                    "price_range_max": db_profile.get("price_range_max", 0.0),
                    "b2c_target_segments": db_profile.get("b2c_target_segments", []),
                    "b2b_target_types": db_profile.get("b2b_target_types", []),
                    "unique_selling_points": db_profile.get("unique_selling_points", ""),
                    "years_operating": db_profile.get("years_operating", 0),
                    "customer_profile": db_profile.get("customer_profile") or {},
                }
                print(f"[INFO] Loaded business profile: {profile['business_name']}")
                print(f"[INFO] Price range: RM{profile['price_range_min']:.2f} - RM{profile['price_range_max']:.2f}")
        
        # Fallback: use business_profile from scenario if DB fetch didn't populate profile
        if not profile:
            profile = body.scenario.get("business_profile") or {}
        
        customer_profile = profile.get("customer_profile") or {}
        customer_type = customer_profile.get("customer_type", "B2C")
        b2b = customer_profile.get("b2b_profile") or {}

        # Use constraint fields from request body
        # B2C: income levels and age groups
        income_levels = body.income_constraints or ["B40", "M40", "T20"]
        age_groups = body.age_constraints or ["20-29", "30-39", "40-49", "50-59", "60+"]
        
        # B2B: target customer types and business sizes
        target_customer_constraints = body.target_customer_constraints
        business_size_constraints = body.business_size_constraints
        
        print(f"[INFO] Customer Type: {customer_type}")

        # ─── Check agent personality cache ───
        # Reuse agents from previous simulation in the same chat if constraints match
        cache_key = _agent_cache_key(
            profile_id=body.profile_id or "",
            agent_count=body.agent_count,
            income_constraints=income_levels,
            age_constraints=age_groups,
            target_customer_constraints=target_customer_constraints,
            business_size_constraints=business_size_constraints,
            b2b_percentage=body.b2b_percentage,
        ) if body.profile_id else None

        cached = _agent_cache.get(cache_key) if cache_key else None
        if cached:
            print(f"[INFO] ♻️  Reusing cached agent personalities (cache key: {cache_key[:8]}...)")
            agents = cached["agents"]
            business_profile_dict = cached["business_profile"]
            
            # Reset per-simulation state on cached agents
            for agent in agents:
                agent["is_active"] = True
                agent["visited_this_week"] = False
                agent["spend_this_week"] = 0.0
                agent["last_decision"] = None
                agent["reasoning"] = None

            # Cancel any existing simulation for this profile
            stale_ids = [
                sid for sid, s in _active_sims.items()
                if s.get("profile_id") == body.profile_id and s.get("status") == "running"
            ]
            for stale_id in stale_ids:
                print(f"[INFO] Aborting previous simulation {stale_id} for same profile")
                _active_sims[stale_id]["status"] = "aborted"
                try:
                    _active_sims[stale_id]["events"].put_nowait(None)
                except Exception:
                    pass

            # Store simulation state and kick off
            _active_sims[sim_id] = {
                "sim_id":         sim_id,
                "scenario":       body.scenario,
                "business_profile": business_profile_dict,
                "profile_id":     body.profile_id,
                "chat_session_id": body.chat_session_id,
                "agents":         agents,
                "current_week":   0,
                "is_paused":      False,
                "status":         "running",
                "events":         asyncio.Queue(),
                "target_customer_constraints": target_customer_constraints,
                "b2b_percentage": body.b2b_percentage,
                "agents_cached":  True,  # Flag: skip LLM profile generation
                # Monte Carlo configuration
                "monte_carlo_enabled": body.monte_carlo_enabled,
                "monte_carlo_config": MonteCarloConfig(
                    min_runs=body.monte_carlo_min_runs,
                    max_runs=body.monte_carlo_max_runs,
                    cv_threshold=body.monte_carlo_cv_threshold,
                ) if body.monte_carlo_enabled else None,
            }

            asyncio.create_task(_run_simulation(sim_id))

            return {
                "simulation_id": sim_id,
                "agent_count": len(agents),
                "agents": agents,
            }

        print("\n" + "="*80)
        print("🚀 STARTING SIMULATION WITH LLM-ENHANCED AGENTS")
        print("="*80)
        print(f"Simulation ID: {sim_id}")
        print(f"Agent Count: {body.agent_count}")
        print(f"Scenario: {body.scenario.get('scenario_type', 'unknown')}")
        if customer_type == "B2B":
            print(f"B2B Constraints:")
            print(f"  - Target Types: {target_customer_constraints or 'all'}")
            print(f"  - Business Sizes: {business_size_constraints or 'all'}")
        else:
            print(f"Customer Profile Constraints:")
            print(f"  - Income Levels: {income_levels}")
            print(f"  - Age Groups: {age_groups}")
        print("="*80)

        # Generate agents using IPF synthetic population + LLM profiles
        from aria.population.synthetic_population import SyntheticPopulationGenerator
        
        print("\n📊 PHASE 1: Generating Synthetic Population (IPF)")
        print("-" * 80)
        
        # Initialize generator
        pop_generator = SyntheticPopulationGenerator(use_ipf=True)
        
        # Build business_profile dict for IPF (basic fields)
        business_profile_dict = {
            "name": profile.get("business_name", profile.get("name", "Local Business")),
            "location": profile.get("location", "Georgetown"),
            "business_type": profile.get("business_type", profile.get("type", "retail")),
            "district": profile.get("district", "Timur Laut"),
            "price_range_min": profile.get("price_range_min", 0.0),
            "price_range_max": profile.get("price_range_max", 0.0),
            "b2c_target_segments": profile.get("b2c_target_segments", []),
            "b2b_target_types": profile.get("b2b_target_types", []),
            "unique_selling_points": profile.get("unique_selling_points", ""),
            "years_operating": profile.get("years_operating", 0),
            "customer_type": customer_type,
            "b2b_profile": b2b,
        }
        
        # Log business context for debugging
        print(f"[INFO] Business Context: {business_profile_dict['name']} ({business_profile_dict['business_type']}) in {business_profile_dict['location']}")
        
        # Branch: agent generation based on customer type
        if customer_type == "B2B":
            print(f"[INFO] B2B business detected — generating business customer agents")
            base_agents = _generate_b2b_agents(
                count=body.agent_count,
                b2b_profile=b2b,
                size_constraints=business_size_constraints,
                target_type_constraints=target_customer_constraints,
            )
            pop_result = {
                'agents': base_agents,
                'method_used': 'b2b_direct',
                'district': profile.get('district', ''),
                'convergence_report': None,
            }
        elif customer_type == "HYBRID":
            # HYBRID: split agents between B2B and B2C based on percentage
            b2b_pct = body.b2b_percentage if body.b2b_percentage is not None else 50
            b2b_pct = max(10, min(90, b2b_pct))  # Clamp to 10-90%
            b2b_count = max(1, round(body.agent_count * b2b_pct / 100))
            b2c_count = body.agent_count - b2b_count
            
            print(f"[INFO] HYBRID business detected — {b2b_pct}% B2B ({b2b_count} agents), {100-b2b_pct}% B2C ({b2c_count} agents)")
            
            # Generate B2B agents
            b2b_agents = _generate_b2b_agents(
                count=b2b_count,
                b2b_profile=b2b,
                size_constraints=business_size_constraints,
                target_type_constraints=target_customer_constraints,
            )
            for agent in b2b_agents:
                agent['customer_segment'] = 'B2B'
            
            # Generate B2C agents using IPF
            b2c_pop_result = await pop_generator.generate_population(
                business_profile=business_profile_dict,
                count=b2c_count,
                income_constraints=income_levels,
                age_constraints=age_groups
            )
            b2c_agents = b2c_pop_result['agents']
            for agent in b2c_agents:
                agent['customer_segment'] = 'B2C'
            
            # Combine both
            base_agents = b2b_agents + b2c_agents
            pop_result = {
                'agents': base_agents,
                'method_used': 'hybrid',
                'district': profile.get('district', ''),
                'convergence_report': b2c_pop_result.get('convergence_report'),
            }
        else:
            # B2C: use IPF synthetic population with demographic constraints
            pop_result = await pop_generator.generate_population(
                business_profile=business_profile_dict,
                count=body.agent_count,
                income_constraints=income_levels,
                age_constraints=age_groups
            )
        
        print(f"✓ Generated {len(pop_result['agents'])} base agents")
        print(f"  Method: {pop_result['method_used']}")
        print(f"  District: {pop_result.get('district', 'Unknown')}")
        if pop_result.get('convergence_report'):
            conv = pop_result['convergence_report']
            print(f"  IPF Convergence: {conv['confidence_score']:.1f}% confidence")
        
        # Get base agents from IPF
        base_agents = pop_result["agents"]
        
        print("\n🧠 PHASE 2: Generating LLM Personality Profiles")
        print("-" * 80)
        
        # Skip LLM profile generation here - do it in background via SSE
        # so the frontend can show agents appearing one by one
        print(f"  Deferring LLM profile generation to background task (streamed to frontend)")
        
        profile_texts = [f"Generating personality..." for _ in base_agents]
        
        print(f"✓ Placeholder profiles created, real profiles will stream via SSE")
        
        print("\n🏷️  PHASE 3: Extracting Personality Types")
        print("-" * 80)
        
        # Use module-level _extract_personality_type (real extraction happens later
        # after LLM profiles are generated in _run_simulation)
        personality_types = [_extract_personality_type(profile) for profile in profile_texts]
        
        # Show distribution
        type_dist = {}
        for ptype in personality_types:
            type_dist[ptype] = type_dist.get(ptype, 0) + 1
        
        print(f"✓ Extracted {len(personality_types)} personality types")
        print(f"  Distribution: {dict(type_dist)}")
        
        print("\n👥 PHASE 4: Creating Final Agent Objects")
        print("-" * 80)
        
        # Combine IPF demographics + LLM personalities
        agents = []
        for i, (base_agent, profile_text, personality_type) in enumerate(
            zip(base_agents, profile_texts, personality_types)
        ):
            agents.append({
                "agent_id": i + 1,
                "persona_name": f"Customer {i + 1}",  # 1-based customer numbering
                
                # Demographics from IPF (data-driven, constrained by customer profile)
                "income_level": base_agent['income_level'],
                "age_range": base_agent['age_range'],
                "monthly_income_rm": base_agent.get('monthly_income_rm', 5000),
                "spending_pattern": base_agent.get('spending_pattern', {}),
                "loyalty_traits": base_agent.get('loyalty_traits', {}),
                "payment_preferences": base_agent.get('payment_preferences', {}),
                
                # Personality from LLM (narrative-driven, rich context)
                "profile_text": profile_text,
                "personality": profile_text,
                "personality_type": personality_type,
                
                # Behavioral attributes
                "is_active": True,
                "visited_this_week": False,
                "spend_this_week": 0.0,
                "last_decision": None,
                "reasoning": None,
            })
        
        print(f"✓ Created {len(agents)} complete agent objects")
        print(f"\n  Agent Distribution:")
        
        # Show distribution
        income_dist = {}
        age_dist = {}
        for agent in agents:
            income = agent['income_level']
            age = agent['age_range']
            income_dist[income] = income_dist.get(income, 0) + 1
            age_dist[age] = age_dist.get(age, 0) + 1
        
        print(f"    Income: {dict(income_dist)}")
        print(f"    Age: {dict(age_dist)}")
        
        print("\n" + "="*80)
        print("✅ AGENT GENERATION COMPLETE")
        print("="*80)
        print(f"Total Time: IPF + LLM")
        print(f"Ready to start simulation...")
        print("="*80 + "\n")
        
        print(f"[INFO] Generated {len(agents)} agents using IPF + LLM profiles")
        print(f"[INFO] Method: {pop_result['method_used']}, District: {pop_result.get('district', 'Unknown')}")
        if pop_result.get('convergence_report'):
            print(f"[INFO] IPF Convergence: {pop_result['convergence_report']['confidence_score']:.1f}% confidence")

        # Cancel any existing simulation for this profile to avoid Ollama contention
        stale_ids = [
            sid for sid, s in _active_sims.items()
            if s.get("profile_id") == body.profile_id and s.get("status") == "running"
        ]
        for stale_id in stale_ids:
            print(f"[INFO] Aborting previous simulation {stale_id} for same profile")
            _active_sims[stale_id]["status"] = "aborted"
            # Signal the SSE stream to close
            try:
                _active_sims[stale_id]["events"].put_nowait(None)
            except Exception:
                pass

        # Store simulation state
        _active_sims[sim_id] = {
            "sim_id":         sim_id,
            "scenario":       body.scenario,
            "business_profile": business_profile_dict,
            "profile_id":     body.profile_id,
            "chat_session_id": body.chat_session_id,
            "agents":         agents,
            "current_week":   0,
            "is_paused":      False,
            "status":         "running",
            "events":         asyncio.Queue(),
            "target_customer_constraints": target_customer_constraints,
            "b2b_percentage": body.b2b_percentage,
            "agents_cached":  False,
            "cache_key":      cache_key,  # For caching after LLM profiles are generated
            # Monte Carlo configuration
            "monte_carlo_enabled": body.monte_carlo_enabled,
            "monte_carlo_config": MonteCarloConfig(
                min_runs=body.monte_carlo_min_runs,
                max_runs=body.monte_carlo_max_runs,
                cv_threshold=body.monte_carlo_cv_threshold,
            ) if body.monte_carlo_enabled else None,
        }

        # Kick off background simulation task
        asyncio.create_task(_run_simulation(sim_id))

        return {
            "simulation_id": sim_id,
            "agent_count": len(agents),
            "agents": agents,
        }

    except Exception as e:
        print(f"[ERROR] Start simulation failed: {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/simulation/history/{profile_id}")
async def get_simulation_history(profile_id: str):
    """Get simulation history for a business profile from the database."""
    try:
        supabase_client = SupabaseClient()
        history = await supabase_client.list_simulation_history(profile_id)
        return {"history": history}
    except Exception as e:
        print(f"[ERROR] Failed to fetch simulation history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/simulation/history/{simulation_id}")
async def delete_simulation_history(simulation_id: str):
    """Delete a simulation from history."""
    try:
        supabase_client = SupabaseClient()
        success = await supabase_client.delete_simulation(simulation_id)
        if not success:
            raise HTTPException(status_code=404, detail="Simulation not found")
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/simulation/{sim_id}/stream")
async def stream_simulation(sim_id: str):
    """
    Server-Sent Events stream for real-time simulation updates.
    """
    if sim_id not in _active_sims:
        raise HTTPException(status_code=404, detail="Simulation not found")

    async def event_generator():
        sim = _active_sims[sim_id]
        q: asyncio.Queue = sim["events"]
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=30)
                if event is None:
                    break
                yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/simulation/{sim_id}/pause")
async def pause_simulation(sim_id: str):
    if sim_id not in _active_sims:
        raise HTTPException(status_code=404, detail="Simulation not found")
    _active_sims[sim_id]["is_paused"] = True
    return {"status": "paused"}


@app.post("/api/simulation/{sim_id}/resume")
async def resume_simulation(sim_id: str):
    if sim_id not in _active_sims:
        raise HTTPException(status_code=404, detail="Simulation not found")
    _active_sims[sim_id]["is_paused"] = False
    return {"status": "running"}


@app.post("/api/simulation/{sim_id}/cancel")
async def cancel_simulation(sim_id: str):
    """Cancel a running simulation. The background task will stop at the next check point."""
    if sim_id not in _active_sims:
        raise HTTPException(status_code=404, detail="Simulation not found")
    _active_sims[sim_id]["status"] = "aborted"
    try:
        _active_sims[sim_id]["events"].put_nowait(None)
    except Exception:
        pass
    logger.info(f"Simulation {sim_id} cancelled by client")
    return {"status": "cancelled"}


@app.post("/api/simulation/cache/clear")
async def clear_agent_cache(profile_id: Optional[str] = None):
    """
    Clear cached agent personalities.
    Called when user starts a new chat or changes business profile/demographics.
    
    If profile_id is provided, only clears cache entries for that profile.
    Otherwise clears all cached agents.
    """
    removed = 0
    if profile_id:
        # Cache keys are hashes that include profile_id, so clear all for this profile
        keys_to_remove = [
            key for key, cached in _agent_cache.items()
        ]
        for key in keys_to_remove:
            del _agent_cache[key]
        removed = len(keys_to_remove)
        logger.info(f"Cleared agent cache for profile {profile_id} ({removed} entries)")
    else:
        removed = len(_agent_cache)
        _agent_cache.clear()
        logger.info(f"Cleared all agent cache ({removed} entries)")
    return {"status": "cleared", "entries_removed": removed}


# ---------------------------------------------------------------------------
# Background simulation runner
# ---------------------------------------------------------------------------

import random


def _extract_personality_type(profile_text: str) -> str:
    """Extract personality type from LLM-generated profile text."""
    profile_lower = profile_text.lower()
    
    # Define personality type keywords (order matters - more specific first)
    type_keywords = {
        'university student': ['university student', 'uni student', 'college student', 'studying at', 'undergraduate'],
        'student': ['student', 'studying'],
        'foodie': ['foodie', 'food enthusiast', 'food lover', 'culinary', 'loves trying new food'],
        'influencer': ['influencer', 'social media', 'content creator', 'blogger', 'youtuber', 'tiktoker'],
        'fitness enthusiast': ['fitness', 'gym', 'workout', 'health-conscious', 'active lifestyle'],
        'parent': ['parent', 'father', 'mother', 'brings family', 'brings kids', 'family man', 'family woman'],
        'wfh employee': ['work from home', 'wfh', 'remote work', 'working remotely'],
        'entrepreneur': ['entrepreneur', 'business owner', 'own business', 'startup', 'runs a'],
        'freelancer': ['freelancer', 'freelance', 'self-employed', 'gig worker'],
        'tourist': ['tourist', 'traveler', 'visitor', 'passing through'],
        'young professional': ['young professional', 'fresh graduate', 'early career'],
        'professional': ['professional', 'executive', 'manager', 'engineer', 'developer', 'accountant', 'lawyer', 'doctor', 'office worker'],
        'retiree': ['retired', 'retiree', 'pensioner'],
        'homemaker': ['homemaker', 'housewife', 'stay-at-home'],
        'senior': ['senior citizen', 'elderly', 'older adult'],
        'employee': ['employee', 'working', 'works at', 'job at', 'office'],
    }
    
    # Check for matches
    for type_name, keywords in type_keywords.items():
        if any(keyword in profile_lower for keyword in keywords):
            return type_name
    
    # Default based on age if no match
    age_range = profile_text.split(',')[0] if ',' in profile_text else ''
    if '18-24' in age_range or '25-34' in age_range:
        return 'young professional'
    elif '35-44' in age_range or '45-54' in age_range:
        return 'professional'
    elif '55+' in age_range or '65+' in age_range:
        return 'senior'
    
    return 'customer'


async def _run_simulation(sim_id: str):
    """
    Main simulation entry point - handles Monte Carlo or single run.
    """
    sim = _active_sims[sim_id]
    
    # Check if Monte Carlo is enabled
    if sim.get("monte_carlo_enabled") and sim.get("monte_carlo_config"):
        await _run_simulation_with_monte_carlo(sim_id)
    else:
        # Single-run mode: run once, then finalize (DB save + report)
        result_data = await _run_simulation_single(sim_id)
        if result_data is None:
            return  # Simulation was aborted
        from aria.simulation.llm_agent_brain import LLMAgentBrain
        llm_brain = LLMAgentBrain()
        await _finalize_simulation(sim_id, result_data, llm_brain)


async def _run_simulation_with_monte_carlo(sim_id: str):
    """
    Runs simulation with Monte Carlo CV-based stopping.
    """
    sim = _active_sims[sim_id]
    config: MonteCarloConfig = sim["monte_carlo_config"]
    q: asyncio.Queue = sim["events"]
    
    logger.info(f"Starting Monte Carlo simulation: min={config.min_runs}, max={config.max_runs}, CV≤{config.cv_threshold}%")
    
    # Emit Monte Carlo start event
    await q.put({
        "type": "monte_carlo_start",
        "data": {
            "min_runs": config.min_runs,
            "max_runs": config.max_runs,
            "cv_threshold": config.cv_threshold,
        }
    })
    
    from aria.simulation.monte_carlo_cv import MonteCarloTracker, RunResult
    tracker = MonteCarloTracker(config)
    
    # Accumulate metrics across all runs for averaging
    all_run_metrics: List[Dict[str, Any]] = []
    # Accumulate per-group breakdown across all runs for averaging
    all_run_breakdowns: List[Dict[str, Dict[str, int]]] = []
    
    # Run multiple simulations until convergence
    for run_num in range(1, config.max_runs + 1):
        logger.info(f"Monte Carlo run {run_num}/{config.max_runs}...")
        
        # Reset agent state between runs (so each run starts fresh)
        if run_num > 1:
            for agent in sim["agents"]:
                agent["is_active"] = True
                agent["visited_this_week"] = False
                agent["spend_this_week"] = 0.0
                agent["last_decision"] = None
                agent["reasoning"] = None
            # Mark agents as cached so we don't regenerate LLM profiles
            sim["agents_cached"] = True
        
        # Emit run start event
        await q.put({
            "type": "monte_carlo_run_start",
            "data": {"run_number": run_num, "max_runs": config.max_runs}
        })
        
        # Run single simulation
        result_data = await _run_simulation_single(sim_id, run_number=run_num)
        
        # If simulation was aborted, stop the Monte Carlo loop
        if result_data is None:
            logger.info(f"Simulation {sim_id} was aborted — stopping Monte Carlo")
            return
        
        all_run_metrics.append(result_data)  # Accumulate all runs for averaging
        
        # Capture per-group breakdown for this run (before agents get reset next iteration)
        mesa_agents_snapshot = sim.get("_last_mesa_agents", [])
        is_price_scenario = sim.get("_last_is_price_scenario", False)
        run_breakdown: Dict[str, Dict[str, int]] = {}
        for ma in mesa_agents_snapshot:
            if is_price_scenario:
                group = ma.income_level
            else:
                group = getattr(ma, 'personality_type', 'customer')
            if group not in run_breakdown:
                run_breakdown[group] = {"total": 0, "visit": 0, "skip": 0, "churn": 0}
            run_breakdown[group]["total"] += 1
            decision = ma.last_decision or "visit"
            if decision in run_breakdown[group]:
                run_breakdown[group][decision] += 1
        all_run_breakdowns.append(run_breakdown)
        
        # Extract metrics
        visits = result_data.get('total_visits', 0)
        skips = result_data.get('total_skips', 0)
        churns = result_data.get('total_churned', 0)
        total_agents = visits + skips + churns
        
        # Create run result
        run_result = RunResult(
            run_number=run_num,
            visits=visits,
            skips=skips,
            churns=churns,
            churn_rate=(churns / total_agents * 100) if total_agents > 0 else 0.0,
            total_visits=visits,
            total_revenue=result_data.get('total_revenue', 0.0),
            active_agents=result_data.get('active_agents', total_agents - churns),
            metadata=result_data.get('metadata')
        )
        
        # Add to tracker
        should_stop = tracker.add_run(run_result)
        
        # Get status message
        status_msg = tracker.get_status_message()
        logger.info(f"Run {run_num}: {status_msg}")
        
        # Get current summary to check convergence
        current_summary = tracker.get_summary()
        
        # Emit progress event
        await q.put({
            "type": "monte_carlo_progress",
            "data": {
                "run_number": run_num,
                "wci": tracker.get_mean("wci") if tracker.get_mean("wci") else 0,
                "wci_cv": tracker.get_cv("wci") if tracker.get_cv("wci") else 0,
                "status": status_msg,
                "converged": current_summary.get('converged', False),
            }
        })
        
        # Check if we should stop
        if should_stop:
            if current_summary.get('converged'):
                logger.info(f"✓ Converged after {run_num} runs!")
            else:
                logger.info(f"⚠ Stopped at max runs ({run_num})")
            break
    
    # Get final summary
    summary = tracker.get_summary()
    actual_runs = summary['num_runs']
    
    logger.info(f"Monte Carlo complete: {actual_runs} runs, WCI={summary['wci']['mean']:.1f}±{summary['wci']['std_dev']:.1f}")
    
    # Store summary in sim state for report generation
    sim["monte_carlo_summary"] = summary
    sim["monte_carlo_total_runs"] = actual_runs
    sim["monte_carlo_converged"] = summary['converged']
    sim["monte_carlo_stopped_reason"] = summary['stopped_reason']
    
    # Emit Monte Carlo complete event
    await q.put({
        "type": "monte_carlo_complete",
        "data": {
            "summary": summary,
            "converged": summary['converged'],
            "total_runs": actual_runs,
            "wci_mean": summary['wci']['mean'],
            "wci_cv": summary['wci']['cv'],
        }
    })
    
    # Finalize: save to DB and generate report using AVERAGED metrics across all runs
    if all_run_metrics:
        num_runs = len(all_run_metrics)
        averaged_metrics = {
            "total_visits": round(sum(r.get("total_visits", 0) for r in all_run_metrics) / num_runs),
            "total_skips": round(sum(r.get("total_skips", 0) for r in all_run_metrics) / num_runs),
            "total_churned": round(sum(r.get("total_churned", 0) for r in all_run_metrics) / num_runs),
            "total_revenue": sum(r.get("total_revenue", 0.0) for r in all_run_metrics) / num_runs,
            "active_agents": round(sum(r.get("active_agents", 0) for r in all_run_metrics) / num_runs),
        }
        
        # Average the per-group breakdown across all runs
        averaged_breakdown: Dict[str, Dict[str, float]] = {}
        for run_bd in all_run_breakdowns:
            for group, counts in run_bd.items():
                if group not in averaged_breakdown:
                    averaged_breakdown[group] = {"total": 0.0, "visit": 0.0, "skip": 0.0, "churn": 0.0}
                for key in ("total", "visit", "skip", "churn"):
                    averaged_breakdown[group][key] += counts.get(key, 0)
        # Divide by number of runs to get averages
        for group in averaged_breakdown:
            for key in ("total", "visit", "skip", "churn"):
                averaged_breakdown[group][key] = round(averaged_breakdown[group][key] / num_runs)
        
        # Store averaged breakdown for _finalize_simulation to use
        sim["_averaged_breakdown"] = averaged_breakdown
        
        logger.info(f"Averaged metrics over {num_runs} runs: visits={averaged_metrics['total_visits']}, "
                    f"skips={averaged_metrics['total_skips']}, churns={averaged_metrics['total_churned']}, "
                    f"revenue=RM{averaged_metrics['total_revenue']:.2f}")
        
        from aria.simulation.llm_agent_brain import LLMAgentBrain
        llm_brain = LLMAgentBrain()
        await _finalize_simulation(sim_id, averaged_metrics, llm_brain)
    else:
        logger.error("Monte Carlo completed but no run data available — skipping finalization")


async def _run_simulation_single(sim_id: str, run_number: int = 1) -> Dict[str, Any]:
    """
    Runs the simulation as a single pass, pushing SSE events to the queue.
    Uses hybrid Mesa + LLM decisions.
    
    Args:
        sim_id: Simulation ID
        run_number: Run number (for Monte Carlo mode, default 1 for single run)
    
    Returns:
        Dictionary with simulation results (total_visits, total_skips, total_churned, total_revenue, active_agents)
    """
    sim = _active_sims[sim_id]
    sim["started_at"] = datetime.now(timezone.utc).isoformat()
    q: asyncio.Queue = sim["events"]
    agents = sim["agents"]
    scenario = sim["scenario"]
    business_profile = sim.get("business_profile", {})

    def _is_aborted() -> bool:
        return _active_sims.get(sim_id, {}).get("status") == "aborted"

    from aria.simulation.llm_agent_brain import LLMAgentBrain, _clean_response
    
    llm_brain = LLMAgentBrain()

    # Derive scenario modifier from type
    scenario_type = scenario.get("scenario_type", "")
    params        = scenario.get("parameters", {})
    
    # DEBUG: Log the actual scenario being used
    print(f"\n{'='*80}")
    print("🔍 SCENARIO DEBUG INFO")
    print(f"{'='*80}")
    print(f"Scenario Type: {scenario_type}")
    print(f"Scenario Description: {scenario.get('description', 'N/A')}")
    print(f"Parameters: {params}")
    print(f"{'='*80}\n")
    
    price_change  = params.get("price_change_percent", 0) / 100  # e.g. 0.10
    
    scenario_message = scenario.get("description", f"Business scenario: {scenario_type}")
    
    # ─── PHASE: Generate agent personalities (streamed to frontend) ───
    if sim.get("agents_cached"):
        # Agents already have LLM-generated profiles from cache — skip generation
        print(f"\n♻️  Using cached agent personalities ({len(agents)} agents)")
        await q.put({"type": "profile_generation_start", "data": {"total": len(agents)}})
        # Emit all profiles immediately so frontend shows them
        for idx, agent in enumerate(agents):
            await q.put({
                "type": "agent_profile_ready",
                "data": {
                    "agent_id": agent['agent_id'],
                    "profile_text": agent['profile_text'],
                    "progress": idx + 1,
                    "total": len(agents)
                }
            })
        await q.put({"type": "profile_generation_complete", "data": {"total": len(agents)}})
        print(f"✓ All {len(agents)} cached personalities emitted to frontend")
    else:
        # Generate fresh LLM personalities
        print(f"\n🧠 Generating agent personalities (streamed to frontend)...")
        await q.put({"type": "profile_generation_start", "data": {"total": len(agents)}})
        
        # Pre-assign personality types from target segments so we get diverse agents
        target_types = []
        b2c_segments = business_profile.get('b2c_target_segments', []) or []
        b2b_types = business_profile.get('b2b_target_types', []) or []
        target_types = b2c_segments + b2b_types
        
        # Apply target customer constraints from settings (user may have unchecked some or added new ones)
        sim_target_constraints = sim.get("target_customer_constraints")
        if sim_target_constraints:
            # Use the constraints directly — they represent the user's selected target types
            target_types = [t for t in sim_target_constraints if t.strip()]
        
        if target_types:
            # Distribute target types evenly across agents
            assigned_personalities = []
            for i in range(len(agents)):
                assigned_personalities.append(target_types[i % len(target_types)])
            # Shuffle so same types aren't all grouped together
            random.shuffle(assigned_personalities)
            print(f"  Pre-assigned personalities from target segments: {target_types}")
        else:
            assigned_personalities = [None] * len(agents)
            print(f"  No target segments set — LLM will generate freely")
        
        batch_size = 3
        for batch_start in range(0, len(agents), batch_size):
            if _is_aborted():
                print(f"[INFO] Simulation {sim_id} aborted during profile generation")
                return
            
            batch = agents[batch_start:batch_start + batch_size]
            batch_tasks = [
                llm_brain.generate_agent_profile(
                    age_range=agent['age_range'],
                    income_level=agent['income_level'],
                    location=business_profile.get('location', 'Georgetown'),
                    business_profile=business_profile,
                    assigned_personality=assigned_personalities[batch_start + j]
                )
                for j, agent in enumerate(batch)
            ]
            batch_results = await asyncio.gather(*batch_tasks)
            
            for i, profile_text in enumerate(batch_results):
                agent_idx = batch_start + i
                agents[agent_idx]['profile_text'] = profile_text
                agents[agent_idx]['personality'] = profile_text
                
                # Emit to frontend immediately
                await q.put({
                    "type": "agent_profile_ready",
                    "data": {
                        "agent_id": agents[agent_idx]['agent_id'],
                        "profile_text": profile_text,
                        "progress": agent_idx + 1,
                        "total": len(agents)
                    }
                })
                print(f"  ✓ Agent {agent_idx}: {profile_text[:60]}...")
        
        await q.put({"type": "profile_generation_complete", "data": {"total": len(agents)}})
        print(f"✓ All {len(agents)} personalities generated")
        
        # Set personality types: use pre-assigned type if available, otherwise extract from profile
        for i, agent in enumerate(agents):
            if assigned_personalities[i]:
                agent['personality_type'] = assigned_personalities[i]
            else:
                agent['personality_type'] = _extract_personality_type(agent['profile_text'])
        
        # Log updated personality distribution
        type_dist_updated = {}
        for agent in agents:
            ptype = agent['personality_type']
            type_dist_updated[ptype] = type_dist_updated.get(ptype, 0) + 1
        print(f"  Personality distribution: {dict(type_dist_updated)}")

        # ─── Cache the generated agents for reuse in same session ───
        cache_key = sim.get("cache_key")
        if cache_key:
            import copy
            _agent_cache[cache_key] = {
                "agents": copy.deepcopy(agents),
                "business_profile": business_profile,
            }
            print(f"[INFO] 💾 Cached {len(agents)} agent personalities (key: {cache_key[:8]}...)")
    
    # ─── Create Mesa model and agents ───
    from aria.simulation.mesa_model import ARIAModel
    from aria.simulation.customer_agent import CustomerAgent
    
    mesa_model = ARIAModel(
        scenario=scenario,
        archetypes=[],  # Not needed — agents are pre-built
        agent_count=len(agents),
        business_profile=business_profile
    )
    
    mesa_agents = []
    for agent_dict in agents:
        mesa_agent = CustomerAgent(
            unique_id=agent_dict['agent_id'],
            model=mesa_model,
            archetype={
                'income_level': agent_dict['income_level'],
                'age_range': agent_dict['age_range'],
                'spending_pattern': agent_dict.get('spending_pattern', {}),
                'loyalty_traits': agent_dict.get('loyalty_traits', {}),
                'base_susceptibility': agent_dict.get('base_susceptibility', 5.0),
            },
            llm_brain=llm_brain,
        )
        mesa_agent.profile_text = agent_dict['profile_text']
        mesa_agent.personality_type = agent_dict.get('personality_type', 'customer')
        mesa_agent.customer_segment = agent_dict.get('customer_segment', 'B2C')
        mesa_agents.append(mesa_agent)
        mesa_model.agents_list.append(mesa_agent)
    
    print(f"✓ Created {len(mesa_agents)} Mesa agents")
    
    # ─── Build social network (Mesa NetworkGrid) ───
    # ~40% of agents are "social" (have 1-3 connections), rest are standalone
    # ─── Build social network (income-weighted connections) ───
    # All agents participate. Connections are weighted by income similarity.
    social_network: Dict[int, List[int]] = {a.unique_id: [] for a in mesa_agents}
    
    # Group agents by income level for weighted connection building
    income_groups_map: Dict[str, List[int]] = {}
    for a in mesa_agents:
        level = a.income_level
        income_groups_map.setdefault(level, []).append(a.unique_id)
    
    # Each agent gets 2-4 connections, preferring same income level (70% same, 30% cross)
    for agent in mesa_agents:
        same_income_peers = [pid for pid in income_groups_map.get(agent.income_level, []) if pid != agent.unique_id]
        other_peers = [a.unique_id for a in mesa_agents if a.unique_id != agent.unique_id and a.income_level != agent.income_level]
        
        num_connections = random.randint(2, min(4, len(mesa_agents) - 1))
        num_same = min(int(num_connections * 0.7) + 1, len(same_income_peers))
        num_cross = min(num_connections - num_same, len(other_peers))
        
        chosen = []
        if same_income_peers:
            chosen += random.sample(same_income_peers, min(num_same, len(same_income_peers)))
        if other_peers and num_cross > 0:
            chosen += random.sample(other_peers, min(num_cross, len(other_peers)))
        
        for pid in chosen:
            if pid not in social_network[agent.unique_id]:
                social_network[agent.unique_id].append(pid)
            if agent.unique_id not in social_network[pid]:
                social_network[pid].append(agent.unique_id)
    
    avg_connections = sum(len(v) for v in social_network.values()) / max(len(mesa_agents), 1)
    print(f"✓ Social network: {len(mesa_agents)} agents, avg {avg_connections:.1f} connections each (income-weighted)")
    
    # ─── Start simulation ───
    print(f"\n[INFO] Scenario: {scenario_message}")
    print(f"[INFO] Price change: {price_change*100:.1f}%")
    print(f"[INFO] Using hybrid Mesa + LLM decisions (2-phase)")
    print("\n" + "="*80)
    print("🎬 SIMULATION STARTING")
    print("="*80)

    await q.put({"type": "week_start", "data": {"week": 1}})

    total_visits  = 0
    total_revenue = 0.0
    total_churned = 0
    agent_decisions = []

    scenario_context = {
        'scenario_type': scenario_type,
        'description': scenario.get('description', ''),
        'parameters': params,
    }

    # Lookup dict: unique_id → agent dict (avoids index-based access)
    agent_by_id: Dict[int, Dict] = {a['agent_id']: a for a in agents}

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 1: Independent decisions (no peer influence)
    # ═══════════════════════════════════════════════════════════════════════════
    print("\n── Phase 1: Independent Decisions ──")
    
    for mesa_agent in mesa_agents:
        if _is_aborted():
            print(f"[INFO] Simulation {sim_id} aborted during Phase 1")
            return
        
        if not mesa_agent.is_active:
            continue

        while sim.get("is_paused"):
            await asyncio.sleep(0.5)

        result = await mesa_agent.make_decision(
            scenario_context=scenario_context,
            business_context=business_profile,
            use_peer_influence=False  # Phase 1: no peers
        )
        
        decision = result["decision"]
        reasoning = result["message"]
        spend = result["spend_amount"]
        
        if decision == "visit" and spend <= 0:
            spend = _calc_spend(agent_by_id[mesa_agent.unique_id], price_change, business_profile)
            mesa_agent.spend_this_week = spend
        
        agent_decisions.append((mesa_agent.unique_id, decision, 0.0))
        
        # Update dict-based agent state
        agent_dict = agent_by_id[mesa_agent.unique_id]
        agent_dict["is_active"] = mesa_agent.is_active
        agent_dict["last_decision"] = decision
        agent_dict["reasoning"] = reasoning
        agent_dict["visited_this_week"] = mesa_agent.visited_this_week
        agent_dict["spend_this_week"] = mesa_agent.spend_this_week
        
        if decision == "churn":
            total_churned += 1
        elif decision == "visit":
            total_visits += 1
            total_revenue += mesa_agent.spend_this_week

        # Emit agent decision
        await q.put({
            "type": "agent_decision",
            "data": {
                "agent_id": mesa_agent.unique_id,
                "decision": decision,
                "reasoning": reasoning,
                "spend_amount": mesa_agent.spend_this_week,
            }
        })

    print(f"  Phase 1 complete: {total_visits} visit, {len(agents)-total_visits-total_churned} skip, {total_churned} churn")

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 2: Peer influence — hybrid (probability gate + LLM interaction)
    # Step 1: Rule-based gate determines WHO is susceptible to peer influence
    # Step 2: LLM decides HOW they respond (considering full scenario, not just price)
    # ═══════════════════════════════════════════════════════════════════════════
    is_price_scenario = scenario_type in ('price_change', 'pricing') or price_change != 0
    
    print("\n── Phase 2: Peer Influence (Hybrid: Gate + LLM) ──")
    
    # Emit phase label to frontend
    await q.put({
        "type": "phase_label",
        "data": {"label": "Peer Influence", "description": "Agents reconsider after hearing from peers"}
    })
    
    # Helper: determine if an agent is a B2B agent
    B2B_SIZES = {'Micro', 'Small', 'Medium'}
    def _is_b2b_agent(agent) -> bool:
        seg = getattr(agent, 'customer_segment', 'B2C')
        if seg == 'B2B':
            return True
        return agent.income_level in B2B_SIZES
    
    # Gate probability: determines who is open to reconsidering
    # For PRICE scenarios: scale by income level / business size and price severity
    # For NON-PRICE scenarios: scale by personality/lifestyle traits
    severity = min(abs(price_change) / 0.15, 2.0) if price_change != 0 else 1.0
    severity_factor = max(0.7, severity)
    
    if is_price_scenario:
        # Income-based gate probabilities — flat 20% for all income levels
        GATE_PROBABILITY = {
            ("B40", "negative"): 0.20,
            ("B40", "positive"): 0.20,
            ("M40", "negative"): 0.20,
            ("M40", "positive"): 0.20,
            ("T20", "negative"): 0.20,
            ("T20", "positive"): 0.20,
        }
    else:
        # Personality-based gate probabilities for non-price scenarios
        PERSONALITY_GATE = {
            ("influencer", "negative"): 0.65,
            ("influencer", "positive"): 0.60,
            ("foodie", "negative"): 0.55,
            ("foodie", "positive"): 0.55,
            ("university student", "negative"): 0.60,
            ("university student", "positive"): 0.55,
            ("student", "negative"): 0.55,
            ("student", "positive"): 0.50,
            ("fitness enthusiast", "negative"): 0.40,
            ("fitness enthusiast", "positive"): 0.45,
            ("parent", "negative"): 0.45,
            ("parent", "positive"): 0.40,
            ("tourist", "negative"): 0.50,
            ("tourist", "positive"): 0.55,
            ("freelancer", "negative"): 0.45,
            ("freelancer", "positive"): 0.40,
            ("wfh employee", "negative"): 0.40,
            ("wfh employee", "positive"): 0.45,
            ("young professional", "negative"): 0.45,
            ("young professional", "positive"): 0.45,
            ("employee", "negative"): 0.35,
            ("employee", "positive"): 0.35,
            ("professional", "negative"): 0.30,
            ("professional", "positive"): 0.35,
            ("entrepreneur", "negative"): 0.25,
            ("entrepreneur", "positive"): 0.30,
            ("homemaker", "negative"): 0.50,
            ("homemaker", "positive"): 0.45,
            ("retiree", "negative"): 0.40,
            ("retiree", "positive"): 0.30,
            ("senior", "negative"): 0.35,
            ("senior", "positive"): 0.25,
            ("customer", "negative"): 0.35,
            ("customer", "positive"): 0.35,
        }
    
    # B2B gate probabilities — flat 30/20/10% by business size
    B2B_GATE = {
        ("Micro", "negative"): 0.30,
        ("Micro", "positive"): 0.30,
        ("Small", "negative"): 0.20,
        ("Small", "positive"): 0.20,
        ("Medium", "negative"): 0.10,
        ("Medium", "positive"): 0.10,
    }
    
    def peer_pressure_multiplier(num_peers: int) -> float:
        if num_peers >= 3: return 1.3
        elif num_peers == 2: return 1.15
        return 1.0
    
    print(f"  {'Price severity' if is_price_scenario else 'Personality-based'} factor: {severity_factor:.2f}x (price_change={price_change*100:.0f}%)")
    
    reconsider_count = 0
    agents_evaluated = 0
    agents_sent_to_llm = 0
    
    for mesa_agent in mesa_agents:
        if _is_aborted():
            print(f"[INFO] Simulation {sim_id} aborted during Phase 2")
            return
        
        if not mesa_agent.is_active:
            continue
        
        peer_ids = social_network.get(mesa_agent.unique_id, [])
        if not peer_ids:
            continue
        
        current_decision = mesa_agent.last_decision
        
        if current_decision == "visit":
            relevant_peers = []
            influencing_peer_ids = []
            for pid in peer_ids:
                peer = mesa_agents[pid] if pid < len(mesa_agents) else None
                if peer and peer.last_decision in ('skip', 'churn') and peer.reasoning:
                    relevant_peers.append(peer)
                    influencing_peer_ids.append(pid)
            if not relevant_peers:
                continue
            direction = "negative"
            if _is_b2b_agent(mesa_agent):
                base_prob = B2B_GATE.get((mesa_agent.income_level, "negative"), 0.20)
            elif is_price_scenario:
                base_prob = GATE_PROBABILITY.get((mesa_agent.income_level, "negative"), 0.25)
            else:
                ptype = getattr(mesa_agent, 'personality_type', 'customer')
                base_prob = PERSONALITY_GATE.get((ptype, "negative"), 0.35)
            
        elif current_decision == "skip":
            relevant_peers = []
            influencing_peer_ids = []
            for pid in peer_ids:
                peer = mesa_agents[pid] if pid < len(mesa_agents) else None
                if peer and peer.last_decision == 'visit' and peer.reasoning:
                    relevant_peers.append(peer)
                    influencing_peer_ids.append(pid)
            if not relevant_peers:
                continue
            direction = "positive"
            if _is_b2b_agent(mesa_agent):
                base_prob = B2B_GATE.get((mesa_agent.income_level, "positive"), 0.15)
            elif is_price_scenario:
                base_prob = GATE_PROBABILITY.get((mesa_agent.income_level, "positive"), 0.25)
            else:
                ptype = getattr(mesa_agent, 'personality_type', 'customer')
                base_prob = PERSONALITY_GATE.get((ptype, "positive"), 0.35)
        else:
            continue
        
        agents_evaluated += 1
        num_influencers = len(influencing_peer_ids)
        gate_prob = min(0.75, base_prob * peer_pressure_multiplier(num_influencers))
        
        # GATE: Does this agent even consider their peers' opinions?
        passes_gate = random.random() < gate_prob
        
        if not passes_gate:
            agent_label = f"{mesa_agent.income_level}" if is_price_scenario else f"{getattr(mesa_agent, 'personality_type', 'customer')}"
            print(f"  Agent {mesa_agent.unique_id} ({agent_label}, {current_decision}): "
                  f"{num_influencers} {direction} peer(s), gate={gate_prob:.0%} → ignored peers")
            await q.put({
                "type": "peer_evaluation",
                "data": {
                    "agent_id": mesa_agent.unique_id,
                    "income_level": mesa_agent.income_level,
                    "personality_type": getattr(mesa_agent, 'personality_type', 'customer'),
                    "current_decision": current_decision,
                    "direction": direction,
                    "num_peers": num_influencers,
                    "probability": round(gate_prob * 100),
                    "flipped": False,
                }
            })
            continue
        
        # PASSED GATE — ask LLM how this agent responds to their peers
        agents_sent_to_llm += 1
        peer_messages = [p.reasoning for p in relevant_peers[:3]]
        
        is_b2b = _is_b2b_agent(mesa_agent)
        
        if is_b2b:
            # B2B: professional/industry language
            if direction == "negative":
                peer_context = f"""You already decided to continue ordering. But other businesses in your industry are saying:
{chr(10).join(f'- Industry contact: "{msg}"' for msg in peer_messages)}

They seem dissatisfied with this supplier. Does their experience concern you enough to pause orders?"""
            else:
                peer_context = f"""You decided to stop ordering. But other businesses you know are saying:
{chr(10).join(f'- Industry contact: "{msg}"' for msg in peer_messages)}

They seem satisfied with the supplier. Does hearing this make you reconsider?"""
            
            reconsider_prompt = f"""You are: {mesa_agent.profile_text}

Scenario: {scenario_message}
Your current decision: {current_decision.upper()}

{peer_context}

As a business, consider: switching costs, contract obligations, relationship value, and what your industry peers are experiencing.

Reply in EXACTLY this format (2 lines only):
Decision: visit OR skip OR churn
Message: [15-20 word message explaining your business decision after hearing from industry contacts]"""
        else:
            # B2C: casual/social language
            if direction == "negative":
                peer_context = f"""You already decided to VISIT. But your friends are saying:
{chr(10).join(f'- Friend: "{msg}"' for msg in peer_messages)}

They seem unhappy. Does their experience worry you enough to skip this time?"""
            else:
                peer_context = f"""You decided to SKIP. But your friends went and said:
{chr(10).join(f'- Friend: "{msg}"' for msg in peer_messages)}

They seem to have enjoyed it. Does hearing this make you want to give it a try?"""
            
            reconsider_prompt = f"""You are: {mesa_agent.profile_text}

Scenario: {scenario_message}
Your current decision: {current_decision.upper()}

{peer_context}

Based on YOUR personality, budget, and values — do you change your mind or stick with your decision?

Reply in EXACTLY this format (2 lines only):
Decision: visit OR skip OR churn
Message: [15-20 word message explaining your choice after hearing from friends]"""

        reconsider_response = await llm_brain.client.generate(
            prompt=reconsider_prompt,
            temperature=0.8,
            max_tokens=200
        )
        
        raw = _clean_response(reconsider_response['response'])
        new_decision = current_decision
        new_message = ""
        
        for line in raw.split('\n'):
            line_lower = line.strip().lower()
            if line_lower.startswith('decision:'):
                d = line_lower.replace('decision:', '').strip()
                if 'churn' in d:
                    new_decision = 'churn'
                elif 'skip' in d:
                    new_decision = 'skip'
                else:
                    new_decision = 'visit'
            elif line_lower.startswith('message:'):
                new_message = line.strip()[len('Message:'):].strip().strip('"').strip("'")
        
        flipped = new_decision != current_decision
        
        agent_label = f"{mesa_agent.income_level}" if is_price_scenario else f"{getattr(mesa_agent, 'personality_type', 'customer')}"
        print(f"  Agent {mesa_agent.unique_id} ({agent_label}, {current_decision}): "
              f"{num_influencers} {direction} peer(s), gate={gate_prob:.0%} PASSED → LLM says {new_decision} {'(CHANGED!)' if flipped else '(held)'}")
        
        # Emit evaluation event
        await q.put({
            "type": "peer_evaluation",
            "data": {
                "agent_id": mesa_agent.unique_id,
                "income_level": mesa_agent.income_level,
                "personality_type": getattr(mesa_agent, 'personality_type', 'customer'),
                "current_decision": current_decision,
                "direction": direction,
                "num_peers": num_influencers,
                "probability": round(gate_prob * 100),
                "flipped": flipped,
            }
        })
        
        if flipped:
            reconsider_count += 1
            old_spend = mesa_agent.spend_this_week
            
            mesa_agent.last_decision = new_decision
            mesa_agent.reasoning = new_message or f"Changed mind after hearing from friends."
            
            if new_decision == "churn":
                mesa_agent.is_active = False
                mesa_agent.visited_this_week = False
                mesa_agent.spend_this_week = 0.0
                total_churned += 1
                if current_decision == "visit":
                    total_visits -= 1
                    total_revenue -= old_spend
            elif new_decision == "skip":
                mesa_agent.visited_this_week = False
                mesa_agent.spend_this_week = 0.0
                if current_decision == "visit":
                    total_visits -= 1
                    total_revenue -= old_spend
            elif new_decision == "visit":
                mesa_agent.visited_this_week = True
                spend = _calc_spend(agent_by_id[mesa_agent.unique_id], price_change, business_profile)
                mesa_agent.spend_this_week = spend
                total_visits += 1
                total_revenue += spend
            
            # Update dict
            agent_dict = agent_by_id[mesa_agent.unique_id]
            agent_dict["is_active"] = mesa_agent.is_active
            agent_dict["last_decision"] = new_decision
            agent_dict["reasoning"] = mesa_agent.reasoning
            agent_dict["visited_this_week"] = mesa_agent.visited_this_week
            agent_dict["spend_this_week"] = mesa_agent.spend_this_week
            
            # Emit updated decision
            await q.put({
                "type": "agent_decision",
                "data": {
                    "agent_id": mesa_agent.unique_id,
                    "decision": new_decision,
                    "reasoning": mesa_agent.reasoning,
                    "spend_amount": mesa_agent.spend_this_week,
                }
            })
            
            # Emit peer influence edges
            influence_label = "encouraged to visit" if direction == "positive" else "discouraged from visiting"
            for pid in influencing_peer_ids:
                await q.put({
                    "type": "peer_influence",
                    "data": {
                        "from_agent_id": pid,
                        "to_agent_id": mesa_agent.unique_id,
                        "influence_type": influence_label,
                        "message": mesa_agents[pid].reasoning or "",
                    }
                })
    
    print(f"  Phase 2 complete: {agents_evaluated} evaluated, {agents_sent_to_llm} sent to LLM, {reconsider_count} changed their mind")
    
    # Build description with explanation if no agents were evaluated
    phase2_description = f"{agents_evaluated} agents evaluated, {reconsider_count} changed their mind"
    if agents_evaluated == 0:
        phase2_description = "No peer influence triggered — no agents had peers with opposing decisions to influence them."
    
    # Emit phase summary to frontend
    await q.put({
        "type": "phase_label",
        "data": {
            "label": "Peer Influence Complete",
            "description": phase2_description
        }
    })
    
    # Log results
    print(f"\n  Results:")
    print(f"    Visits: {total_visits}")
    print(f"    Revenue: RM {total_revenue:.2f}")
    print(f"    Churned: {total_churned}")
    print(f"    Active Agents: {sum(1 for a in agents if a['is_active'])}")
    
    # Show decision distribution
    if agent_decisions:
        visit_count = sum(1 for _, d, _ in agent_decisions if d == "visit")
        skip_count = sum(1 for _, d, _ in agent_decisions if d == "skip")
        churn_count = sum(1 for _, d, _ in agent_decisions if d == "churn")
        
        print(f"    Decision Distribution:")
        print(f"      Visit: {visit_count} ({visit_count/len(agent_decisions)*100:.0f}%)")
        print(f"      Skip: {skip_count} ({skip_count/len(agent_decisions)*100:.0f}%)")
        print(f"      Churn: {churn_count} ({churn_count/len(agent_decisions)*100:.0f}%)")

    # Emit summary (always emit even if later steps fail)
    active_count  = sum(1 for a in agents if a["is_active"])
    churned_total = len(agents) - active_count
    total_visits_final = sum(1 for a in agents if a.get("visited_this_week"))
    total_revenue_final = sum(a.get("spend_this_week", 0) for a in agents if a.get("visited_this_week"))
    await q.put({
        "type": "week_summary",
        "data": {
            "week":          1,
            "total_visits":  total_visits_final,
            "total_revenue": round(total_revenue_final, 2),
            "active_agents": active_count,
            "churned_agents": churned_total,
        }
    })
    await asyncio.sleep(0.1)  # Ensure SSE flushes before report generation

    sim["current_week"] = 1

    # Simulation complete
    print("\n" + "="*80)
    print("🏁 SIMULATION COMPLETE")
    print("="*80)
    
    active_final  = sum(1 for a in agents if a["is_active"])
    churned_final = len(agents) - active_final
    
    print(f"Final Results:")
    print(f"  Active Agents: {active_final}/{len(agents)}")
    print(f"  Churned: {churned_final}")
    print(f"  Retention Rate: {active_final/len(agents)*100:.1f}%")
    print("="*80 + "\n")
    
    # ─── Save mesa_agents to sim state for finalization ───
    # The simulation can be called multiple times in MC mode; the FINAL run's
    # mesa_agents will be the ones used to generate the report.
    sim["_last_mesa_agents"] = mesa_agents
    sim["_last_is_price_scenario"] = is_price_scenario
    
    # Return run results for Monte Carlo tracking
    return {
        "total_visits": total_visits,
        "total_skips": len(agents) - total_visits - total_churned,
        "total_churned": total_churned,
        "total_revenue": total_revenue,
        "active_agents": sum(1 for a in agents if a["is_active"]),
        "agents": agents,
    }


async def _finalize_simulation(sim_id: str, run_metrics: Dict[str, Any], llm_brain) -> None:
    """
    Finalize a simulation: save to database, generate report, emit completion event.
    
    Called after _run_simulation_single (single-run mode) or after the Monte Carlo
    loop completes (MC mode). Reads state from sim["_last_mesa_agents"] etc.
    
    Args:
        sim_id: Simulation ID
        run_metrics: Final run metrics (total_visits, total_skips, total_churned, total_revenue)
        llm_brain: LLM client for generating recommendations
    """
    sim = _active_sims[sim_id]
    q: asyncio.Queue = sim["events"]
    agents = sim["agents"]
    scenario = sim["scenario"]
    business_profile = sim.get("business_profile", {})
    scenario_type = scenario.get("scenario_type", "")
    params = scenario.get("parameters", {})
    
    mesa_agents = sim.get("_last_mesa_agents", [])
    is_price_scenario = sim.get("_last_is_price_scenario", False)
    
    # Use pre-computed averaged breakdown (from MC mode) if available,
    # otherwise compute from the last run's mesa_agents (single-run mode)
    averaged_breakdown = sim.get("_averaged_breakdown")
    
    total_visits = run_metrics.get("total_visits", 0)
    total_churned = run_metrics.get("total_churned", 0)
    total_revenue = run_metrics.get("total_revenue", 0.0)
    active_final = run_metrics.get("active_agents", sum(1 for a in agents if a["is_active"]))
    
    # ─── Save results to database ───
    sim_db_id = None
    try:
        supabase = SupabaseClient()
        profile_id = sim.get("profile_id")
        
        if profile_id:
            # Save scenario — include session_id in parameters for later retrieval
            scenario_params = dict(params)
            if sim.get("chat_session_id"):
                scenario_params["_session_id"] = sim["chat_session_id"]

            saved_scenario = await supabase.save_scenario(
                business_profile_id=profile_id,
                scenario_name=scenario.get('scenario_name', 'Simulation'),
                scenario_type=scenario_type,
                description=scenario.get('description', ''),
                parameters=scenario_params,
            )
            scenario_db_id = saved_scenario.get('scenario_id')
            
            # Save simulation record with Monte Carlo metadata
            mc_summary = sim.get("monte_carlo_summary")
            saved_sim = await supabase.save_simulation(
                scenario_id=scenario_db_id,
                agent_count=len(agents),
                status="completed",
                started_at=sim.get("started_at"),
                monte_carlo_enabled=sim.get("monte_carlo_enabled", False),
                monte_carlo_total_runs=sim.get("monte_carlo_total_runs", 1),
                monte_carlo_converged=sim.get("monte_carlo_converged"),
            )
            sim_db_id = saved_sim.get('simulation_id')
            
            # Save agent decision events
            events = []
            for mesa_agent in mesa_agents:
                events.append({
                    "simulation_id": sim_db_id,
                    "agent_id": mesa_agent.unique_id,
                    "income_level": mesa_agent.income_level,
                    "decision": mesa_agent.last_decision or "visit",
                    "reasoning": mesa_agent.reasoning or "",
                    "spend_amount": mesa_agent.spend_this_week,
                    "profile_text": mesa_agent.profile_text,
                })
            await supabase.save_simulation_events(sim_db_id, events)
            
            print(f"✓ Simulation results saved to database (sim_id: {sim_db_id})")
        else:
            print("⚠ No profile_id — skipping database save")
    except Exception as e:
        print(f"⚠ Failed to save simulation to database: {e}")
    
    # ─── Generate simulation report ───
    print("\n📊 Generating simulation report...")
    
    from aria.simulation.llm_agent_brain import _clean_response
    
    # Compute breakdown: use averaged breakdown (MC mode) or compute from mesa_agents (single-run)
    if averaged_breakdown:
        # MC mode: use pre-averaged breakdown from all runs
        breakdown_data = averaged_breakdown
        breakdown_label = "income" if is_price_scenario else "personality"
    elif is_price_scenario:
        income_breakdown = {}
        for mesa_agent in mesa_agents:
            level = mesa_agent.income_level
            if level not in income_breakdown:
                income_breakdown[level] = {"total": 0, "visit": 0, "skip": 0, "churn": 0}
            income_breakdown[level]["total"] += 1
            decision = mesa_agent.last_decision or "visit"
            if decision in income_breakdown[level]:
                income_breakdown[level][decision] += 1
        breakdown_data = income_breakdown
        breakdown_label = "income"
    else:
        personality_breakdown = {}
        for mesa_agent in mesa_agents:
            ptype = getattr(mesa_agent, 'personality_type', 'customer')
            if ptype not in personality_breakdown:
                personality_breakdown[ptype] = {"total": 0, "visit": 0, "skip": 0, "churn": 0}
            personality_breakdown[ptype]["total"] += 1
            decision = mesa_agent.last_decision or "visit"
            if decision in personality_breakdown[ptype]:
                personality_breakdown[ptype][decision] += 1
        breakdown_data = personality_breakdown
        breakdown_label = "personality"
    
    # Calculate risk metrics
    churn_rate = (total_churned / len(agents)) * 100 if agents else 0
    visit_rate = (total_visits / len(agents)) * 100 if agents else 0
    skip_count = len(agents) - total_visits - total_churned
    
    # Determine risk level
    if churn_rate >= 30:
        risk_level = "High"
    elif churn_rate >= 15:
        risk_level = "Medium"
    else:
        risk_level = "Low"
    
    # Generate LLM analysis, key reasons, and recommendations (single call)
    recommendations = []
    analysis_explanation = ""
    key_reasons = []
    try:
        reasoning_samples = []
        for mesa_agent in mesa_agents:
            if mesa_agent.reasoning and mesa_agent.last_decision in ('skip', 'churn'):
                if is_price_scenario:
                    reasoning_samples.append(f"[{mesa_agent.income_level}, {mesa_agent.last_decision}]: {mesa_agent.reasoning}")
                else:
                    ptype = getattr(mesa_agent, 'personality_type', 'customer')
                    reasoning_samples.append(f"[{ptype}, {mesa_agent.last_decision}]: {mesa_agent.reasoning}")
        
        if is_price_scenario:
            breakdown_text = f"""Income breakdown:
{chr(10).join(f"- {level}: {data['visit']} visit, {data['skip']} skip, {data['churn']} churn (out of {data['total']})" for level, data in breakdown_data.items())}"""
        else:
            breakdown_text = f"""Personality/Lifestyle breakdown:
{chr(10).join(f"- {ptype}: {data['visit']} visit, {data['skip']} skip, {data['churn']} churn (out of {data['total']})" for ptype, data in breakdown_data.items())}"""
        
        rec_prompt = f"""You are a business advisor for a Malaysian micro-business.

Business: {business_profile.get('name', 'Unknown')} ({business_profile.get('business_type', 'business')})
Location: {business_profile.get('location', 'Malaysia')}
Price range: RM{business_profile.get('price_range_min', 0):.0f}-RM{business_profile.get('price_range_max', 0):.0f}

Scenario tested: {scenario.get('description', scenario_type)}

Results:
- {total_visits} out of {len(agents)} customers would still visit ({visit_rate:.0f}%)
- {skip_count} would skip this time ({skip_count/len(agents)*100:.0f}%)
- {total_churned} would leave permanently ({churn_rate:.0f}% churn)
- Estimated revenue from visitors: RM{total_revenue:.2f}

{breakdown_text}

Sample customer reasoning (those who skipped or churned):
{chr(10).join(reasoning_samples[:10]) if reasoning_samples else "None - all customers visited."}

Respond in this EXACT format:

ANALYSIS:
[Write 2-3 sentences explaining WHY customers reacted this way. What patterns do you see? Which {"income segments" if is_price_scenario else "personality types/lifestyles"} are most affected and why? Be specific about the numbers.]

KEY REASONS:
1. [Top reason customers skipped or churned - one concise sentence]
2. [Second most common reason - one concise sentence]
3. [Third reason - one concise sentence]

RECOMMENDATIONS:
1. [actionable recommendation]
2. [actionable recommendation]
3. [actionable recommendation]"""

        rec_response = await llm_brain.client.generate(prompt=rec_prompt, temperature=0.7, max_tokens=900)
        rec_text = _clean_response(rec_response['response'])
        
        # Parse the three sections
        if 'ANALYSIS:' in rec_text and 'KEY REASONS:' in rec_text and 'RECOMMENDATIONS:' in rec_text:
            # Split into sections
            after_analysis = rec_text.split('KEY REASONS:')
            analysis_part = after_analysis[0].replace('ANALYSIS:', '').strip()
            after_reasons = after_analysis[1].split('RECOMMENDATIONS:')
            reasons_part = after_reasons[0].strip()
            recs_part = after_reasons[1].strip()
            
            analysis_explanation = analysis_part.replace('**', '')
            
            # Parse key reasons
            for line in reasons_part.split('\n'):
                line = line.strip()
                if line and line[0].isdigit():
                    cleaned = line.lstrip('0123456789').lstrip('.)')
                    cleaned = cleaned.strip().replace('**', '')
                    if cleaned:
                        key_reasons.append(cleaned)
            key_reasons = key_reasons[:3]
            
            # Parse recommendations
            recommendations = [line.strip() for line in recs_part.split('\n') if line.strip() and line.strip()[0].isdigit()]
        elif 'ANALYSIS:' in rec_text and 'RECOMMENDATIONS:' in rec_text:
            # Fallback: no KEY REASONS section found
            parts = rec_text.split('RECOMMENDATIONS:')
            analysis_part = parts[0].replace('ANALYSIS:', '').replace('KEY REASONS:', '').strip()
            recs_part = parts[1].strip()
            analysis_explanation = analysis_part.replace('**', '')
            recommendations = [line.strip() for line in recs_part.split('\n') if line.strip() and line.strip()[0].isdigit()]
        else:
            recommendations = [line.strip() for line in rec_text.split('\n') if line.strip() and line.strip()[0].isdigit()]
        
        if not recommendations:
            recommendations = [rec_text.replace('**', '')]
        
        print(f"✓ Analysis, key reasons ({len(key_reasons)}), and recommendations generated")
    except Exception as e:
        print(f"⚠ Failed to generate analysis: {e}")
        recommendations = ["Consider monitoring customer feedback closely after implementing this change."]
    
    # Build report object
    mc_summary = sim.get("monte_carlo_summary")
    mc_total_runs = sim.get("monte_carlo_total_runs", 1)

    # Build disclaimer text
    if mc_summary and mc_summary.get("converged"):
        ci = mc_summary["wci"].get("confidence_interval_95")
        ci_text = f" 95% CI: [{ci[0]:.1f}, {ci[1]:.1f}]." if ci else ""
        disclaimer = (
            f"Based on {mc_total_runs} runs × {len(agents)} AI agents "
            f"= {mc_total_runs * len(agents)} total simulations. "
            f"Results stabilized at {mc_summary['wci'].get('cv', 0):.2f}% variation.{ci_text} "
            f"Results are statistically verified, not predictive. Actual behavior may vary."
        )
    elif mc_summary:
        disclaimer = (
            f"Based on {mc_total_runs} runs × {len(agents)} AI agents. "
            f"Simulation reached maximum run limit. "
            f"Results are indicative, not predictive. Actual behavior may vary."
        )
    else:
        disclaimer = (
            f"Based on a single run of {len(agents)} AI agents. "
            f"Results are indicative, not predictive. Actual customer behavior may vary."
        )

    report = {
        "scenario": {
            "name": scenario.get('scenario_name', scenario_type),
            "description": scenario.get('description', ''),
            "type": scenario_type,
        },
        "risk_summary": {
            "risk_level": risk_level,
            "churn_rate": round(churn_rate, 1),
            "visit_rate": round(visit_rate, 1),
            "estimated_revenue": round(total_revenue, 2),
            "total_agents": len(agents),
            "churn_rate_std_dev": round(mc_summary["churns"]["std_dev"], 2) if mc_summary and mc_summary.get("churns", {}).get("std_dev") else None,
            "confidence_interval_95": mc_summary["wci"].get("confidence_interval_95") if mc_summary else None,
        },
        "monte_carlo": {
            "total_runs": mc_total_runs,
            "converged": mc_summary.get("converged", False),
            "stopped_reason": mc_summary.get("stopped_reason"),
            "wci_mean": round(mc_summary["wci"]["mean"], 2) if mc_summary else None,
            "wci_std_dev": round(mc_summary["wci"]["std_dev"], 2) if mc_summary else None,
            "wci_cv": round(mc_summary["wci"]["cv"], 2) if mc_summary and mc_summary["wci"].get("cv") else None,
            "confidence_interval_95": mc_summary["wci"].get("confidence_interval_95") if mc_summary else None,
            "run_by_run": [
                {
                    "run": r["run_number"],
                    "wci": round(r["wci"], 2),
                    "churn_rate": round((r["churns"] / len(agents)) * 100, 1) if len(agents) > 0 else 0,
                    "visits": r["visits"],
                    "skips": r["skips"],
                    "churns": r["churns"],
                }
                for r in mc_summary.get("runs", [])
            ] if mc_summary else [],
        } if mc_summary else None,
        "breakdown_type": breakdown_label,
        "archetype_breakdown": {
            level: {
                "total": data["total"],
                "visit_pct": round((data["visit"] / data["total"]) * 100, 1) if data["total"] > 0 else 0,
                "skip_pct": round((data["skip"] / data["total"]) * 100, 1) if data["total"] > 0 else 0,
                "churn_pct": round((data["churn"] / data["total"]) * 100, 1) if data["total"] > 0 else 0,
            }
            for level, data in breakdown_data.items()
        },
        "recommendations": recommendations,
        "analysis": analysis_explanation,
        "key_reasons": key_reasons,
        "disclaimer": disclaimer,
    }
    
    print(f"✓ Report generated (risk: {risk_level}, churn: {churn_rate:.1f}%)")
    
    # Save report to database
    if sim_db_id:
        try:
            await supabase.save_simulation_report(
                simulation_id=sim_db_id,
                report=report,
                monte_carlo_summary=mc_summary,
            )
            print(f"✓ Report saved to database")
        except Exception as e:
            print(f"⚠ Failed to save report: {e}")
    
    # Emit completion event to frontend
    await q.put({
        "type": "simulation_complete",
        "data": {
            "summary": (
                f"{active_final} of {len(agents)} agents remained active. "
                f"{total_churned} churned."
            ),
            "report": report,
        }
    })
    await q.put(None)  # Signal end of stream
    sim["status"] = "complete"


# ---------------------------------------------------------------------------
# Decision text helpers
# ---------------------------------------------------------------------------

def _generate_b2b_agents(
    count: int,
    b2b_profile: Dict,
    size_constraints: Optional[List[str]] = None,
    target_type_constraints: Optional[List[str]] = None,
) -> List[Dict]:
    """
    Generate B2B customer agents directly from b2b_profile data.
    Distributes by business size and target types, filtered by constraints.
    """
    segments = b2b_profile.get('target_business_types', ['Workshop', 'Retail Shop'])
    avg_transaction = b2b_profile.get('avg_transaction_rm', 500)
    purchase_frequency = b2b_profile.get('purchase_frequency', 'monthly')
    
    # Apply target type constraints
    if target_type_constraints:
        segments = [s for s in segments if s in target_type_constraints] or segments
    
    # Frequency multipliers for monthly spend calculation
    freq_multipliers = {
        'daily': 30, '2-3 times/week': 10, 'weekly': 4, 'bi-weekly': 2,
        'monthly': 1, 'quarterly': 0.33, 'yearly': 0.08, 'one-time': 1,
    }
    freq_mult = freq_multipliers.get(purchase_frequency, 1)
    
    # Available sizes from profile, filtered by constraints
    available_sizes = b2b_profile.get('business_size', ['Micro', 'Small', 'Medium'])
    if size_constraints:
        available_sizes = [s for s in available_sizes if s in size_constraints] or available_sizes
    
    # Distribute sizes evenly across available sizes
    size_dist = []
    for i in range(count):
        size_dist.append(available_sizes[i % len(available_sizes)])
    
    # Size spending multipliers
    size_mult = {'Micro': 0.6, 'Small': 1.0, 'Medium': 2.0}
    
    agents = []
    for i in range(count):
        size = size_dist[i] if i < len(size_dist) else 'Small'
        segment = segments[i % len(segments)] if segments else 'Business'
        monthly_spend = avg_transaction * freq_mult * size_mult.get(size, 1.0)
        monthly_spend *= random.uniform(0.8, 1.2)  # variance
        
        agents.append({
            'income_level': size,  # repurposed: business size
            'age_range': segment,  # repurposed: business segment
            'monthly_income_rm': monthly_spend,
            'spending_pattern': {
                'avg_spend_rm': avg_transaction,
                'frequency': purchase_frequency,
            },
            'loyalty_traits': {},
            'payment_preferences': {},
            'base_susceptibility': 5.0,
        })
    
    return agents


def _calc_spend(agent: Dict, price_change: float, business_profile: Optional[Dict] = None) -> float:
    """Calculate spending amount based on business price range and price change."""
    # B2B: use the agent's pre-computed monthly spend
    if business_profile and business_profile.get('customer_type') == 'B2B':
        monthly = agent.get('monthly_income_rm', 500)
        return round(monthly * (1 + price_change), 2)
    
    # B2C: Use business price range if available
    if business_profile:
        price_min = business_profile.get('price_range_min', 0)
        price_max = business_profile.get('price_range_max', 0)
        if price_min > 0 and price_max > 0:
            base = random.uniform(price_min, price_max)
            return round(base * (1 + price_change), 2)
    
    # Fallback: income-based estimate
    base = {"B40": 12, "M40": 25, "T20": 45}.get(agent.get("income_level", "M40"), 20)
    return round(base * (1 + price_change) * random.uniform(0.8, 1.2), 2)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
