"""
ARIA Mesa Model for agent-based simulation.
Implements the main simulation model using Mesa framework.
"""

import mesa
from typing import Dict, Any, List


class ARIAModel(mesa.Model):
    """
    Main simulation model for ARIA.
    Manages customer agents and tracks simulation metrics.
    """
    
    def __init__(
        self,
        scenario: Dict[str, Any],
        archetypes: List[Dict[str, Any]],
        agent_count: int = 15,
        business_profile: Dict[str, Any] = None
    ):
        """
        Initialize ARIA simulation model.
        
        Args:
            scenario: Scenario parameters
            archetypes: List of customer archetypes
            agent_count: Number of agents to create
            business_profile: Business profile with location and pricing context
        """
        super().__init__()
        
        self.scenario = scenario
        self.archetypes = archetypes
        self.agent_count = agent_count
        self.business_profile = business_profile  # Store for agent access
        
        self.current_week = 0
        
        # Simulation metrics
        self.total_visits = 0
        self.total_revenue = 0.0
        self.active_agents = agent_count
        
        # Store agents in a list (Mesa 3.x doesn't use schedule the same way)
        self.agents_list = []
    
    def step(self):
        """
        Advance the simulation by one week.
        All agents make decisions and take actions.
        """
        self.current_week += 1
        
        # Reset weekly metrics
        self.total_visits = 0
        self.total_revenue = 0.0
        
        # All agents take their turn
        for agent in self.agents_list:
            agent.step()
    
    def count_visits(self) -> int:
        """
        Count total visits this week.
        
        Returns:
            Number of visits
        """
        visits = sum(
            1 for agent in self.agents_list
            if hasattr(agent, 'visited_this_week') and agent.visited_this_week
        )
        return visits
    
    def calculate_revenue(self) -> float:
        """
        Calculate total revenue this week.
        
        Returns:
            Total revenue in RM
        """
        revenue = sum(
            agent.spend_this_week
            for agent in self.agents_list
            if hasattr(agent, 'spend_this_week')
        )
        return revenue
    
    def count_active_agents(self) -> int:
        """
        Count number of active (non-churned) agents.
        
        Returns:
            Number of active agents
        """
        active = sum(
            1 for agent in self.agents_list
            if hasattr(agent, 'is_active') and agent.is_active
        )
        return active
    
    def calculate_avg_susceptibility(self) -> float:
        """
        Calculate average susceptibility score across all agents.
        
        Returns:
            Average susceptibility score
        """
        active_agents = [
            agent for agent in self.agents_list
            if hasattr(agent, 'is_active') and agent.is_active
        ]
        
        if not active_agents:
            return 0.0
        
        # Calculate churn risk based on recent negative experiences in memory
        total_risk = 0.0
        for agent in active_agents:
            if hasattr(agent, 'memory') and agent.memory:
                recent_memory = agent.memory[-5:]
                negative_count = sum(
                    1 for memory in recent_memory 
                    if any(word in memory.lower() for word in ['churn', 'stop', 'negative', 'skip'])
                )
                # Risk score: 0-10 based on negative experiences
                risk = min(10.0, (negative_count / 5.0) * 10.0)
                total_risk += risk
        
        return total_risk / len(active_agents)
    
    def get_agents_by_income_level(self, income_level: str) -> List:
        """
        Get all agents of a specific income level.
        
        Args:
            income_level: B40, M40, or T20
        
        Returns:
            List of agents
        """
        return [
            agent for agent in self.agents_list
            if hasattr(agent, 'archetype') and 
            agent.archetype.get('income_level') == income_level
        ]
    
    def get_simulation_summary(self) -> Dict[str, Any]:
        """
        Get summary of simulation state.
        
        Returns:
            Dictionary with simulation metrics
        """
        return {
            "current_week": self.current_week,
            "total_visits": self.count_visits(),
            "total_revenue": self.calculate_revenue(),
            "active_agents": self.count_active_agents(),
            "churned_agents": self.agent_count - self.count_active_agents(),
            "avg_susceptibility": self.calculate_avg_susceptibility()
        }
    
    def get_agent_data(self) -> List[Dict[str, Any]]:
        """
        Get data for all agents.
        
        Returns:
            List of agent data dictionaries
        """
        return [
            {
                "agent_id": agent.unique_id,
                "persona_name": agent.archetype["persona_name"],
                "income_level": agent.archetype["income_level"],
                "age_range": agent.archetype["age_range"],
                "is_active": agent.is_active,
                "visited_this_week": agent.visited_this_week,
                "spend_this_week": agent.spend_this_week,
                "total_visits": len([m for m in agent.memory if "visited" in m.lower()]),
                "last_decision": agent.memory[-1] if agent.memory else None
            }
            for agent in self.agents_list
            if hasattr(agent, 'archetype')
        ]
