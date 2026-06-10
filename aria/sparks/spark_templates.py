"""
Hard-coded Spark template catalogue.

No database reads required at runtime for template definitions —
templates are defined here as Python constants.
"""

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class SparkQuestion:
    id: str
    label: str
    text: str


@dataclass
class SparkTemplate:
    id: str
    name: str
    description: str
    questions: List[SparkQuestion] = field(default_factory=list)


SPARK_TEMPLATES: Dict[str, SparkTemplate] = {
    "competitive_context": SparkTemplate(
        id="competitive_context",
        name="Competitive Context",
        description="Tell ARIA about your nearby competitors so simulations reflect real competitive pressure.",
        questions=[
            SparkQuestion(
                id="comp_names_count",
                label="Competitor names & count",
                text="How many direct competitors do you have within a 5-minute walk, and what are their names (if known)?",
            ),
            SparkQuestion(
                id="comp_pricing",
                label="Competitor pricing",
                text="Are their prices generally higher, similar, or lower than yours? Any rough percentage difference?",
            ),
            SparkQuestion(
                id="comp_offerings",
                label="Competitor key offerings",
                text="What are the key products or services your competitors offer that you don't (or do differently)?",
            ),
        ],
    ),
    "location_context": SparkTemplate(
        id="location_context",
        name="Location Context",
        description="Describe your location's foot traffic and surroundings to help ARIA generate location-aware scenarios.",
        questions=[
            SparkQuestion(
                id="loc_traffic_type",
                label="Foot traffic type",
                text="What is the predominant type of foot traffic near your business? (e.g., residential, office workers, commuters, tourists, school crowd)",
            ),
            SparkQuestion(
                id="loc_landmarks",
                label="Nearby landmarks & transport",
                text="What key landmarks, transport nodes, or anchor tenants are near you? (e.g., LRT station, hospital, shopping mall, night market)",
            ),
            SparkQuestion(
                id="loc_area_type",
                label="Area character",
                text="Is your immediate area primarily residential, commercial, or mixed? Does it feel busy or quiet on a typical weekday?",
            ),
        ],
    ),
    "business_hours_seasonality": SparkTemplate(
        id="business_hours_seasonality",
        name="Business Hours & Seasonality",
        description="Capture your peak periods and seasonal patterns so ARIA can simulate demand surges and slow spells accurately.",
        questions=[
            SparkQuestion(
                id="bhs_peak_hours",
                label="Peak trading hours & days",
                text="What are your busiest hours and days of the week? (e.g., lunch hour Mon–Fri, Saturday afternoon)",
            ),
            SparkQuestion(
                id="bhs_seasonal_peaks",
                label="Seasonal / event-driven peaks",
                text="Are there recurring seasonal periods or local events that significantly boost your demand? (e.g., Hari Raya prep week, school holidays, Penang food festival)",
            ),
            SparkQuestion(
                id="bhs_slow_periods",
                label="Typical slow periods",
                text="When are your slowest periods? (e.g., mid-week afternoons, post-Raya, monsoon season)",
            ),
        ],
    ),
}
