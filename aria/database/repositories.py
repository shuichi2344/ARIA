"""
Database repository layer for ARIA.
Provides CRUD operations and common query patterns for all models.
"""

from typing import Optional, List, Sequence
from datetime import datetime
from uuid import UUID
from sqlalchemy import select, update, delete, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from aria.database.models import (
    User, BusinessProfile, Archetype, Scenario, Simulation,
    SimulationEvent, AgentInteraction, SimulationAnalysis,
    MarketImpactReport, ErrorLog, SimulationStatus
)


# ============================================================================
# User Repository
# ============================================================================

async def create_user(session: AsyncSession, email: str, password_hash: str) -> User:
    """Create a new user."""
    user = User(email=email, password_hash=password_hash)
    session.add(user)
    await session.flush()
    return user


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> Optional[User]:
    """Get user by ID."""
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    """Get user by email."""
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


# ============================================================================
# Business Profile Repository
# ============================================================================

async def create_business_profile(
    session: AsyncSession,
    user_id: UUID,
    business_name: str,
    business_type: str,
    location: str,
    **kwargs
) -> BusinessProfile:
    """Create a new business profile."""
    profile = BusinessProfile(
        user_id=user_id,
        business_name=business_name,
        business_type=business_type,
        location=location,
        **kwargs
    )
    session.add(profile)
    await session.flush()
    return profile


async def get_business_profile_by_id(
    session: AsyncSession,
    profile_id: UUID
) -> Optional[BusinessProfile]:
    """Get business profile by ID."""
    result = await session.execute(
        select(BusinessProfile).where(BusinessProfile.id == profile_id)
    )
    return result.scalar_one_or_none()


async def get_business_profiles_by_user(
    session: AsyncSession,
    user_id: UUID
) -> Sequence[BusinessProfile]:
    """Get all business profiles for a user."""
    result = await session.execute(
        select(BusinessProfile)
        .where(BusinessProfile.user_id == user_id)
        .order_by(desc(BusinessProfile.created_at))
    )
    return result.scalars().all()


async def update_business_profile(
    session: AsyncSession,
    profile_id: UUID,
    **kwargs
) -> Optional[BusinessProfile]:
    """Update business profile fields."""
    kwargs['updated_at'] = datetime.utcnow()
    await session.execute(
        update(BusinessProfile)
        .where(BusinessProfile.id == profile_id)
        .values(**kwargs)
    )
    return await get_business_profile_by_id(session, profile_id)


# ============================================================================
# Archetype Repository
# ============================================================================

async def create_archetype(
    session: AsyncSession,
    business_profile_id: UUID,
    persona_name: str,
    income_level: str,
    age_range: str,
    spending_pattern: dict,
    loyalty_traits: dict,
    payment_preferences: dict,
    base_susceptibility: float
) -> Archetype:
    """Create a new archetype."""
    archetype = Archetype(
        business_profile_id=business_profile_id,
        persona_name=persona_name,
        income_level=income_level,
        age_range=age_range,
        spending_pattern=spending_pattern,
        loyalty_traits=loyalty_traits,
        payment_preferences=payment_preferences,
        base_susceptibility=base_susceptibility
    )
    session.add(archetype)
    await session.flush()
    return archetype


async def get_archetypes_by_business_profile(
    session: AsyncSession,
    business_profile_id: UUID
) -> Sequence[Archetype]:
    """Get all archetypes for a business profile."""
    result = await session.execute(
        select(Archetype)
        .where(Archetype.business_profile_id == business_profile_id)
        .order_by(Archetype.income_level, Archetype.persona_name)
    )
    return result.scalars().all()


async def delete_archetypes_by_business_profile(
    session: AsyncSession,
    business_profile_id: UUID
):
    """Delete all archetypes for a business profile."""
    await session.execute(
        delete(Archetype).where(Archetype.business_profile_id == business_profile_id)
    )


# ============================================================================
# Scenario Repository
# ============================================================================

async def create_scenario(
    session: AsyncSession,
    business_profile_id: UUID,
    scenario_name: str,
    scenario_type: str,
    parameters: dict,
    description: str,
    duration_weeks: int = 4
) -> Scenario:
    """Create a new scenario."""
    scenario = Scenario(
        business_profile_id=business_profile_id,
        scenario_name=scenario_name,
        scenario_type=scenario_type,
        parameters=parameters,
        description=description,
        duration_weeks=duration_weeks
    )
    session.add(scenario)
    await session.flush()
    return scenario


async def get_scenario_by_id(session: AsyncSession, scenario_id: UUID) -> Optional[Scenario]:
    """Get scenario by ID."""
    result = await session.execute(select(Scenario).where(Scenario.id == scenario_id))
    return result.scalar_one_or_none()


