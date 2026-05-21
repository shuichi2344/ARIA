"""
SQLAlchemy ORM models for ARIA database.
Maps to Supabase PostgreSQL tables defined in migrations/001_initial_schema.sql
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4
from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, Text, JSON, Enum,
    ForeignKey, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class SimulationStatus(str, enum.Enum):
    """Simulation status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class RiskLevel(str, enum.Enum):
    """Risk level enumeration."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class User(Base):
    """User account model."""
    __tablename__ = "users"
    
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    business_profiles: Mapped[List["BusinessProfile"]] = relationship(
        "BusinessProfile", back_populates="user", cascade="all, delete-orphan"
    )


class BusinessProfile(Base):
    """Business profile model."""
    __tablename__ = "business_profiles"
    
    profile_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_type: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    district: Mapped[Optional[str]] = mapped_column(String(100))
    price_range_min: Mapped[Optional[float]] = mapped_column(Float)
    price_range_max: Mapped[Optional[float]] = mapped_column(Float)
    target_audience: Mapped[Optional[str]] = mapped_column(Text)
    unique_selling_points: Mapped[Optional[str]] = mapped_column(Text)
    years_operating: Mapped[Optional[int]] = mapped_column(Integer)
    data_source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="business_profiles")
    archetypes: Mapped[List["Archetype"]] = relationship(
        "Archetype", back_populates="business_profile", cascade="all, delete-orphan"
    )
    scenarios: Mapped[List["Scenario"]] = relationship(
        "Scenario", back_populates="business_profile", cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index("idx_business_profiles_user_id", "user_id"),
        Index("idx_business_profiles_years_operating", "years_operating"),
        CheckConstraint("price_range_min >= 0", name="check_price_range_min"),
        CheckConstraint("price_range_max >= price_range_min", name="check_price_range_max"),
        CheckConstraint("years_operating >= 0 AND years_operating <= 200", name="check_years_operating"),
    )


class Archetype(Base):
    """Consumer archetype model."""
    __tablename__ = "archetypes"
    
    archetype_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    profile_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("business_profiles.profile_id", ondelete="CASCADE"), nullable=False
    )
    persona_name: Mapped[str] = mapped_column(String(255), nullable=False)
    income_level: Mapped[str] = mapped_column(String(10), nullable=False)
    age_range: Mapped[str] = mapped_column(String(20), nullable=False)
    spending_pattern: Mapped[dict] = mapped_column(JSON, nullable=False)
    loyalty_traits: Mapped[dict] = mapped_column(JSON, nullable=False)
    payment_preferences: Mapped[dict] = mapped_column(JSON, nullable=False)
    base_susceptibility: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    business_profile: Mapped["BusinessProfile"] = relationship("BusinessProfile", back_populates="archetypes")
    
    __table_args__ = (
        Index("idx_archetypes_business_profile_id", "profile_id"),
        CheckConstraint("income_level IN ('B40', 'M40', 'T20')", name="check_income_level"),
        CheckConstraint("base_susceptibility >= 0 AND base_susceptibility <= 10", name="check_base_susceptibility"),
    )


class Scenario(Base):
    """Simulation scenario model."""
    __tablename__ = "scenarios"
    
    scenario_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    profile_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("business_profiles.profile_id", ondelete="CASCADE"), nullable=False
    )
    scenario_name: Mapped[str] = mapped_column(String(255), nullable=False)
    scenario_type: Mapped[str] = mapped_column(String(100), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    duration_weeks: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    business_profile: Mapped["BusinessProfile"] = relationship("BusinessProfile", back_populates="scenarios")
    simulations: Mapped[List["Simulation"]] = relationship(
        "Simulation", back_populates="scenario", cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index("idx_scenarios_business_profile_id", "profile_id"),
        CheckConstraint("duration_weeks >= 1 AND duration_weeks <= 52", name="check_duration_weeks"),
    )


class Simulation(Base):
    """Simulation run model."""
    __tablename__ = "simulations"
    
    simulation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    scenario_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("scenarios.scenario_id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[SimulationStatus] = mapped_column(
        String(50), nullable=False, default=SimulationStatus.PENDING
    )
    duration_weeks: Mapped[int] = mapped_column(Integer, nullable=False)
    agent_count: Mapped[int] = mapped_column(Integer, nullable=False)
    current_week: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_percentage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="simulations")
    events: Mapped[List["SimulationEvent"]] = relationship(
        "SimulationEvent", back_populates="simulation", cascade="all, delete-orphan"
    )
    interactions: Mapped[List["AgentInteraction"]] = relationship(
        "AgentInteraction", back_populates="simulation", cascade="all, delete-orphan"
    )
    analysis: Mapped[Optional["SimulationAnalysis"]] = relationship(
        "SimulationAnalysis", back_populates="simulation", uselist=False, cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index("idx_simulations_scenario_id", "scenario_id"),
        Index("idx_simulations_status", "status"),
        CheckConstraint("duration_weeks >= 1 AND duration_weeks <= 52", name="check_duration_weeks"),
        CheckConstraint("agent_count >= 5 AND agent_count <= 50", name="check_agent_count"),
        CheckConstraint("current_week >= 0", name="check_current_week"),
        CheckConstraint("progress_percentage >= 0 AND progress_percentage <= 100", name="check_progress_percentage"),
    )


class SimulationEvent(Base):
    """Individual agent decision event model."""
    __tablename__ = "simulation_events"
    
    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    simulation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("simulations.simulation_id", ondelete="CASCADE"), nullable=False
    )
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    agent_id: Mapped[int] = mapped_column(Integer, nullable=False)
    archetype_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("archetypes.archetype_id", ondelete="CASCADE"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    susceptibility_score: Mapped[float] = mapped_column(Float, nullable=False)
    visited: Mapped[bool] = mapped_column(Boolean, nullable=False)
    spend_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    simulation: Mapped["Simulation"] = relationship("Simulation", back_populates="events")
    
    __table_args__ = (
        Index("idx_simulation_events_simulation_id", "simulation_id"),
        Index("idx_simulation_events_week", "week"),
        CheckConstraint("susceptibility_score >= 0 AND susceptibility_score <= 10", name="check_susceptibility_score"),
        CheckConstraint("spend_amount >= 0", name="check_spend_amount"),
    )


class AgentInteraction(Base):
    """Agent-to-agent interaction model."""
    __tablename__ = "agent_interactions"
    
    interaction_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    simulation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("simulations.simulation_id", ondelete="CASCADE"), nullable=False
    )
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    agent_id: Mapped[int] = mapped_column(Integer, nullable=False)
    peer_agent_id: Mapped[int] = mapped_column(Integer, nullable=False)
    interaction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    simulation: Mapped["Simulation"] = relationship("Simulation", back_populates="interactions")
    
    __table_args__ = (
        Index("idx_agent_interactions_simulation_id", "simulation_id"),
        Index("idx_agent_interactions_week", "week"),
    )


class SimulationAnalysis(Base):
    """Simulation analysis results model."""
    __tablename__ = "simulation_analysis"
    
    analysis_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    simulation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("simulations.simulation_id", ondelete="CASCADE"), nullable=False, unique=True
    )
    overall_risk_rating: Mapped[float] = mapped_column(Float, nullable=False)
    churn_risk_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    revenue_impact_estimate: Mapped[float] = mapped_column(Float, nullable=False)
    time_to_impact_weeks: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_level: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_factors: Mapped[dict] = mapped_column(JSON, nullable=False)
    archetype_susceptibility_scores: Mapped[dict] = mapped_column(JSON, nullable=False)
    trends: Mapped[dict] = mapped_column(JSON, nullable=False)
    insights: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    simulation: Mapped["Simulation"] = relationship("Simulation", back_populates="analysis")
    report: Mapped[Optional["MarketImpactReport"]] = relationship(
        "MarketImpactReport", back_populates="analysis", uselist=False, cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index("idx_simulation_analysis_simulation_id", "simulation_id"),
        CheckConstraint("churn_risk_percentage >= 0 AND churn_risk_percentage <= 100", name="check_churn_risk"),
        CheckConstraint("confidence_level >= 0 AND confidence_level <= 100", name="check_confidence_level"),
    )


class MarketImpactReport(Base):
    """Market impact report model."""
    __tablename__ = "market_impact_reports"
    
    report_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    analysis_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("simulation_analysis.analysis_id", ondelete="CASCADE"), nullable=False, unique=True
    )
    risk_summary: Mapped[str] = mapped_column(String, nullable=False)
    archetype_breakdown: Mapped[dict] = mapped_column(JSON, nullable=False)
    visualizations: Mapped[dict] = mapped_column(JSON, nullable=False)
    recommendations: Mapped[dict] = mapped_column(JSON, nullable=False)
    pdf_url: Mapped[Optional[str]] = mapped_column(String(500))
    csv_url: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    analysis: Mapped["SimulationAnalysis"] = relationship("SimulationAnalysis", back_populates="report")
    
    __table_args__ = (
        Index("idx_market_impact_reports_analysis_id", "analysis_id"),
    )


class ErrorLog(Base):
    """Error logging model."""
    __tablename__ = "error_logs"
    
    log_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    service: Mapped[str] = mapped_column(String(100), nullable=False)
    error_type: Mapped[str] = mapped_column(String(100), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[Optional[dict]] = mapped_column(JSON)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index("idx_error_logs_service", "service"),
        Index("idx_error_logs_timestamp", "timestamp"),
    )

