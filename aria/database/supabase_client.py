"""
Supabase REST API client for database operations.
"""

import aiohttp
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
            'Prefer': 'return=representation',
        }

    # -------------------------------------------------------------------------
    # User auth methods — all delegated to Supabase Auth
    # -------------------------------------------------------------------------

    async def register_user(self, email: str, password: str) -> Dict[str, Any]:
        """
        Register a new user via Supabase Auth.

        Supabase sends a confirmation email automatically when email
        confirmation is enabled in the Dashboard (Authentication > Settings).
        If "Confirm email" is disabled the user is logged in immediately and
        the response includes an access_token / refresh_token.

        Returns a dict with at least:
            id, email, created_at, access_token (if auto-confirmed),
            refresh_token (if auto-confirmed)
        """
        url = f"{self.base_url}/auth/v1/signup"
        payload = {
            "email": email.lower().strip(),
            "password": password,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=self.headers) as resp:
                body = await resp.json()
                if resp.status not in (200, 201):
                    msg = body.get("msg") or body.get("message") or body.get("error_description") or str(body)
                    if "already registered" in msg.lower():
                        raise Exception("EMAIL_TAKEN")
                    raise Exception(f"Supabase Auth signup error ({resp.status}): {msg}")

                # Supabase returns the user inside body["user"] when email
                # confirmation is ON, or at the top level when it's OFF.
                user = body.get("user") or body
                session_data = body.get("session") or {}

                return {
                    "id":            user.get("id", ""),
                    "email":         user.get("email", email),
                    "created_at":    user.get("created_at", datetime.now(timezone.utc).isoformat()),
                    "access_token":  session_data.get("access_token") or body.get("access_token"),
                    "refresh_token": session_data.get("refresh_token") or body.get("refresh_token"),
                    "email_confirmed": user.get("email_confirmed_at") is not None,
                }

    async def login_user(self, email: str, password: str) -> Dict[str, Any]:
        """
        Authenticate a user via Supabase Auth (password grant).

        Returns a dict with:
            id, email, created_at, access_token, refresh_token
        """
        url = f"{self.base_url}/auth/v1/token?grant_type=password"
        payload = {
            "email": email.lower().strip(),
            "password": password,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=self.headers) as resp:
                if resp.status != 200:
                    raise Exception("INVALID_CREDENTIALS")

                body = await resp.json()
                user = body.get("user", {})

                return {
                    "id":            user.get("id", ""),
                    "email":         user.get("email", email),
                    "created_at":    user.get("created_at", datetime.now(timezone.utc).isoformat()),
                    "access_token":  body.get("access_token"),
                    "refresh_token": body.get("refresh_token"),
                }

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a Supabase Auth user by ID using the admin endpoint.
        Requires the service-role key.
        """
        url = f"{self.base_url}/auth/v1/admin/users/{user_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as resp:
                if resp.status == 200:
                    user = await resp.json()
                    return {
                        "id":         user.get("id"),
                        "email":      user.get("email"),
                        "created_at": user.get("created_at"),
                    }
                return None

    async def request_password_reset(self, email: str, redirect_to: Optional[str] = None) -> bool:
        """
        Trigger Supabase Auth to send a password-reset email via Supabase SMTP.

        Supabase always returns 200 to prevent email enumeration.
        The reset link in the email will contain an access_token the user
        must send to /api/auth/reset-password.
        """
        url = f"{self.base_url}/auth/v1/recover"
        payload: Dict[str, Any] = {"email": email.lower().strip()}
        if redirect_to:
            payload["redirect_to"] = redirect_to

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=self.headers) as resp:
                return resp.status == 200

    async def update_user_password(self, access_token: str, new_password: str) -> bool:
        """
        Update a user's password using their JWT access token.
        This is called after the user clicks the Supabase password-reset link
        and supplies the token from the URL fragment (#access_token=...).

        Raises Exception with the error message on failure.
        """
        url = f"{self.base_url}/auth/v1/user"
        payload = {"password": new_password}

        # Use the user's own JWT, not the service-role key
        user_headers = {
            **self.headers,
            "Authorization": f"Bearer {access_token}",
        }

        async with aiohttp.ClientSession() as session:
            async with session.put(url, json=payload, headers=user_headers) as resp:
                if resp.status == 200:
                    return True
                body = await resp.json()
                msg = body.get("msg") or body.get("message") or body.get("error_description") or "Failed to update password"
                raise Exception(msg)

    async def change_password(self, access_token: str, new_password: str) -> bool:
        """
        Change a user's password.  The caller must supply a valid JWT —
        Supabase Auth handles credential verification internally.

        Args:
            access_token: The user's current Supabase JWT.
            new_password: The new password to set.

        Returns:
            True on success.
        Raises:
            Exception("INVALID_CREDENTIALS") if the token is invalid/expired.
        """
        try:
            return await self.update_user_password(access_token, new_password)
        except Exception as exc:
            msg = str(exc).lower()
            if "invalid" in msg or "expired" in msg or "jwt" in msg:
                raise Exception("INVALID_CREDENTIALS")
            raise

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
        
        insert_headers = {
            **self.headers,
            'Prefer': 'return=representation',
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=insert_headers) as response:
                if response.status in [200, 201]:
                    result = await response.json()
                    if isinstance(result, list) and result:
                        return result[0]
                    if isinstance(result, dict) and result:
                        return result
                    # Supabase returned empty — re-fetch the just-inserted row by user_id + name
                    return await self._fetch_latest_profile(data["user_id"])
                else:
                    error_text = await response.text()
                    raise Exception(f"Supabase API error ({response.status}): {error_text}")

    async def _fetch_latest_profile(self, user_id: str) -> Dict[str, Any]:
        """Fallback: fetch the most recently created profile for a user."""
        url = f"{self.base_url}/rest/v1/business_profiles"
        params = {
            "user_id": f"eq.{user_id}",
            "order": "created_at.desc",
            "limit": "1",
            "select": "*",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=self.headers) as response:
                if response.status == 200:
                    result = await response.json()
                    if result:
                        return result[0]
                raise Exception("Profile was inserted but could not be retrieved.")
    
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
                        print(f"[WARN] get_business_profile: empty result for {profile_id}, status={response.status}")
                        return None
                    row = result[0]
                    row['customer_profile'] = _reconstruct_customer_profile(row)
                    return row
                print(f"[WARN] get_business_profile: status={response.status} for {profile_id}")
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
        # PostgREST requires the filter in the URL for PATCH
        url = f"{self.base_url}/rest/v1/business_profiles?profile_id=eq.{profile_id}"
        
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
        
        patch_headers = {**self.headers, 'Prefer': 'return=representation'}
        async with aiohttp.ClientSession() as session:
            async with session.patch(url, json=data, headers=patch_headers) as response:
                if response.status in [200, 204]:
                    result = await response.json()
                    if isinstance(result, list) and result:
                        return result[0]
                    if isinstance(result, dict) and result:
                        return result
                    # Empty response — re-fetch the updated row
                    print(f"[DEBUG] PATCH returned empty, re-fetching profile {profile_id}")
                    fetched = await self.get_business_profile(profile_id)
                    if fetched:
                        return fetched
                    raise Exception(f"Profile {profile_id} could not be retrieved after update.")
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
        """Save a scenario to the database. Returns the saved row with scenario_id."""
        url = f"{self.base_url}/rest/v1/scenarios"
        data = {
            "profile_id": business_profile_id,
            "scenario_name": scenario_name,
            "scenario_type": scenario_type,
            "description": description,
            "parameters": parameters,
        }
        insert_headers = {**self.headers, 'Prefer': 'return=representation'}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=insert_headers) as response:
                if response.status in [200, 201]:
                    result = await response.json()
                    if isinstance(result, list) and result:
                        return result[0]
                    if isinstance(result, dict) and result:
                        return result
                    # Empty response — fetch the latest scenario for this profile
                    async with session.get(
                        url,
                        params={"profile_id": f"eq.{business_profile_id}", "order": "created_at.desc", "limit": "1"},
                        headers=self.headers,
                    ) as fetch_resp:
                        rows = await fetch_resp.json() if fetch_resp.status == 200 else []
                        if rows:
                            return rows[0]
                    raise Exception("Scenario inserted but could not be retrieved.")
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
        """Save a simulation record. Returns the saved row with simulation_id."""
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
        insert_headers = {**self.headers, 'Prefer': 'return=representation'}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=insert_headers) as response:
                if response.status in [200, 201]:
                    result = await response.json()
                    if isinstance(result, list) and result:
                        return result[0]
                    if isinstance(result, dict) and result:
                        return result
                    # Empty response — fetch the latest simulation for this scenario
                    async with session.get(
                        url,
                        params={"scenario_id": f"eq.{scenario_id}", "order": "created_at.desc", "limit": "1"},
                        headers=self.headers,
                    ) as fetch_resp:
                        rows = await fetch_resp.json() if fetch_resp.status == 200 else []
                        if rows:
                            return rows[0]
                    raise Exception("Simulation inserted but could not be retrieved.")
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
        # Use return=minimal for bulk inserts — avoids large response payloads
        bulk_headers = {**self.headers, 'Prefer': 'return=minimal'}
        # Insert in chunks of 100 to avoid request size limits
        chunk_size = 100
        async with aiohttp.ClientSession() as session:
            for i in range(0, len(events), chunk_size):
                chunk = events[i:i + chunk_size]
                async with session.post(url, json=chunk, headers=bulk_headers) as response:
                    if response.status not in [200, 201, 204]:
                        error_text = await response.text()
                        print(f"[WARN] Failed to save simulation events chunk {i}-{i+len(chunk)}: {error_text}")

    async def save_simulation_report(
        self,
        simulation_id: str,
        report: Dict[str, Any],
        monte_carlo_summary: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Save simulation report to the database."""
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
            "key_reasons": report.get("key_reasons", []),
            "monte_carlo_summary": monte_carlo_summary,
        }
        insert_headers = {**self.headers, 'Prefer': 'return=minimal'}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=insert_headers) as response:
                if response.status not in [200, 201, 204]:
                    error_text = await response.text()
                    print(f"[WARN] Failed to save report for sim {simulation_id}: {error_text}")

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
        """Delete a simulation and all its related data (cascade order)."""
        delete_headers = {**self.headers, 'Prefer': 'return=minimal'}
        async with aiohttp.ClientSession() as session:
            # 1. Get scenario_id before deleting (to clean up orphaned scenario)
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

            # 2. Delete simulation events (FK → simulation)
            async with session.delete(
                f"{self.base_url}/rest/v1/simulation_events",
                params={"simulation_id": f"eq.{simulation_id}"},
                headers=delete_headers,
            ) as resp:
                if resp.status not in [200, 204]:
                    print(f"[WARN] Failed to delete events for sim {simulation_id}: {resp.status}")

            # 3. Delete simulation report (FK → simulation)
            async with session.delete(
                f"{self.base_url}/rest/v1/simulation_reports",
                params={"simulation_id": f"eq.{simulation_id}"},
                headers=delete_headers,
            ) as resp:
                if resp.status not in [200, 204]:
                    print(f"[WARN] Failed to delete report for sim {simulation_id}: {resp.status}")

            # 4. Delete the simulation itself
            async with session.delete(
                sim_url,
                params={"simulation_id": f"eq.{simulation_id}"},
                headers=delete_headers,
            ) as response:
                if response.status not in [200, 204]:
                    print(f"[ERROR] Failed to delete simulation {simulation_id}: {response.status}")
                    return False

            # 5. Delete the orphaned scenario only if no other simulations use it
            if scenario_id:
                async with session.get(
                    sim_url,
                    params={"scenario_id": f"eq.{scenario_id}", "select": "simulation_id", "limit": "1"},
                    headers=self.headers,
                ) as resp:
                    other_sims = await resp.json() if resp.status == 200 else []

                if not other_sims:
                    async with session.delete(
                        f"{self.base_url}/rest/v1/scenarios",
                        params={"scenario_id": f"eq.{scenario_id}"},
                        headers=delete_headers,
                    ) as resp:
                        if resp.status not in [200, 204]:
                            print(f"[WARN] Failed to delete scenario {scenario_id}: {resp.status}")

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
        data: Dict[str, Any] = {"user_id": user_id}
        if profile_id:
            data["profile_id"] = profile_id
        insert_headers = {**self.headers, 'Prefer': 'return=representation'}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=insert_headers) as response:
                if response.status in [200, 201]:
                    result = await response.json()
                    row = (result[0] if isinstance(result, list) and result
                           else result if isinstance(result, dict) and result
                           else None)
                    if row:
                        return row.get("session_id")
                    # Empty response — fetch latest session for this user
                    async with session.get(
                        url,
                        params={"user_id": f"eq.{user_id}", "order": "started_at.desc", "limit": "1"},
                        headers=self.headers,
                    ) as fetch_resp:
                        rows = await fetch_resp.json() if fetch_resp.status == 200 else []
                        if rows:
                            return rows[0].get("session_id")
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
