"""
Population generation module for ARIA.
Includes IPF-based synthetic population generation.
"""

from aria.population.ipf_engine import IPFEngine, IPFConvergenceError
from aria.population.synthetic_population import SyntheticPopulationGenerator

__all__ = [
    "IPFEngine",
    "IPFConvergenceError",
    "SyntheticPopulationGenerator"
]
