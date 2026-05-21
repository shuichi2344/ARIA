"""
Archetype Generator for ARIA.
Generates synthetic populations using IPF-based demographic matching.
Maintains backward compatibility with existing archetype system.
"""

from typing import Dict, Any, List
from aria.external import DOSMClient
from aria.population import SyntheticPopulationGenerator
from aria.database.connection import get_session
from aria.database import repositories
import logging

logger = logging.getLogger(__name__)


class ArchetypeGenerator:
    """
    Agent for generating customer archetypes using IPF-based synthetic populations.
    
    Replaces arbitrary archetype generation with statistically valid populations
    that match DOSM marginal distributions for age and income.
    """
    
    def __init__(self, use_ipf: bool = True):
        """
        Initialize Archetype Generator.
        
        Args:
            use_ipf: Whether to use IPF (True) or fallback to simple sampling (False)
        """
        self.dosm_client = DOSMClient()
        self.population_generator = SyntheticPopulationGenerator(use_ipf=use_ipf)
        self.use_ipf = use_ipf
        
        logger.info(f"ArchetypeGenerator initialized with IPF={'enabled' if use_ipf else 'disabled'}")
    
    async def fetch_demographics(
        self,
        location: str
    ) -> Dict[str, Any]:
        """
        Fetch demographic data for location.
        
        Args:
            location: Business location
        
        Returns:
            Demographic data dictionary
        """
        # Map location to district
        district = self.dosm_client.map_location_to_district(location)
        
        # Get demographics (with automatic fallback to static data)
        demographics = await self.dosm_client.get_demographics(district)
        
        return demographics
    
    async def generate_archetypes(
        self,
        business_profile: Dict[str, Any],
        count: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Generate customer archetypes using IPF-based synthetic population.
        
        Args:
            business_profile: Business profile data including location
            count: Number of archetypes to generate (default: 100)
        
        Returns:
            List of archetype dictionaries with complete attributes
        """
        logger.info(f"Generating {count} archetypes for business: {business_profile.get('name', 'Unknown')}")
        
        # Generate synthetic population using IPF
        result = await self.population_generator.generate_population(
            business_profile=business_profile,
            count=count
        )
        
        agents = result["agents"]
        method_used = result["method_used"]
        
        # Log generation details
        logger.info(f"Generated {len(agents)} agents using method: {method_used}")
        
        if method_used == "ipf" and result.get("convergence_report"):
            conv_report = result["convergence_report"]
            logger.info(f"IPF Convergence: {conv_report['converged']}, "
                       f"Confidence: {conv_report['confidence_score']:.1f}%, "
                       f"Iterations: {conv_report['iterations']}")
            
            if result.get("validation_report"):
                val_report = result["validation_report"]
                logger.info(f"Validation max error: {val_report['overall_max_error']:.2f}%")
        
        return agents
    

    
    async def save_archetypes(
        self,
        business_profile_id: int,
        archetypes: List[Dict[str, Any]]
    ) -> List[int]:
        """
        Save archetypes to database.
        
        Args:
            business_profile_id: Business profile ID
            archetypes: List of archetype dictionaries
        
        Returns:
            List of created archetype IDs
        """
        archetype_ids = []
        
        async with get_session() as session:
            # Delete existing archetypes for this profile
            await repositories.delete_archetypes_by_business_profile(
                session=session,
                business_profile_id=business_profile_id
            )
            
            # Create new archetypes
            for archetype_data in archetypes:
                archetype = await repositories.create_archetype(
                    session=session,
                    business_profile_id=business_profile_id,
                    persona_name=archetype_data["persona_name"],
                    income_level=archetype_data["income_level"],
                    age_range=archetype_data["age_range"],
                    spending_pattern=archetype_data["spending_pattern"],
                    loyalty_traits=archetype_data["loyalty_traits"],
                    payment_preferences=archetype_data["payment_preferences"],
                    base_susceptibility=archetype_data["base_susceptibility"]
                )
                archetype_ids.append(archetype.id)
        
        return archetype_ids
    
    async def get_archetypes(
        self,
        business_profile_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get archetypes for a business profile.
        
        Args:
            business_profile_id: Business profile ID
        
        Returns:
            List of archetype dictionaries
        """
        async with get_session() as session:
            archetypes = await repositories.get_archetypes_by_business_profile(
                session=session,
                business_profile_id=business_profile_id
            )
            
            return [
                {
                    "id": a.id,
                    "persona_name": a.persona_name,
                    "income_level": a.income_level,
                    "age_range": a.age_range,
                    "spending_pattern": a.spending_pattern,
                    "loyalty_traits": a.loyalty_traits,
                    "payment_preferences": a.payment_preferences,
                    "base_susceptibility": a.base_susceptibility
                }
                for a in archetypes
            ]
