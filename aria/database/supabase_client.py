"""
Supabase REST API client for database operations.
This is a fallback when direct PostgreSQL connection doesn't work.
"""

import aiohttp
import hashlib
import secrets
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from aria.config import get_settings


def _reconstruct_customer_profile(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Reconstruct customer_profile dict from flat DB columns."""
    customer_type = row.get('customer_type', 'B2C')
    if not customer_type:
        return None
    
    # Normalize: LLM/old data may use "Both" instead of "HYBRID"
    if customer_type.lower() in ('both', 'mixed'):
        customer_type = 'HYBRID'
    
    # Use new separate columns
    b2c_segments: list = row.get('b2c_target_segments') or []
    b2b_types: list = row.get('b2b_target_types') or []
    
    # Clean up whitespace in array values
    b2c_segments = [s.strip() for s in b2c_segments if s and s.strip()]
    b2b_types = [s.strip() for s in b2b_types if s and s.strip()]
    
    profile: Dict[str, Any] = {
        'customer_type': customer_type,
        'target_customers': ', '.join(b2c_segments) if b2c_segments else ', '.join(b2b_types),
    }
    
    if customer_type in ('B2C', 'HYBRID'):
        profile['b2c_profile'] = {
            'target_segments': b2c_segments or ['working professionals', 'students'],
            'typical_income_levels': ['B40', 'M40', 'T20'],
            'avg_transaction_rm': ((row.get('price_range_min') or 0) + (row.get('price_range_max') or 0)) / 2,
        }
    
    if customer_type in ('B2B', 'HYBRID'):
        profile['b2b_profile'] = {
            'target_business_types': b2b_types or [],
            'business_size': row.get('b2b_business_sizes') or [],
            'purchase_frequency': row.get('b2b_purchase_frequency') or 'monthly',
            'avg_transaction_rm': row.get('b2b_avg_transaction_rm') or 500,
            'decision_factors': row.get('b2b_decision_factors') or ['price', 'quality', 'reliability'],
        }
    
    return profile


def _hash_password(password: str) -> str:
    """Hash a password using SHA-256 with a random salt."""
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{hashed}"


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored hash."""
    try:
        salt, hashed = stored_hash.split(":", 1)
        return hashlib.sha256(f"{salt}{password}".encode()).hexdigest() == hashed
    except Exception:
        return False


class SupabaseClient:
    """Client for Supabase REST API operations."""
    
    def __init__(self):
        settings = get_settings()
        self.base_url = str(settings.supabase_url).rstrip('/')
        self.api_key = settings.supabase_key
        self.headers = {
            'apikey': self.api_key,
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        }

    # -------------------------------------------------------------------------
    # User auth methods
    # -------------------------------------------------------------------------

    async def register_user(self, email: str, password: str) -> Dict[str, Any]:
        """
        Register a new user.

        Returns:
            Dict with the created user data (id, email, created_at)
        Raises:
            Exception if email already exists or DB error
        """
        # Check if email already taken
        existing = await self.get_user_by_email(email)
        if existing:
            raise Exception("EMAIL_TAKEN")

        url = f"{self.base_url}/rest/v1/users"
        data = {
            "email": email.lower().strip(),
            "password_hash": _hash_password(password),
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=self.headers) as response:
                if response.status in [200, 201]:
                    result = await response.json()
                    user = result[0] if isinstance(result, list) else result
                    # Never return the password hash to callers
                    return {"id": user["user_id"], "email": user["email"], "created_at": user["created_at"]}
                else:
                    error_text = await response.text()
                    raise Exception(f"Supabase API error ({response.status}): {error_text}")

    async def login_user(self, email: str, password: str) -> Dict[str, Any]:
        """
        Verify credentials and return user data.

        Returns:
            Dict with user data (id, email, created_at)
        Raises:
            Exception("INVALID_CREDENTIALS") if email/password don't match
        """
        user = await self.get_user_by_email(email)
        if not user:
            raise Exception("INVALID_CREDENTIALS")

        if not _verify_password(password, user.get("password_hash", "")):
            raise Exception("INVALID_CREDENTIALS")

        return {"id": user["user_id"], "email": user["email"], "created_at": user["created_at"]}

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a user row by email (includes password_hash for internal use).
        """
        url = f"{self.base_url}/rest/v1/users"
        params = {"email": f"eq.{email.lower().strip()}", "select": "*"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=self.headers) as response:
                if response.status == 200:
                    result = await response.json()
                    return result[0] if result else None
                return None

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a user row by id (excludes password_hash).
        """
        url = f"{self.base_url}/rest/v1/users"
        params = {"user_id": f"eq.{user_id}", "select": "user_id,email,created_at"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=self.headers) as response:
                if response.status == 200:
                    result = await response.json()
                    if not result:
                        return None
                    row = result[0]
                    # Normalise to the 'id' key the API layer expects
                    return {"id": row["user_id"], "email": row["email"], "created_at": row["created_at"]}
                return None

    async def change_password(self, user_id: str, current_password: str, new_password: str) -> bool:
        """
        Change a user's password after verifying the current one.

        Returns:
            True if password was changed successfully
        Raises:
            Exception("INVALID_CREDENTIALS") if current password is wrong
            Exception("USER_NOT_FOUND") if user doesn't exist
        """
        # Fetch user with password hash
        url = f"{self.base_url}/rest/v1/users"
        params = {"user_id": f"eq.{user_id}", "select": "*"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=self.headers) as response:
                if response.status != 200:
                    raise Exception("USER_NOT_FOUND")
                result = await response.json()
                if not result:
                    raise Exception("USER_NOT_FOUND")
                user = result[0]

        # Verify current password
        if not _verify_password(current_password, user.get("password_hash", "")):
            raise Exception("INVALID_CREDENTIALS")

        # Update with new password hash
        new_hash = _hash_password(new_password)
        update_url = f"{self.base_url}/rest/v1/users?user_id=eq.{user_id}"
        headers = {**self.headers, "Prefer": "return=minimal"}

        async with aiohttp.ClientSession() as session:
            async with session.patch(update_url, json={"password_hash": new_hash}, headers=headers) as response:
                if response.status in [200, 204]:
                    return True
                error_text = await response.text()
                raise Exception(f"Failed to update password: {error_text}")

    async def create_password_reset_token(self, user_id: str, token: str, expires_at: str) -> bool:
        """Store a password reset token in the database."""
        url = f"{self.base_url}/rest/v1/password_reset_tokens"
        data = {
            "user_id": user_id,
            "token": token,
            "expires_at": expires_at,
            "used": False,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=self.headers) as response:
                return response.status in [200, 201]

    async def use_password_reset_token(self, token: str, new_password: str) -> bool:
        """
        Validate a reset token and update the user's password.
        Marks the token as used. Returns False if token is invalid/expired/used.
        """
        from datetime import datetime, timezone as tz

        # Fetch the token
        url = f"{self.base_url}/rest/v1/password_reset_tokens"
        params = {"token": f"eq.{token}", "used": "eq.false", "select": "*"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=self.headers) as response:
                if response.status != 200:
                    print(f"[DEBUG] Reset token lookup failed with status {response.status}")
                    return False
                result = await response.json()
                if not result:
                    print(f"[DEBUG] Reset token not found or already used (token: {token[:8]}...)")
                    return False
                token_row = result[0]

        # Check expiry
        expires_at = token_row.get("expires_at", "")
        try:
            # Supabase returns timestamp without timezone — treat as UTC
            expiry_str = expires_at.replace("Z", "+00:00")
            expiry = datetime.fromisoformat(expiry_str)
            # If naive (no timezone info), assume UTC
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=tz.utc)
            if datetime.now(tz.utc) > expiry:
                return False
        except Exception:
            return False

        user_id = token_row["user_id"]

        # Update password
        new_hash = _hash_password(new_password)
        update_url = f"{self.base_url}/rest/v1/users?user_id=eq.{user_id}"
        headers = {**self.headers, "Prefer": "return=minimal"}

        async with aiohttp.ClientSession() as session:
            async with session.patch(update_url, json={"password_hash": new_hash}, headers=headers) as response:
                if response.status not in [200, 204]:
                    return False

        # Mark token as used
        token_update_url = f"{self.base_url}/rest/v1/password_reset_tokens?token=eq.{token}"
        async with aiohttp.ClientSession() as session:
            async with session.patch(token_update_url, json={"used": True}, headers=headers) as response:
                pass  # Best effort

        return True

    # -------------------------------------------------------------------------
    # Business profile methods
    # -------------------------------------------------------------------------

    async def create_business_profile(
        self,
        user_id: str,
        business_name: str,
        business_type: str,
        location: str,
        district: Optional[str] = None,
        years_operating: Optional[int] = None,
        unique_selling_points: Optional[str] = None,
        price_range_min: Optional[float] = None,
        price_range_max: Optional[float] = None,
        data_source: str = "web_ui",
        customer_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a business profile using Supabase REST API.
        Saves B2C and B2B target customers as separate array columns.
        """
        url = f"{self.base_url}/rest/v1/business_profiles"
        
        data: Dict[str, Any] = {
            "user_id": user_id,
            "business_name": business_name,
            "business_type": business_type,
            "location": location,
            "district": district,
            "years_operating": years_operating,
            "unique_selling_points": unique_selling_points,
            "price_range_min": price_range_min,
            "price_range_max": price_range_max,
            "data_source": data_source,
        }
        
        # Flatten customer_profile into explicit columns
        if customer_profile:
            ct = customer_profile.get("customer_type", "B2C")
            if ct.lower() in ('both', 'mixed'):
                ct = 'HYBRID'
            data["customer_type"] = ct
            
            b2c = customer_profile.get("b2c_profile") or {}
            b2b = customer_profile.get("b2b_profile") or {}
            
            b2c_segments = b2c.get("target_segments", []) if b2c else []
            b2b_types = b2b.get("target_business_types", []) if b2b else []
            
            if b2c_segments:
                data["b2c_target_segments"] = b2c_segments
            if b2b_types:
                data["b2b_target_types"] = b2b_types
            
            if b2b:
                data["b2b_business_sizes"] = b2b.get("business_size", [])
                data["b2b_avg_transaction_rm"] = b2b.get("avg_transaction_rm")
                data["b2b_purchase_frequency"] = b2b.get("purchase_frequency")
                data["b2b_decision_factors"] = b2b.get("decision_factors", [])
        
        # Remove None values
        data = {k: v for k, v in data.items() if v is not None}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=self.headers) as response:
                if response.status in [200, 201]:
                    result = await response.json()
                    return result[0] if isinstance(result, list) else result
                else:
                    error_text = await response.text()
                    raise Exception(f"Supabase API error ({response.status}): {error_text}")
    
    async def get_business_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a business profile by ID.
        Reconstructs customer_profile from flat columns.
        """
        url = f"{self.base_url}/rest/v1/business_profiles"
        params = {"profile_id": f"eq.{profile_id}", "select": "*"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=self.headers) as response:
                if response.status == 200:
                    result = await response.json()
                    if not result:
                        return None
                    row = result[0]
                    row['customer_profile'] = _reconstruct_customer_profile(row)
                    return row
                return None

    async def update_business_profile(
        self,
        profile_id: str,
        business_name: str,
        business_type: str,
        location: str,
        district: Optional[str] = None,
        years_operating: Optional[int] = None,
        unique_selling_points: Optional[str] = None,
        price_range_min: Optional[float] = None,
        price_range_max: Optional[float] = None,
        customer_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update an existing business profile."""
        url = f"{self.base_url}/rest/v1/business_profiles"
        params = {"profile_id": f"eq.{profile_id}"}
        
        data: Dict[str, Any] = {
            "business_name": business_name,
            "business_type": business_type,
            "location": location,
            "district": district,
            "years_operating": years_operating,
            "unique_selling_points": unique_selling_points,
            "price_range_min": price_range_min,
            "price_range_max": price_range_max,
        }
        
        if customer_profile:
            ct = customer_profile.get("customer_type", "B2C")
            if ct.lower() in ('both', 'mixed'):
                ct = 'HYBRID'
            data["customer_type"] = ct
            
            b2c = customer_profile.get("b2c_profile") or {}
            b2b = customer_profile.get("b2b_profile") or {}
            
            b2c_segments = b2c.get("target_segments", []) if b2c else []
            b2b_types = b2b.get("target_business_types", []) if b2b else []
            
            if b2c_segments:
                data["b2c_target_segments"] = b2c_segments
            if b2b_types:
                data["b2b_target_types"] = b2b_types
            
            if b2b:
                data["b2b_business_sizes"] = b2b.get("business_size", [])
                data["b2b_avg_transaction_rm"] = b2b.get("avg_transaction_rm")
                data["b2b_purchase_frequency"] = b2b.get("purchase_frequency")
                data["b2b_decision_factors"] = b2b.get("decision_factors", [])
        
        data = {k: v for k, v in data.items() if v is not None}
        
        headers = {**self.headers, 'Prefer': 'return=representation'}
        async with aiohttp.ClientSession() as session:
            async with session.patch(url, json=data, params=params, headers=headers) as response:
                if response.status in [200, 204]:
                    result = await response.json()
                    return result[0] if isinstance(result, list) and result else data
                else:
                    error_text = await response.text()
                    raise Exception(f"Failed to update profile: {error_text}")
    
    async def list_business_profiles(self, user_id: str) -> List[Dict[str, Any]]:
        """
        List all business profiles for a user.
        
        Returns:
            List of profile dicts
        """
        url = f"{self.base_url}/rest/v1/business_profiles"
        params = {
            "user_id": f"eq.{user_id}",
            "select": "*",
            "order": "created_at.desc"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=self.headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return []
    
    async def health_check(self) -> bool:
        """
        Check if Supabase API is accessible.
        
        Returns:
            True if API is healthy, False otherwise
        """
        try:
            url = f"{self.base_url}/rest/v1/"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    return response.status in [200, 404]  # 404 is ok, means API is up
        except Exception as e:
            print(f"[ERROR] Supabase health check failed: {e}")
            return False

    # -------------------------------------------------------------------------
    # Simulation results methods
    # -------------------------------------------------------------------------

    async def save_scenario(
        self,
        business_profile_id: str,
        scenario_name: str,
        scenario_type: str,
        description: str,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Save a scenario to the database."""
        url = f"{self.base_url}/rest/v1/scenarios"
        data = {
            "profile_id": business_profile_id,
            "scenario_name": scenario_name,
            "scenario_type": scenario_type,
            "description": description,
            "parameters": parameters,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=self.headers) as response:
                if response.status in [200, 201]:
                    result = await response.json()
                    return result[0] if isinstance(result, list) else result
                else:
                    error_text = await response.text()
                    raise Exception(f"Failed to save scenario: {error_text}")

    async def save_simulation(
        self,
        scenario_id: str,
        agent_count: int,
        status: str = "completed",
        started_at: Optional[str] = None,
        monte_carlo_enabled: bool = False,
        monte_carlo_total_runs: int = 1,
        monte_carlo_converged: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Save a simulation record to the database.
        
        Args:
            scenario_id: UUID of the scenario
            agent_count: Number of agents in simulation
            status: Simulation status
            started_at: ISO timestamp when simulation started
            monte_carlo_enabled: Whether Monte Carlo CV was used
            monte_carlo_total_runs: Total number of MC runs executed
            monte_carlo_converged: Whether MC converged (WCI CV <= threshold)
        """
        url = f"{self.base_url}/rest/v1/simulations"
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "scenario_id": scenario_id,
            "status": status,
            "current_week": 1,
            "agent_count": agent_count,
            "progress_percentage": 100.0,
            "started_at": started_at or now,
            "completed_at": now,
            "monte_carlo_enabled": monte_carlo_enabled,
            "monte_carlo_total_runs": monte_carlo_total_runs,
            "monte_carlo_converged": monte_carlo_converged,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=self.headers) as response:
                if response.status in [200, 201]:
                    result = await response.json()
                    return result[0] if isinstance(result, list) else result
                else:
                    error_text = await response.text()
                    raise Exception(f"Failed to save simulation: {error_text}")

    async def save_simulation_events(
        self,
        simulation_id: str,
        events: List[Dict[str, Any]],
    ) -> None:
        """Save simulation events (agent decisions) in bulk."""
        if not events:
            return
        url = f"{self.base_url}/rest/v1/simulation_events"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=events, headers=self.headers) as response:
                if response.status not in [200, 201]:
                    error_text = await response.text()
                    print(f"[WARN] Failed to save simulation events: {error_text}")

    async def save_simulation_report(
        self,
        simulation_id: str,
        report: Dict[str, Any],
        monte_carlo_summary: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Save simulation report to the database.
        
        Args:
            simulation_id: UUID of the simulation
            report: Report data with risk_summary, archetype_breakdown, recommendations
            monte_carlo_summary: Optional Monte Carlo convergence statistics
        """
        url = f"{self.base_url}/rest/v1/simulation_reports"
        data = {
            "simulation_id": simulation_id,
            "risk_level": report["risk_summary"]["risk_level"],
            "churn_rate": report["risk_summary"]["churn_rate"],
            "visit_rate": report["risk_summary"]["visit_rate"],
            "estimated_revenue": report["risk_summary"]["estimated_revenue"],
            "archetype_breakdown": report["archetype_breakdown"],
            "recommendations": report["recommendations"],
            "analysis": report.get("analysis", ""),
            "monte_carlo_summary": monte_carlo_summary,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=self.headers) as response:
                if response.status not in [200, 201]:
                    error_text = await response.text()
                    print(f"[WARN] Failed to save report: {error_text}")

    async def list_simulation_history(self, profile_id: str) -> List[Dict[str, Any]]:
        """
        List simulation history for a business profile.
        Returns scenarios with their simulation results, reports, and agent events.
        """
        # First get scenarios for this profile
        url = f"{self.base_url}/rest/v1/scenarios"
        params = {
            "profile_id": f"eq.{profile_id}",
            "select": "scenario_id,scenario_name,scenario_type,description,parameters,created_at",
            "order": "created_at.desc",
            "limit": "50",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=self.headers) as response:
                if response.status != 200:
                    return []
                scenarios = await response.json()

        if not scenarios:
            return []

        # Get simulations for these scenarios
        scenario_ids = [s['scenario_id'] for s in scenarios]
        sim_url = f"{self.base_url}/rest/v1/simulations"
        sim_params = {
            "scenario_id": f"in.({','.join(scenario_ids)})",
            "select": "simulation_id,scenario_id,status,agent_count,completed_at,created_at",
            "status": "eq.completed",
            "order": "completed_at.desc",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(sim_url, params=sim_params, headers=self.headers) as response:
                if response.status != 200:
                    return []
                simulations = await response.json()

        if not simulations:
            return []

        sim_ids = [s['simulation_id'] for s in simulations]

        # Fetch reports and events in parallel
        async with aiohttp.ClientSession() as session:
            report_task = session.get(
                f"{self.base_url}/rest/v1/simulation_reports",
                params={"simulation_id": f"in.({','.join(sim_ids)})", "select": "*"},
                headers=self.headers,
            )
            events_task = session.get(
                f"{self.base_url}/rest/v1/simulation_events",
                params={
                    "simulation_id": f"in.({','.join(sim_ids)})",
                    "select": "simulation_id,agent_id,income_level,decision,reasoning,spend_amount,profile_text",
                    "order": "agent_id.asc",
                },
                headers=self.headers,
            )
            async with report_task as report_resp, events_task as events_resp:
                reports = await report_resp.json() if report_resp.status == 200 else []
                events  = await events_resp.json() if events_resp.status == 200 else []

        # Build lookup maps
        scenario_map = {s['scenario_id']: s for s in scenarios}
        report_map   = {r['simulation_id']: r for r in (reports or [])}

        # Group events by simulation_id
        events_by_sim: Dict[str, List[Dict[str, Any]]] = {}
        for ev in (events or []):
            sid = ev['simulation_id']
            events_by_sim.setdefault(sid, []).append(ev)

        # Combine into history items
        history = []
        for sim in simulations:
            scenario = scenario_map.get(sim['scenario_id'], {})
            report   = report_map.get(sim['simulation_id'])
            sim_events = events_by_sim.get(sim['simulation_id'], [])

            # Reconstruct agents list from saved events
            agents = [
                {
                    "agent_id":      ev['agent_id'],
                    "persona_name":  f"Customer {ev['agent_id']}",
                    "income_level":  ev.get('income_level', 'M40'),
                    "age_range":     "",
                    "is_active":     ev.get('decision') != 'churn',
                    "last_decision": ev.get('decision'),
                    "reasoning":     ev.get('reasoning', ''),
                    "personality":   ev.get('profile_text', ''),
                    "personality_type": "",
                }
                for ev in sim_events
            ]

            # Reconstruct activity feed from saved events
            feed = [
                {
                    "id":       ev['agent_id'],
                    "type":     ev.get('decision', 'visit'),
                    "agentId":  ev['agent_id'],
                    "html": (
                        f"<strong>Customer {ev['agent_id']}</strong> "
                        + ("visited 🟢" if ev.get('decision') == 'visit'
                           else "churned 🔴" if ev.get('decision') == 'churn'
                           else "skipped 🟡")
                        + f"<span class=\"reasoning\">{ev.get('reasoning', '')}</span>"
                    ),
                }
                for ev in sim_events
            ]

            # Normalise timestamp
            raw_ts = sim.get('completed_at') or sim.get('created_at', '')
            if raw_ts and not raw_ts.endswith('Z') and '+' not in raw_ts:
                raw_ts = raw_ts + 'Z'

            history.append({
                'simulation_id': sim['simulation_id'],
                'scenario_name': scenario.get('scenario_name', 'Unknown'),
                'scenario_type': scenario.get('scenario_type', ''),
                'description':   scenario.get('description', ''),
                'agent_count':   sim.get('agent_count', 0),
                'completed_at':  raw_ts,
                'report':        report,
                'agents':        agents,
                'feed':          feed,
                'session_id':    (scenario.get('parameters') or {}).get('_session_id'),
            })

        return history

    async def delete_simulation(self, simulation_id: str) -> bool:
        """Delete a simulation and its related data."""
        async with aiohttp.ClientSession() as session:
            # Get the scenario_id before deleting (to clean up orphaned scenario)
            sim_url = f"{self.base_url}/rest/v1/simulations"
            async with session.get(
                sim_url,
                params={"simulation_id": f"eq.{simulation_id}", "select": "scenario_id"},
                headers=self.headers,
            ) as response:
                scenario_id = None
                if response.status == 200:
                    rows = await response.json()
                    if rows:
                        scenario_id = rows[0].get("scenario_id")

            # Delete simulation events first (FK dependency)
            events_url = f"{self.base_url}/rest/v1/simulation_events"
            await session.delete(
                events_url,
                params={"simulation_id": f"eq.{simulation_id}"},
                headers=self.headers,
            )

            # Delete simulation report (FK dependency)
            reports_url = f"{self.base_url}/rest/v1/simulation_reports"
            await session.delete(
                reports_url,
                params={"simulation_id": f"eq.{simulation_id}"},
                headers=self.headers,
            )

            # Delete the simulation itself
            async with session.delete(
                sim_url,
                params={"simulation_id": f"eq.{simulation_id}"},
                headers=self.headers,
            ) as response:
                if response.status not in [200, 204]:
                    return False

            # Delete the orphaned scenario
            if scenario_id:
                scenarios_url = f"{self.base_url}/rest/v1/scenarios"
                await session.delete(
                    scenarios_url,
                    params={"scenario_id": f"eq.{scenario_id}"},
                    headers=self.headers,
                )

            return True

    async def save_chat_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Save a chat message to the database."""
        url = f"{self.base_url}/rest/v1/chat_messages"
        data = {
            "session_id": session_id,
            "role": role,
            "content": content,
        }
        if metadata:
            data["message_metadata"] = metadata
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=self.headers) as response:
                if response.status not in [200, 201]:
                    pass  # Non-critical, don't crash

    async def create_chat_session(
        self,
        user_id: str,
        profile_id: Optional[str] = None,
    ) -> Optional[str]:
        """Create a chat session and return its ID."""
        url = f"{self.base_url}/rest/v1/chat_sessions"
        data = {"user_id": user_id}
        if profile_id:
            data["profile_id"] = profile_id
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=self.headers) as response:
                if response.status in [200, 201]:
                    result = await response.json()
                    row = result[0] if isinstance(result, list) else result
                    return row.get("session_id")
                return None

    async def list_chat_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve all messages for a chat session, ordered by creation time."""
        url = f"{self.base_url}/rest/v1/chat_messages"
        params = {
            "session_id": f"eq.{session_id}",
            "select": "role,content,message_metadata,created_at",
            "order": "created_at.asc",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=self.headers) as response:
                if response.status == 200:
                    return await response.json()
                return []
