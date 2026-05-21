"""
DOSM (Department of Statistics Malaysia) client for Penang district demographics.
Fetches Penang demographic data (income + age) for archetype generation.

Uses the DOSM Open Data parquet file (https://storage.dosm.gov.my) for live
population data with local income JSON as supplementary data.
"""

import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)


class DOSMAPIError(Exception):
    """Exception raised for DOSM data errors."""
    pass


class DOSMClient:
    """Client for fetching Penang district demographic data from DOSM sources."""

    # Official DOSM parquet file URL (recommended access method per data.gov.my)
    DOSM_PARQUET_URL = "https://storage.dosm.gov.my/population/population_district.parquet"
    REQUEST_TIMEOUT = 30  # seconds

    # Mapping from DOSM 5-year age bands to our grouped age bands
    # Children (0-19) are excluded as they are not relevant customers
    AGE_BAND_MAPPING = {
        "20-24": "20-29",
        "25-29": "20-29",
        "30-34": "30-39",
        "35-39": "30-39",
        "40-44": "40-49",
        "45-49": "40-49",
        "50-54": "50-59",
        "55-59": "50-59",
        "60-64": "60+",
        "65-69": "60+",
        "70-74": "60+",
        "75-79": "60+",
        "80-84": "60+",
        "85+": "60+",
    }

    # Ordered list of our grouped age bands
    AGE_GROUPS = ["20-29", "30-39", "40-49", "50-59", "60+"]

    # Penang district names as they appear in the DOSM dataset
    PENANG_DISTRICTS = [
        "Timur Laut",
        "Barat Daya",
        "Seberang Perai Tengah",
        "Seberang Perai Utara",
        "Seberang Perai Selatan",
    ]

    def __init__(self):
        """Initialize DOSM client with Penang data paths."""
        self.penang_data_path = (
            Path(__file__).parent.parent.parent / "data" / "penang_income_districts.json"
        )

    async def get_demographics(self, district: str) -> Dict[str, Any]:
        """
        Get demographic data for a Penang district.

        Fetches live age data from the DOSM parquet file and combines it
        with local income distribution data.

        Args:
            district: Penang district name (required)

        Returns:
            Dictionary with demographic data including income distribution,
            age distribution, and spending patterns

        Raises:
            DOSMAPIError: If district not found or data unavailable
        """
        if not district:
            raise DOSMAPIError(
                "District name is required. Available districts: "
                + ", ".join(self.PENANG_DISTRICTS)
            )

        data = self._load_penang_district_data(district)

        if not data:
            raise DOSMAPIError(
                f"District '{district}' not found. Available districts: "
                + ", ".join(self.PENANG_DISTRICTS)
            )

        return data

    def _load_penang_district_data(self, district: str) -> Optional[Dict[str, Any]]:
        """
        Load Penang district data combining live age data with local income data.

        Args:
            district: District name

        Returns:
            District demographic data or None if not found
        """
        try:
            with open(self.penang_data_path, "r", encoding="utf-8") as f:
                penang_data = json.load(f)

            # Check district aliases
            district_aliases = penang_data.get("district_aliases", {})
            normalized_district = district_aliases.get(district.lower(), district)

            # Get district data
            districts = penang_data.get("districts", {})
            district_info = districts.get(normalized_district)

            if not district_info:
                return None

            # Calculate median incomes based on household distribution
            income_dist = district_info.get("income_distribution", {})
            household_dist = district_info.get("household_distribution_by_income_class", {})

            b40_median = self._estimate_median_income(
                household_dist, 0, income_dist["B40"]["percentage"]
            )
            m40_median = self._estimate_median_income(
                household_dist,
                income_dist["B40"]["percentage"],
                income_dist["B40"]["percentage"] + income_dist["M40"]["percentage"],
            )
            t20_median = self._estimate_median_income(
                household_dist,
                income_dist["B40"]["percentage"] + income_dist["M40"]["percentage"],
                100,
            )

            income_groups = penang_data.get("income_groups", {})

            result = {
                "income_distribution": {
                    "B40": {
                        "percentage": income_dist["B40"]["percentage"],
                        "median_income_rm": b40_median,
                        "min_income_rm": income_groups["B40"]["min_income_rm"],
                        "max_income_rm": income_groups["B40"]["max_income_rm"],
                        "description": income_groups["B40"]["description"],
                    },
                    "M40": {
                        "percentage": income_dist["M40"]["percentage"],
                        "median_income_rm": m40_median,
                        "min_income_rm": income_groups["M40"]["min_income_rm"],
                        "max_income_rm": income_groups["M40"]["max_income_rm"],
                        "description": income_groups["M40"]["description"],
                    },
                    "T20": {
                        "percentage": income_dist["T20"]["percentage"],
                        "median_income_rm": t20_median,
                        "min_income_rm": income_groups["T20"]["min_income_rm"],
                        "max_income_rm": income_groups["T20"]["max_income_rm"],
                        "description": income_groups["T20"]["description"],
                    },
                },
                "household_distribution_by_income_class": household_dist,
                "source": f"DOSM Penang District Data - {normalized_district}",
                "district": normalized_district,
                "state": "Pulau Pinang",
            }

            # Fetch live age distribution from DOSM parquet
            age_data = self._fetch_age_distribution(normalized_district)
            if age_data:
                result["age_distribution"] = age_data["age_distribution"]
                result["total_population"] = age_data.get("total_population")
                result["data_source"] = age_data.get("data_source")
            else:
                logger.warning(
                    f"Could not fetch live age data for {normalized_district}"
                )

            # Add spending patterns and payment preferences
            result["spending_patterns"] = self._get_penang_spending_patterns(normalized_district)
            result["payment_preferences"] = self._get_penang_payment_preferences(normalized_district)

            return result

        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            logger.error(f"Could not load Penang district data: {e}")
            return None

    # -------------------------------------------------------------------------
    # DOSM Parquet Data Fetch
    # -------------------------------------------------------------------------

    def _fetch_age_distribution(self, district: str) -> Optional[Dict[str, Any]]:
        """
        Fetch live population/age data from the DOSM parquet file.

        Data source: https://storage.dosm.gov.my/population/population_district.parquet

        Args:
            district: Penang district name

        Returns:
            Dictionary with age_distribution, total_population, and data_source,
            or None if the fetch fails.
        """
        try:
            logger.info(f"Fetching population data from DOSM parquet for district: {district}")

            df = pd.read_parquet(self.DOSM_PARQUET_URL)

            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])

            # Filter for the specific district, both sexes, overall ethnicity
            district_df = df[
                (df["state"] == "Pulau Pinang")
                & (df["district"] == district)
                & (df["sex"] == "both")
                & (df["ethnicity"] == "overall")
                & (df["age"] != "overall")
            ]

            if district_df.empty:
                logger.warning(f"No parquet data found for district: {district}")
                return None

            # Use the most recent date
            latest_date = district_df["date"].max()
            district_df = district_df[district_df["date"] == latest_date]

            date_str = latest_date.strftime("%Y-%m-%d")
            logger.info(f"Using DOSM data from: {date_str}")

            return self._transform_to_age_distribution(district_df, district, date_str)

        except Exception as e:
            logger.warning(f"Failed to fetch DOSM parquet data for {district}: {e}")
            return None

    def _transform_to_age_distribution(
        self, df: "pd.DataFrame", district: str, date_str: str
    ) -> Optional[Dict[str, Any]]:
        """
        Transform a filtered DataFrame into the grouped age distribution format.

        Args:
            df: Filtered DataFrame with columns: age, population (in thousands)
            district: District name
            date_str: Date string for the data

        Returns:
            Dictionary with age_distribution, total_population, data_source
        """
        age_band_populations: Dict[str, float] = {band: 0.0 for band in self.AGE_GROUPS}
        total_population = 0.0

        for _, row in df.iterrows():
            age_band_5yr = row["age"]
            population = row["population"] * 1000  # Convert from thousands

            grouped_band = self.AGE_BAND_MAPPING.get(age_band_5yr)
            if grouped_band:
                age_band_populations[grouped_band] += population
                total_population += population
            else:
                logger.debug(f"Unmapped age band: {age_band_5yr}")

        if total_population == 0:
            logger.warning(f"Total population is 0 for {district}")
            return None

        age_distribution = {}
        for band, count in age_band_populations.items():
            percentage = round((count / total_population) * 100, 1)
            age_distribution[band] = {
                "percentage": percentage,
                "count": int(round(count)),
            }

        logger.info(
            f"DOSM: {district} total population = {int(total_population):,} "
            f"(date: {date_str})"
        )

        return {
            "age_distribution": age_distribution,
            "total_population": int(round(total_population)),
            "data_source": f"DOSM Open Data (population_district.parquet, {date_str})",
        }

    def fetch_all_penang_districts(self) -> Dict[str, Any]:
        """
        Fetch population data for all Penang districts from the DOSM parquet file.

        Returns:
            Dictionary with district data, or empty dict on failure.
        """
        try:
            logger.info("Fetching all Penang district population data from DOSM")

            df = pd.read_parquet(self.DOSM_PARQUET_URL)

            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])

            penang_df = df[
                (df["state"] == "Pulau Pinang")
                & (df["sex"] == "both")
                & (df["ethnicity"] == "overall")
                & (df["age"] != "overall")
            ]

            if penang_df.empty:
                return {}

            latest_date = penang_df["date"].max()
            penang_df = penang_df[penang_df["date"] == latest_date]
            date_str = latest_date.strftime("%Y-%m-%d")

            results = {}
            for district in self.PENANG_DISTRICTS:
                district_df = penang_df[penang_df["district"] == district]
                if not district_df.empty:
                    transformed = self._transform_to_age_distribution(
                        district_df, district, date_str
                    )
                    if transformed:
                        results[district] = transformed

            return results

        except Exception as e:
            logger.error(f"Failed to fetch all Penang districts: {e}")
            return {}

    # -------------------------------------------------------------------------
    # Spending & Payment Patterns
    # -------------------------------------------------------------------------

    def _get_penang_spending_patterns(self, district: str) -> Dict[str, Any]:
        """Get spending patterns for Penang districts."""
        if district in ["Barat Daya", "Timur Laut"]:
            return {
                "food_beverage": {"percentage": 29.0, "avg_monthly_rm": 900, "description": "Food and beverages including dining out"},
                "transport": {"percentage": 15.0, "avg_monthly_rm": 500, "description": "Transportation and fuel"},
                "housing": {"percentage": 24.0, "avg_monthly_rm": 950, "description": "Rent, mortgage, and housing costs"},
                "utilities": {"percentage": 8.0, "avg_monthly_rm": 250, "description": "Electricity, water, internet"},
                "healthcare": {"percentage": 5.0, "avg_monthly_rm": 150, "description": "Medical expenses and insurance"},
                "education": {"percentage": 6.0, "avg_monthly_rm": 200, "description": "Education and training"},
                "recreation": {"percentage": 9.0, "avg_monthly_rm": 280, "description": "Entertainment and leisure"},
                "others": {"percentage": 4.0, "avg_monthly_rm": 120, "description": "Other expenses"},
            }
        else:
            return {
                "food_beverage": {"percentage": 27.0, "avg_monthly_rm": 750, "description": "Food and beverages including dining out"},
                "transport": {"percentage": 16.0, "avg_monthly_rm": 430, "description": "Transportation and fuel"},
                "housing": {"percentage": 23.0, "avg_monthly_rm": 750, "description": "Rent, mortgage, and housing costs"},
                "utilities": {"percentage": 9.0, "avg_monthly_rm": 240, "description": "Electricity, water, internet"},
                "healthcare": {"percentage": 5.0, "avg_monthly_rm": 130, "description": "Medical expenses and insurance"},
                "education": {"percentage": 6.0, "avg_monthly_rm": 160, "description": "Education and training"},
                "recreation": {"percentage": 7.0, "avg_monthly_rm": 190, "description": "Entertainment and leisure"},
                "others": {"percentage": 7.0, "avg_monthly_rm": 180, "description": "Other expenses"},
            }

    def _get_penang_payment_preferences(self, district: str) -> Dict[str, Any]:
        """Get payment preferences for Penang districts."""
        if district in ["Timur Laut", "Barat Daya"]:
            return {
                "cash": {"percentage": 38.0, "description": "Physical cash payments"},
                "card": {"percentage": 32.0, "description": "Credit/debit card payments"},
                "ewallet": {"percentage": 25.0, "description": "E-wallet (Touch 'n Go, GrabPay, etc.)"},
                "online_banking": {"percentage": 5.0, "description": "Online banking transfers"},
            }
        else:
            return {
                "cash": {"percentage": 45.0, "description": "Physical cash payments"},
                "card": {"percentage": 28.0, "description": "Credit/debit card payments"},
                "ewallet": {"percentage": 22.0, "description": "E-wallet (Touch 'n Go, GrabPay, etc.)"},
                "online_banking": {"percentage": 5.0, "description": "Online banking transfers"},
            }

    # -------------------------------------------------------------------------
    # Income Estimation
    # -------------------------------------------------------------------------

    def _estimate_median_income(
        self, household_dist: Dict[str, float],
        start_percentile: float, end_percentile: float
    ) -> int:
        """Estimate median income for a group based on household distribution."""
        income_midpoints = {
            "1999_and_below": 1000,
            "2000_2999": 2500,
            "3000_3999": 3500,
            "4000_4999": 4500,
            "5000_5999": 5500,
            "6000_6999": 6500,
            "7000_7999": 7500,
            "8000_8999": 8500,
            "9000_9999": 9500,
            "10000_10999": 10500,
            "11000_11999": 11500,
            "12000_12999": 12500,
            "13000_13999": 13500,
            "14000_14999": 14500,
            "15000_and_above": 18000,
        }

        cumulative = 0.0
        target_percentile = (start_percentile + end_percentile) / 2

        for income_class in sorted(household_dist.keys()):
            percentage = household_dist[income_class]
            cumulative += percentage
            if cumulative >= target_percentile:
                return income_midpoints.get(income_class, 10000)

        return 10000

    # -------------------------------------------------------------------------
    # Location Mapping
    # -------------------------------------------------------------------------

    def map_location_to_district(self, location: str) -> str:
        """Map a location string to a Malaysian district name."""
        location_lower = location.lower()

        penang_districts = {
            "Timur Laut": [
                "georgetown", "george town", "pulau tikus", "tanjung bungah",
                "batu ferringhi", "air itam", "jelutong", "northeast", "timur laut",
            ],
            "Barat Daya": [
                "balik pulau", "bayan lepas", "teluk kumbar", "gertak sanggul",
                "southwest", "barat daya",
            ],
            "Seberang Perai Tengah": [
                "butterworth", "bukit mertajam", "alma", "perai",
                "central seberang perai", "seberang perai tengah",
            ],
            "Seberang Perai Utara": [
                "kepala batas", "tasek gelugor", "bertam", "penaga",
                "north seberang perai", "seberang perai utara",
            ],
            "Seberang Perai Selatan": [
                "nibong tebal", "simpang ampat", "batu kawan", "jawi",
                "south seberang perai", "seberang perai selatan",
            ],
        }

        for district, keywords in penang_districts.items():
            if any(keyword in location_lower for keyword in keywords):
                return district

        if any(keyword in location_lower for keyword in ["penang", "pulau pinang", "pinang"]):
            return "Timur Laut"

        district_mapping = {
            "Kuala Lumpur": ["kuala lumpur", "kl", "klcc", "bukit bintang", "cheras", "bangsar"],
            "Petaling": ["petaling jaya", "pj", "subang", "shah alam"],
            "Johor Bahru": ["johor bahru", "jb", "johor"],
            "Ipoh": ["ipoh", "perak"],
            "Melaka": ["melaka", "malacca"],
            "Seremban": ["seremban", "negeri sembilan"],
            "Kota Kinabalu": ["kota kinabalu", "kk", "sabah"],
            "Kuching": ["kuching", "sarawak"],
        }

        for district, keywords in district_mapping.items():
            if any(keyword in location_lower for keyword in keywords):
                return district

        return "Kuala Lumpur"

    async def health_check(self) -> bool:
        """
        Check if data sources are accessible.

        Returns:
            True if at least one data source is available
        """
        local_available = self.penang_data_path.exists()

        parquet_available = False
        try:
            response = requests.head(self.DOSM_PARQUET_URL, timeout=5)
            parquet_available = response.status_code == 200
        except requests.RequestException:
            pass

        if parquet_available:
            logger.info("DOSM parquet data source is available")
        else:
            logger.info("DOSM parquet unavailable")

        return local_available or parquet_available

    def get_available_districts(self) -> list[str]:
        """Get list of available Penang districts."""
        return list(self.PENANG_DISTRICTS)
