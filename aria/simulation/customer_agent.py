"""
Customer Agent for ARIA simulation.
Represents individual customer behavior using Mesa agent framework.
Uses LLM for decision-making with cultural context.
"""

import mesa
from typing import Dict, Any, List, Optional
from aria.simulation.llm_agent_brain import LLMAgentBrain


class CustomerAgent(mesa.Agent):
    """
    Customer agent that makes decisions about visiting a business.
    Hybrid approach: Mesa for structure/state, LLM for decisions.
    """
    
    def __init__(
        self,
        unique_id: int,
        model: mesa.Model,
        archetype: Dict[str, Any],
        llm_brain: Optional[LLMAgentBrain] = None,
        economic_context: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize customer agent.
        
        Args:
            unique_id: Unique agent identifier
            model: Mesa model instance
            archetype: Customer archetype data
            llm_brain: LLM brain for decision-making
            economic_context: Economic context for decision-making
        """
        super().__init__(unique_id, model)
        
        self.unique_id = unique_id
        self.archetype = archetype
        self.llm_brain = llm_brain or LLMAgentBrain()
        self.economic_context = economic_context
        
        # Agent identity
        self.income_level: str = archetype.get('income_level', 'M40')
        self.age_range: str = archetype.get('age_range', '25-34')
        self.profile_text: str = ""  # Set after LLM profile generation
        self.personality_type: str = "customer"
        
        # Agent state
        self.memory: List[str] = []
        self.visited_this_week = False
        self.spend_this_week = 0.0
        self.is_active = True  # False if churned
        self.last_decision: Optional[str] = None
        self.reasoning: Optional[str] = None
        
        # Peer influence
        self.influencing_peers: List['CustomerAgent'] = []
    
    def get_peer_messages(self) -> List[str]:
        """
        Get reasoning from same-income peers who already decided.
        
        Returns:
            List of peer reasoning strings
        """
        peers = [
            agent for agent in self.model.agents_list
            if agent.unique_id != self.unique_id
            and agent.income_level == self.income_level
            and agent.last_decision is not None
            and agent.is_active
        ]
        
        messages = []
        self.influencing_peers = []
        for peer in peers[:3]:
            if peer.reasoning:
                messages.append(peer.reasoning)
                self.influencing_peers.append(peer)
        
        return messages
    
    async def make_decision(
        self,
        scenario_context: Dict[str, Any],
        business_context: Optional[Dict[str, Any]] = None,
        use_peer_influence: bool = False
    ) -> Dict[str, Any]:
        """
        Make a decision using LLM brain.
        
        Args:
            scenario_context: Scenario info (description, type, parameters)
            business_context: Business info (name, type, location, prices)
            use_peer_influence: Whether to include peer messages
        
        Returns:
            Dict with keys: decision, message, spend_amount
        """
        peer_messages = self.get_peer_messages() if use_peer_influence else None
        
        spark_section = scenario_context.get("spark_section", "") if isinstance(scenario_context, dict) else ""

        result = await self.llm_brain.make_decision_and_message(
            agent_profile=self.profile_text,
            scenario_context=scenario_context,
            business_context=business_context,
            peer_messages=peer_messages if peer_messages else None,
            income_level=self.income_level,
            spark_section=spark_section
        )
        
        # Update state
        self.last_decision = result["decision"]
        self.reasoning = result["message"]
        
        if result["decision"] == "churn":
            self.is_active = False
            self.memory.append(f"Decided to stop visiting. {result['message']}")
        elif result["decision"] == "skip":
            self.visited_this_week = False
            self.spend_this_week = 0.0
            self.memory.append(f"Skipped. {result['message']}")
        else:  # visit
            self.visited_this_week = True
            self.spend_this_week = result["spend_amount"]
            self.memory.append(f"Visited, spent RM{result['spend_amount']:.2f}. {result['message']}")
        
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize agent state for SSE events and frontend."""
        return {
            "agent_id": self.unique_id,
            "income_level": self.income_level,
            "age_range": self.age_range,
            "profile_text": self.profile_text,
            "personality": self.profile_text,
            "personality_type": self.personality_type,
            "is_active": self.is_active,
            "last_decision": self.last_decision,
            "reasoning": self.reasoning,
            "spend_this_week": self.spend_this_week,
            "visited_this_week": self.visited_this_week,
        }
