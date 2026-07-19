"""
Synthetic Population Generator using IPF.
Replaces arbitrary archetype generation with statistically valid synthetic populations.
"""

import logging
from typing import Dict, Any, List, Optional
import random

from aria.population.ipf_engine import IPFEngine, IPFConvergenceError
from aria.external import DOSMClient

logger = logging.getLogger(__name__)


class SyntheticPopulationGenerator:
    """
    Generates synthetic populations using Iterative Proportional Fitting (IPF).
    
    Creates agents with joint age-income distributions that match DOSM data,
    then assigns detailed attributes based on demographics and business profile.
    """
    
    def __init__(
        self,
        use_ipf: bool = True,
        convergence_threshold: float = 0.0001,
        max_iterations: int = 1000
    ):
        """
        Initialize Synthetic Population Generator.
        
        Args:
            use_ipf: Whether to use IPF (True) or fall back to simple sampling (False)
            convergence_threshold: IPF convergence threshold
            max_iterations: Maximum IPF iterations
        """
        self.use_ipf = use_ipf
        self.dosm_client = DOSMClient()
        self.ipf_engine = IPFEngine(
            convergence_threshold=convergence_threshold,
            max_iterations=max_iterations
        )
    
    async def generate_population(
        self,
        business_profile: Dict[str, Any],
        count: int = 100,
        income_constraints: Optional[List[str]] = None,
        age_constraints: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate synthetic population for a business.
        
        Args:
            business_profile: Business profile data including location
            count: Number of agents to generate
            income_constraints: Optional list of allowed income levels (e.g., ['T20'] or ['B40', 'M40'])
            age_constraints: Optional list of allowed age groups (e.g., ['25-34', '35-44'])
        
        Returns:
            Dictionary containing:
                - agents: List of agent dictionaries
                - validation_report: IPF validation metrics
                - convergence_report: IPF convergence details
                - method_used: "ipf" or "fallback"
        """
        logger.info(f"Generating synthetic population of {count} agents")
        logger.info(f"Business: {business_profile.get('name', 'Unknown')} at {business_profile.get('location', 'Unknown')}")
        
        if income_constraints:
            logger.info(f"Income constraints: {income_constraints}")
        if age_constraints:
            logger.info(f"Age constraints: {age_constraints}")
        
        # Fetch demographics for business location
        location = business_profile.get("location", "Timur Laut")
        district = self.dosm_client.map_location_to_district(location)
        demographics = await self.dosm_client.get_demographics(district)
        
        logger.info(f"Using demographics for district: {district}")
        
        # Extract marginal distributions
        age_marginals = self._extract_age_marginals(demographics, age_constraints)
        income_marginals = self._extract_income_marginals(demographics, income_constraints)
        
        # Generate population using IPF or fallback
        if self.use_ipf:
            try:
                result = await self._generate_with_ipf(
                    age_marginals=age_marginals,
                    income_marginals=income_marginals,
                    demographics=demographics,
                    count=count
                )
                result["method_used"] = "ipf"
                return result
            
            except (IPFConvergenceError, Exception) as e:
                logger.error(f"IPF generation failed: {e}, falling back to simple sampling")
                result = self._generate_with_fallback(
                    age_marginals=age_marginals,
                    income_marginals=income_marginals,
                    demographics=demographics,
                    count=count
                )
                result["method_used"] = "fallback"
                result["fallback_reason"] = str(e)
                return result
        else:
            logger.info("IPF disabled, using fallback method")
            result = self._generate_with_fallback(
                age_marginals=age_marginals,
                income_marginals=income_marginals,
                demographics=demographics,
                count=count
            )
            result["method_used"] = "fallback"
            return result
    
    def _extract_age_marginals(self, demographics: Dict[str, Any], age_constraints: Optional[List[str]] = None) -> Dict[str, float]:
        """
        Extract age marginals from demographics data.
        
        Args:
            demographics: Demographics data
            age_constraints: Optional list of allowed age groups
        
        Returns:
            Dictionary of age group percentages (normalized if constrained)
        """
        age_dist = demographics.get("age_distribution", {})
        
        # Filter to only relevant age groups (20+)
        adult_age_groups = ["20-29", "30-39", "40-49", "50-59", "60+"]
        
        marginals = {}
        for age_group in adult_age_groups:
            # Skip if constraints specified and this group not in constraints
            if age_constraints and age_group not in age_constraints:
                continue
                
            data = age_dist.get(age_group, {})
            percentage = data.get("percentage", 0.0) if isinstance(data, dict) else data
            marginals[age_group] = percentage
        
        # Renormalize if constrained (so percentages sum to 100)
        if age_constraints and marginals:
            total = sum(marginals.values())
            if total > 0:
                marginals = {k: (v / total) * 100 for k, v in marginals.items()}
        
        return marginals
    
    def _extract_income_marginals(self, demographics: Dict[str, Any], income_constraints: Optional[List[str]] = None) -> Dict[str, float]:
        """
        Extract income marginals from demographics data.
        
        Args:
            demographics: Demographics data
            income_constraints: Optional list of allowed income levels
        
        Returns:
            Dictionary of income level percentages (normalized if constrained)
        """
        income_dist = demographics.get("income_distribution", {})
        
        marginals = {}
        for income_level, data in income_dist.items():
            # Skip if constraints specified and this level not in constraints
            if income_constraints and income_level not in income_constraints:
                continue
                
            marginals[income_level] = data.get("percentage", 0.0)
        
        # Renormalize if constrained (so percentages sum to 100)
        if income_constraints and marginals:
            total = sum(marginals.values())
            if total > 0:
                marginals = {k: (v / total) * 100 for k, v in marginals.items()}
        
        return marginals
    
    async def _generate_with_ipf(
        self,
        age_marginals: Dict[str, float],
        income_marginals: Dict[str, float],
        demographics: Dict[str, Any],
        count: int
    ) -> Dict[str, Any]:
        """Generate population using IPF."""
        logger.info("Using IPF method for population generation")
        
        # Run IPF to get joint distribution
        joint_dist, convergence_report = self.ipf_engine.fit(
            age_marginals=age_marginals,
            income_marginals=income_marginals
        )
        
        # Sample agents from joint distribution
        agent_samples = self.ipf_engine.sample_agents(
            joint_dist=joint_dist,
            n_agents=count
        )
        
        # Validate sample
        validation_report = self.ipf_engine.validate_sample(
            agents=agent_samples,
            age_targets=age_marginals,
            income_targets=income_marginals
        )
        
        # Assign detailed attributes to agents
        agents = self._assign_agent_attributes(
            agent_samples=agent_samples,
            demographics=demographics
        )
        
        logger.info(f"Generated {len(agents)} agents using IPF")
        logger.info(f"Convergence: {convergence_report['converged']}, Confidence: {convergence_report['confidence_score']:.1f}%")
        logger.info(f"Validation max error: {validation_report['overall_max_error']:.2f}%")
        
        return {
            "agents": agents,
            "convergence_report": convergence_report,
            "validation_report": validation_report,
            "district": demographics.get("district", "Unknown"),
            "source": demographics.get("source", "Unknown")
        }
    
    def _generate_with_fallback(
        self,
        age_marginals: Dict[str, float],
        income_marginals: Dict[str, float],
        demographics: Dict[str, Any],
        count: int
    ) -> Dict[str, Any]:
        """Generate population using simple independent sampling (fallback)."""
        logger.info("Using fallback method for population generation")
        
        # Sample age and income independently (not joint distribution)
        agent_samples = []
        
        age_groups = list(age_marginals.keys())
        age_probs = [age_marginals[ag] / 100.0 for ag in age_groups] if age_groups else []
        
        # Fallback: if no age marginals, use equal distribution across age constraints
        if not age_groups:
            age_groups = self.age_constraints if self.age_constraints else ['25-34', '35-44', '45-54']
            age_probs = [1.0 / len(age_groups)] * len(age_groups)
        
        income_levels = list(income_marginals.keys())
        income_probs = [income_marginals[il] / 100.0 for il in income_levels] if income_levels else []
        
        # Fallback: if no income marginals, use equal distribution
        if not income_levels:
            income_levels = self.income_constraints if self.income_constraints else ['B40', 'M40', 'T20']
            income_probs = [1.0 / len(income_levels)] * len(income_levels)
        
        for _ in range(count):
            age_group = random.choices(age_groups, weights=age_probs, k=1)[0]
            income_level = random.choices(income_levels, weights=income_probs, k=1)[0]
            agent_samples.append((age_group, income_level))
        
        # Assign detailed attributes
        agents = self._assign_agent_attributes(
            agent_samples=agent_samples,
            demographics=demographics
        )
        
        logger.info(f"Generated {len(agents)} agents using fallback method")
        
        return {
            "agents": agents,
            "convergence_report": None,
            "validation_report": None,
            "district": demographics.get("district", "Unknown"),
            "source": demographics.get("source", "Unknown")
        }
    
    def _assign_agent_attributes(
        self,
        agent_samples: List[tuple[str, str]],
        demographics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Assign detailed attributes to sampled agents.

        Args:
            agent_samples: List of (age_group, income_level) tuples
            demographics: Demographics data

        Returns:
            List of complete agent dictionaries
        """
        return [
            self._create_agent(
                agent_index=idx,
                age_group=age_group,
                income_level=income_level,
                demographics=demographics
            )
            for idx, (age_group, income_level) in enumerate(agent_samples)
        ]

    def _create_agent(
        self,
        agent_index: int,
        age_group: str,
        income_level: str,
        demographics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a single agent with demographic attributes.

        Args:
            agent_index: Zero-based index used to generate a simple agent label
            age_group: Age group (e.g., "20-29")
            income_level: Income level (B40/M40/T20)
            demographics: Demographics data

        Returns:
            Agent dictionary with income_level, age_range, and monthly_income_rm
        """
        income_data = demographics.get("income_distribution", {}).get(income_level, {})
        median_income = income_data.get("median_income_rm", 5000)

        return {
            "persona_name": f"Agent {agent_index + 1}",
            "income_level": income_level,
            "age_range": age_group,
            "monthly_income_rm": median_income,
        }
