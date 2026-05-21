"""
Database layer for ARIA.
Handles database models, connections, and data access.
"""

from aria.database.models import (
    Base,
    User,
    BusinessProfile,
    Archetype,
    Scenario,
    Simulation,
    SimulationEvent,
    AgentInteraction,
    SimulationAnalysis,
    MarketImpactReport,
    ErrorLog,
    SimulationStatus,
    RiskLevel,
)

from aria.database.connection import (
    get_engine,
    get_session_factory,
    get_session,
    check_connection,
    close_engine,
)

from aria.database import repositories

__all__ = [
    # Models
    "Base",
    "User",
    "BusinessProfile",
    "Archetype",
    "Scenario",
    "Simulation",
    "SimulationEvent",
    "AgentInteraction",
    "SimulationAnalysis",
    "MarketImpactReport",
    "ErrorLog",
    "SimulationStatus",
    "RiskLevel",
    # Connection
    "get_engine",
    "get_session_factory",
    "get_session",
    "check_connection",
    "close_engine",
    # Repositories
    "repositories",
]
