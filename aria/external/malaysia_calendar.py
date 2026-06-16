"""
Malaysia Calendar API client for holiday context.

Fetches Malaysian public holidays, school calendar, and business day information
from the Malaysia Calendar API (mycal-api). Used to provide holiday context
to the LLM when users ask about holidays, demand surges, or seasonal planning.

API source: https://github.com/Junhui20/malaysia-calendar-api
Data sourced from official Malaysian government publications (JPM BKPP, JAKIM, KPM).
"""

import aiohttp
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MalaysiaCalendarClient:
    """
    Client for the Malaysia Calendar API.
    
    Provides holiday and business day information for Pulau Pinang (Penang)
    and other Malaysian states. Used to enrich simulation context with
    real holiday data.
    """
    
    BASE_URL = "https://mycal-api.huijun00100101.workers.dev/v1"
    DEFAULT_STATE = "pulau-pinang"
    
    def __init__(self, state: str = "pulau-pinang"):
        """
        Initialize Malaysia Calendar client.
        
        Args:
            state: State code to filter holidays for (default: pulau-pinang).
                   Accepts aliases like 'penang', 'pg', 'pulau-pinang'.
        """
        self.state = state
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            )
        return self.session
    
    async def close(self):
        """Close aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def _make_request(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a GET request to the Malaysia Calendar API.
        
        Args:
            path: API path (e.g., '/holidays')
            params: Query parameters
            
        Returns:
            JSON response data
        """
        session = await self._get_session()
        url = f"{self.BASE_URL}{path}"
        
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"Malaysia Calendar API returned {response.status} for {path}")
                    return {}
        except aiohttp.ClientError as e:
            logger.warning(f"Malaysia Calendar API request failed: {e}")
            return {}
        except Exception as e:
            logger.warning(f"Unexpected error calling Malaysia Calendar API: {e}")
            return {}
    
    async def get_holidays(self, year: Optional[int] = None, month: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get public holidays for the configured state.
        
        Args:
            year: Year to query (default: current year)
            month: Optional month filter (1-12)
            
        Returns:
            List of holiday dictionaries with name, date, type info
        """
        if year is None:
            year = datetime.now().year
        
        params: Dict[str, Any] = {
            "year": year,
            "state": self.state,
        }
        if month:
            params["month"] = month
        
        data = await self._make_request("/holidays", params)
        holidays = data.get("data", [])
        
        # Normalize the response into a simpler format
        result = []
        for h in holidays:
            name = h.get("name", {})
            result.append({
                "date": h.get("date", ""),
                "name_en": name.get("en", "") if isinstance(name, dict) else str(name),
                "name_ms": name.get("ms", "") if isinstance(name, dict) else str(name),
                "type": h.get("type", ""),
                "status": h.get("status", "confirmed"),
            })
        
        return result
    
    async def get_upcoming_holidays(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get the next upcoming holidays for the configured state.
        
        Args:
            limit: Maximum number of upcoming holidays to return
            
        Returns:
            List of upcoming holiday dictionaries
        """
        data = await self._make_request("/holidays/next", {"state": self.state})
        
        if not data:
            return []
        
        # The API returns a single next holiday or a list
        holidays = data.get("data", [])
        if isinstance(holidays, dict):
            holidays = [holidays]
        
        result = []
        for h in holidays[:limit]:
            name = h.get("name", {})
            result.append({
                "date": h.get("date", ""),
                "name_en": name.get("en", "") if isinstance(name, dict) else str(name),
                "name_ms": name.get("ms", "") if isinstance(name, dict) else str(name),
                "type": h.get("type", ""),
                "days_until": h.get("daysUntil", None),
            })
        
        return result
    
    async def check_date(self, check_date: str) -> Dict[str, Any]:
        """
        Check if a specific date is a holiday, weekend, or working day.
        
        Args:
            check_date: Date string in YYYY-MM-DD format
            
        Returns:
            Dictionary with isHoliday, isWeekend, isWorkingDay, holidays list
        """
        data = await self._make_request("/holidays/check", {
            "date": check_date,
            "state": self.state,
        })
        
        return data.get("data", {})
    
    async def get_business_days(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Count business days between two dates for the configured state.
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Dictionary with businessDays count and totalDays
        """
        data = await self._make_request("/business-days", {
            "start": start_date,
            "end": end_date,
            "state": self.state,
        })
        
        return data.get("data", {})
    
    async def get_school_holidays(self, year: Optional[int] = None, group: str = "B") -> List[Dict[str, Any]]:
        """
        Get school holidays (cuti penggal, cuti perayaan) for the year.
        
        Pulau Pinang is in Kumpulan B (Group B) which uses Sat-Sun weekends.
        
        Args:
            year: Year to query (default: current year)
            group: School group - "A" (Kedah/Kelantan/Terengganu) or "B" (all others including Penang)
            
        Returns:
            List of school holiday periods with start/end dates and names
        """
        if year is None:
            year = datetime.now().year
        
        params: Dict[str, Any] = {"year": year, "group": group}
        data = await self._make_request("/school/holidays", params)
        
        holidays = data.get("data", [])
        result = []
        for h in holidays:
            name = h.get("name", {})
            result.append({
                "start": h.get("startDate", ""),
                "end": h.get("endDate", ""),
                "name_en": name.get("en", "") if isinstance(name, dict) else str(name),
                "name_ms": name.get("ms", "") if isinstance(name, dict) else str(name),
                "type": h.get("type", ""),
                "days": h.get("days", 0),
            })
        
        return result
    
    async def get_school_terms(self, year: Optional[int] = None, group: str = "B") -> List[Dict[str, Any]]:
        """
        Get school term dates and day counts.
        
        Args:
            year: Year to query (default: current year)
            group: School group - "A" or "B" (Penang = B)
            
        Returns:
            List of school terms with start/end dates
        """
        if year is None:
            year = datetime.now().year
        
        params: Dict[str, Any] = {"year": year, "group": group}
        data = await self._make_request("/school/terms", params)
        
        terms = data.get("data", [])
        result = []
        for t in terms:
            name = t.get("name", {})
            result.append({
                "start": t.get("startDate", ""),
                "end": t.get("endDate", ""),
                "name_en": name.get("en", "") if isinstance(name, dict) else str(name),
                "name_ms": name.get("ms", "") if isinstance(name, dict) else str(name),
                "days": t.get("days", 0),
            })
        
        return result
    
    async def get_exam_schedule(self, year: Optional[int] = None, exam_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get exam schedules (SPM, STPM, MUET, PT3).
        
        Args:
            year: Year to query (default: current year)
            exam_type: Filter by exam type (spm, stpm, muet, pt3) or None for all
            
        Returns:
            List of exam periods with dates and details
        """
        if year is None:
            year = datetime.now().year
        
        params: Dict[str, Any] = {"year": year}
        if exam_type:
            params["type"] = exam_type
        
        data = await self._make_request("/school/exams", params)
        
        exams = data.get("data", [])
        result = []
        for ex in exams:
            name = ex.get("name", "")
            full_name = ex.get("fullName", {})
            result.append({
                "start": ex.get("startDate", ""),
                "end": ex.get("endDate", ""),
                "name": name if isinstance(name, str) else str(name),
                "name_en": full_name.get("en", name) if isinstance(full_name, dict) else str(name),
                "type": ex.get("type", ""),
                "status": ex.get("status", ""),
            })
        
        return result
    
    async def is_school_day(self, check_date: str) -> Dict[str, Any]:
        """
        Check if a specific date is a school day.
        
        Args:
            check_date: Date string in YYYY-MM-DD format
            
        Returns:
            Dictionary with isSchoolDay boolean and reason
        """
        data = await self._make_request("/school/is-school-day", {
            "date": check_date,
            "state": self.state,
        })
        
        return data.get("data", {})

    async def get_holiday_context_summary(self, year: Optional[int] = None) -> str:
        """
        Generate a human-readable summary of holiday context for the LLM.
        Includes upcoming public holidays, school holidays, and exam schedules.
        
        Args:
            year: Year to summarize (default: current year)
            
        Returns:
            Formatted string summary of holiday, school, and exam information
        """
        if year is None:
            year = datetime.now().year
        
        parts = []
        
        # Get upcoming public holidays
        upcoming = await self.get_upcoming_holidays(limit=5)
        if upcoming:
            parts.append(f"Upcoming public holidays in {self.state.replace('-', ' ').title()}:")
            for h in upcoming:
                days_info = f" ({h['days_until']} days away)" if h.get('days_until') is not None else ""
                ms_name = f" / {h['name_ms']}" if h.get('name_ms') and h['name_ms'] != h['name_en'] else ""
                parts.append(f"  • {h['date']} — {h['name_en']}{ms_name}{days_info}")
        
        # Get all holidays for the year to provide seasonal context
        all_holidays = await self.get_holidays(year=year)
        if all_holidays:
            parts.append(f"\nTotal public holidays in {year}: {len(all_holidays)}")
            
            # Group by month for seasonal insight
            monthly: Dict[int, List[str]] = {}
            for h in all_holidays:
                try:
                    month_num = int(h["date"].split("-")[1])
                    # Include both names for LLM matching
                    label = h["name_en"]
                    if h.get("name_ms") and h["name_ms"] != h["name_en"]:
                        label = f"{h['name_ms']} ({h['name_en']})"
                    monthly.setdefault(month_num, []).append(label)
                except (IndexError, ValueError):
                    pass
            
            # Highlight months with many holidays (potential demand surges)
            busy_months = [(m, names) for m, names in monthly.items() if len(names) >= 2]
            if busy_months:
                parts.append("\nMonths with multiple holidays (potential demand surges):")
                month_names = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                for m, names in sorted(busy_months):
                    parts.append(f"  • {month_names[m]}: {', '.join(names)}")
        
        # Get school holidays (Kumpulan B for Penang)
        school_holidays = await self.get_school_holidays(year=year, group="B")
        if school_holidays:
            parts.append(f"\nSchool holidays {year} (Kumpulan B — Pulau Pinang):")
            for sh in school_holidays:
                days_info = f" ({sh['days']} days)" if sh.get('days') else ""
                parts.append(f"  • {sh['start']} to {sh['end']} — {sh['name_en']}{days_info}")
        
        # Get exam schedule
        exams = await self.get_exam_schedule(year=year)
        if exams:
            parts.append(f"\nMajor exam periods {year}:")
            for ex in exams:
                end_info = f" to {ex['end']}" if ex.get('end') else ""
                parts.append(f"  • {ex['start']}{end_info} — {ex['name']} ({ex['type'].upper()})")
        
        return "\n".join(parts) if parts else "Holiday data unavailable"