async def get_scenarios_by_business_profile(
    session: AsyncSession,
    business_profile_id: UUID
) -> Sequence[Scenario]:
    """Get all scenarios for a business profile."""
    result = await session.execute(
        select(Scenario)
        .where(Scenario.business_profile_id == business_profile_id)
        .order_by(desc(Scenario.created_at))
    )
    return result.scalars().all()


# ============================================================================
# Simulation Repository
# ============================================================================

async def create_simulation(
    session: AsyncSession,
    scenario_id: UUID,
    duration_weeks: int,
    agent_count: int
) -> Simulation:
    """Create a new simulation."""
    simulation = Simulation(
        scenario_id=scenario_id,
        duration_weeks=duration_weeks,
        agent_count=agent_count,
        status=SimulationStatus.PENDING
    )
    session.add(simulation)
    await session.flush()
    return simulation


async def get_simulation_by_id(
    session: AsyncSession,
    simulation_id: UUID,
    load_relationships: bool = False
) -> Optional[Simulation]:
    """Get simulation by ID with optional relationship loading."""
    query = select(Simulation).where(Simulation.id == simulation_id)
    
    if load_relationships:
        query = query.options(
            selectinload(Simulation.scenario),
            selectinload(Simulation.events),
            selectinload(Simulation.interactions)
        )
    
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_simulations_by_scenario(
    session: AsyncSession,
    scenario_id: UUID
) -> Sequence[Simulation]:
    """Get all simulations for a scenario."""
    result = await session.execute(
        select(Simulation)
        .where(Simulation.scenario_id == scenario_id)
        .order_by(desc(Simulation.created_at))
    )
    return result.scalars().all()


async def update_simulation_status(
    session: AsyncSession,
    simulation_id: UUID,
    status: SimulationStatus,
    **kwargs
) -> Optional[Simulation]:
    """Update simulation status and optional fields."""
    update_data = {"status": status, **kwargs}
    
    if status == SimulationStatus.RUNNING and "started_at" not in kwargs:
        update_data["started_at"] = datetime.utcnow()
    elif status == SimulationStatus.COMPLETED and "completed_at" not in kwargs:
        update_data["completed_at"] = datetime.utcnow()
    
    await session.execute(
        update(Simulation)
        .where(Simulation.id == simulation_id)
        .values(**update_data)
    )
    return await get_simulation_by_id(session, simulation_id)


async def update_simulation_progress(
    session: AsyncSession,
    simulation_id: UUID,
    current_week: int,
    progress_percentage: float
):
    """Update simulation progress."""
    await session.execute(
        update(Simulation)
        .where(Simulation.id == simulation_id)
        .values(current_week=current_week, progress_percentage=progress_percentage)
    )


async def link_simulation_to_economic_context(
    session: AsyncSession,
    simulation_id: UUID,
    economic_context_id: UUID
):
    """Link simulation to economic context."""
    await session.execute(
        update(Simulation)
        .where(Simulation.id == simulation_id)
        .values(economic_context_id=economic_context_id)
    )
    await session.commit()


# ============================================================================
# Simulation Event Repository
# ============================================================================

async def create_simulation_event(
    session: AsyncSession,
    simulation_id: UUID,
    week: int,
    agent_id: int,
    archetype_id: UUID,
    decision: str,
    reasoning: str,
    susceptibility_score: float,
    visited: bool,
    spend_amount: float = 0.0
) -> SimulationEvent:
    """Create a new simulation event."""
    event = SimulationEvent(
        simulation_id=simulation_id,
        week=week,
        agent_id=agent_id,
        archetype_id=archetype_id,
        decision=decision,
        reasoning=reasoning,
        susceptibility_score=susceptibility_score,
        visited=visited,
        spend_amount=spend_amount
    )
    session.add(event)
    await session.flush()
    return event


async def get_simulation_events(
    session: AsyncSession,
    simulation_id: UUID,
    week: Optional[int] = None
) -> Sequence[SimulationEvent]:
    """Get simulation events, optionally filtered by week."""
    query = select(SimulationEvent).where(SimulationEvent.simulation_id == simulation_id)
    
    if week is not None:
        query = query.where(SimulationEvent.week == week)
    
    query = query.order_by(SimulationEvent.week, SimulationEvent.agent_id)
    result = await session.execute(query)
    return result.scalars().all()


# ============================================================================
# Agent Interaction Repository
# ============================================================================

async def create_agent_interaction(
    session: AsyncSession,
    simulation_id: UUID,
    week: int,
    agent_id: int,
    peer_agent_id: int,
    interaction_type: str,
    content: str
) -> AgentInteraction:
    """Create a new agent interaction."""
    interaction = AgentInteraction(
        simulation_id=simulation_id,
        week=week,
        agent_id=agent_id,
        peer_agent_id=peer_agent_id,
        interaction_type=interaction_type,
        content=content
    )
    session.add(interaction)
    await session.flush()
    return interaction


async def get_agent_interactions(
    session: AsyncSession,
    simulation_id: UUID,
    week: Optional[int] = None
) -> Sequence[AgentInteraction]:
    """Get agent interactions, optionally filtered by week."""
    query = select(AgentInteraction).where(AgentInteraction.simulation_id == simulation_id)
    
    if week is not None:
        query = query.where(AgentInteraction.week == week)
    
    query = query.order_by(AgentInteraction.week, AgentInteraction.recorded_at)
    result = await session.execute(query)
    return result.scalars().all()


# ============================================================================
# Simulation Analysis Repository
# ============================================================================

async def create_simulation_analysis(
    session: AsyncSession,
    simulation_id: UUID,
    overall_risk_rating: float,
    churn_risk_percentage: float,
    revenue_impact_estimate: float,
    time_to_impact_weeks: int,
    confidence_level: float,
    confidence_factors: dict,
    archetype_susceptibility_scores: dict,
    trends: dict,
    insights: dict
) -> SimulationAnalysis:
    """Create a new simulation analysis."""
    analysis = SimulationAnalysis(
        simulation_id=simulation_id,
        overall_risk_rating=overall_risk_rating,
        churn_risk_percentage=churn_risk_percentage,
        revenue_impact_estimate=revenue_impact_estimate,
        time_to_impact_weeks=time_to_impact_weeks,
        confidence_level=confidence_level,
        confidence_factors=confidence_factors,
        archetype_susceptibility_scores=archetype_susceptibility_scores,
        trends=trends,
        insights=insights
    )
    session.add(analysis)
    await session.flush()
    return analysis


async def get_analysis_by_simulation(
    session: AsyncSession,
    simulation_id: UUID
) -> Optional[SimulationAnalysis]:
    """Get analysis for a simulation."""
    result = await session.execute(
        select(SimulationAnalysis).where(SimulationAnalysis.simulation_id == simulation_id)
    )
    return result.scalar_one_or_none()


# ============================================================================
# Market Impact Report Repository
# ============================================================================

async def create_market_impact_report(
    session: AsyncSession,
    analysis_id: UUID,
    risk_summary: dict,
    archetype_breakdown: dict,
    visualizations: dict,
    recommendations: list,
    pdf_url: Optional[str] = None,
    csv_url: Optional[str] = None
) -> MarketImpactReport:
    """Create a new market impact report."""
    import json
    report = MarketImpactReport(
        simulation_analysis_id=analysis_id,
        risk_summary=json.dumps(risk_summary),
        archetype_breakdown=archetype_breakdown,
        visualizations=visualizations,
        recommendations=recommendations,
        pdf_url=pdf_url,
        csv_url=csv_url
    )
    session.add(report)
    await session.flush()
    return report


async def get_report_by_analysis(
    session: AsyncSession,
    analysis_id: UUID
) -> Optional[MarketImpactReport]:
    """Get report for an analysis."""
    result = await session.execute(
        select(MarketImpactReport).where(MarketImpactReport.simulation_analysis_id == analysis_id)
    )
    return result.scalar_one_or_none()


async def update_report_exports(
    session: AsyncSession,
    report_id: UUID,
    pdf_url: Optional[str] = None,
    csv_url: Optional[str] = None
):
    """Update report export URLs."""
    update_data = {}
    if pdf_url is not None:
        update_data["pdf_url"] = pdf_url
    if csv_url is not None:
        update_data["csv_url"] = csv_url
    
    if update_data:
        await session.execute(
            update(MarketImpactReport)
            .where(MarketImpactReport.id == report_id)
            .values(**update_data)
        )


# ============================================================================
# Error Log Repository
# ============================================================================

async def create_error_log(
    session: AsyncSession,
    component: str,
    error_type: str,
    error_message: str,
    context: Optional[dict] = None
) -> ErrorLog:
    """Create a new error log entry."""
    error_log = ErrorLog(
        service=component,
        error_type=error_type,
        error_message=error_message,
        context=context
    )
    session.add(error_log)
    await session.flush()
    return error_log


async def get_recent_errors(
    session: AsyncSession,
    component: Optional[str] = None,
    limit: int = 100
) -> Sequence[ErrorLog]:
    """Get recent error logs, optionally filtered by component."""
    query = select(ErrorLog)
    
    if component is not None:
        query = query.where(ErrorLog.service == component)
    
    query = query.order_by(desc(ErrorLog.timestamp)).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()
