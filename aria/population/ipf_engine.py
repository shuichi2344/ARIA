"""
Iterative Proportional Fitting (IPF) Engine for Synthetic Population Generation.
Generates joint distributions of age and income that match DOSM marginal totals.
"""

import numpy as np
from typing import Dict, Any, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class IPFConvergenceError(Exception):
    """Exception raised when IPF fails to converge."""
    pass


class IPFEngine:
    """
    Iterative Proportional Fitting engine for generating synthetic populations.
    
    IPF adjusts a seed matrix to match target marginal distributions for
    age and income, creating a joint probability distribution.
    """
    
    def __init__(
        self,
        convergence_threshold: float = 0.0001,  # 0.01%
        max_iterations: int = 1000
    ):
        """
        Initialize IPF Engine.
        
        Args:
            convergence_threshold: Maximum acceptable error (default: 0.0001 = 0.01%)
            max_iterations: Maximum number of iterations (default: 1000)
        """
        self.convergence_threshold = convergence_threshold
        self.max_iterations = max_iterations
        
        # Age groups (rows)
        self.age_groups = ["20-29", "30-39", "40-49", "50-59", "60+"]
        
        # Income groups (columns)
        self.income_groups = ["B40", "M40", "T20"]
    
    def fit(
        self,
        age_marginals: Dict[str, float],
        income_marginals: Dict[str, float]
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Execute IPF to generate joint distribution matching marginal totals.
        
        Args:
            age_marginals: Dict mapping age groups to percentages (must sum to 100)
            income_marginals: Dict mapping income groups to percentages (must sum to 100)
        
        Returns:
            Tuple of (joint_distribution_matrix, convergence_report)
        
        Raises:
            IPFConvergenceError: If IPF fails to converge
        """
        logger.info(f"Starting IPF with threshold={self.convergence_threshold}, max_iter={self.max_iterations}")
        logger.info(f"Age marginals: {age_marginals}")
        logger.info(f"Income marginals: {income_marginals}")
        
        # Validate and normalize marginals
        age_marginals = self._normalize_marginals(age_marginals, "age")
        income_marginals = self._normalize_marginals(income_marginals, "income")
        
        # Convert to arrays (as proportions, not percentages)
        age_targets = np.array([age_marginals.get(ag, 0.0) / 100.0 for ag in self.age_groups])
        income_targets = np.array([income_marginals.get(ig, 0.0) / 100.0 for ig in self.income_groups])
        
        # Initialize uniform seed matrix
        seed_matrix = self._initialize_seed_matrix()
        
        # Execute IPF iterations
        joint_dist, iterations, max_error = self._ipf_iterate(
            seed_matrix, age_targets, income_targets
        )
        
        # Validate convergence
        if max_error > self.convergence_threshold:
            logger.warning(f"IPF did not fully converge. Max error: {max_error:.6f}")
        
        # Generate convergence report
        report = self._generate_convergence_report(
            joint_dist, age_targets, income_targets, iterations, max_error
        )
        
        logger.info(f"IPF completed in {iterations} iterations with max error {max_error:.6f}")
        
        return joint_dist, report
    
    def _normalize_marginals(
        self,
        marginals: Dict[str, float],
        name: str
    ) -> Dict[str, float]:
        """
        Normalize marginals to sum to 100%.
        
        Args:
            marginals: Dictionary of marginal values
            name: Name for logging (age/income)
        
        Returns:
            Normalized marginals
        """
        total = sum(marginals.values())
        
        if total == 0:
            raise ValueError(f"{name} marginals sum to zero")
        
        if any(v < 0 for v in marginals.values()):
            raise ValueError(f"{name} marginals contain negative values")
        
        if abs(total - 100.0) > 0.1:
            logger.warning(f"{name} marginals sum to {total:.2f}%, normalizing to 100%")
            return {k: (v / total) * 100.0 for k, v in marginals.items()}
        
        return marginals
    
    def _initialize_seed_matrix(self) -> np.ndarray:
        """
        Initialize uniform seed matrix.
        
        Returns:
            Seed matrix with uniform probabilities
        """
        n_age = len(self.age_groups)
        n_income = len(self.income_groups)
        
        # Uniform probability for each cell
        uniform_prob = 1.0 / (n_age * n_income)
        
        seed = np.full((n_age, n_income), uniform_prob)
        
        logger.debug(f"Initialized {n_age}x{n_income} seed matrix with uniform probability {uniform_prob:.6f}")
        
        return seed
    
    def _ipf_iterate(
        self,
        seed: np.ndarray,
        age_targets: np.ndarray,
        income_targets: np.ndarray
    ) -> Tuple[np.ndarray, int, float]:
        """
        Execute IPF iterative scaling.
        
        Args:
            seed: Initial seed matrix
            age_targets: Target age distribution (as proportions)
            income_targets: Target income distribution (as proportions)
        
        Returns:
            Tuple of (converged_matrix, iterations, max_error)
        """
        matrix = seed.copy()
        
        for iteration in range(self.max_iterations):
            # Scale rows to match age distribution
            row_sums = matrix.sum(axis=1, keepdims=True)
            row_sums = np.where(row_sums == 0, 1, row_sums)  # Avoid division by zero
            matrix = matrix * (age_targets.reshape(-1, 1) / row_sums)
            
            # Scale columns to match income distribution
            col_sums = matrix.sum(axis=0, keepdims=True)
            col_sums = np.where(col_sums == 0, 1, col_sums)  # Avoid division by zero
            matrix = matrix * (income_targets.reshape(1, -1) / col_sums)
            
            # Check convergence
            current_age = matrix.sum(axis=1)
            current_income = matrix.sum(axis=0)
            
            age_error = np.abs(current_age - age_targets).max()
            income_error = np.abs(current_income - income_targets).max()
            max_error = max(age_error, income_error)
            
            if max_error < self.convergence_threshold:
                logger.debug(f"Converged at iteration {iteration + 1}")
                return matrix, iteration + 1, max_error
            
            # Log progress every 100 iterations
            if (iteration + 1) % 100 == 0:
                logger.debug(f"Iteration {iteration + 1}: max_error={max_error:.6f}")
        
        # Did not converge within max iterations
        logger.warning(f"IPF did not converge after {self.max_iterations} iterations")
        return matrix, self.max_iterations, max_error
    
    def _generate_convergence_report(
        self,
        joint_dist: np.ndarray,
        age_targets: np.ndarray,
        income_targets: np.ndarray,
        iterations: int,
        max_error: float
    ) -> Dict[str, Any]:
        """
        Generate convergence report with validation metrics.
        
        Args:
            joint_dist: Final joint distribution matrix
            age_targets: Target age distribution
            income_targets: Target income distribution
            iterations: Number of iterations executed
            max_error: Maximum error achieved
        
        Returns:
            Convergence report dictionary
        """
        # Calculate actual marginals from joint distribution
        actual_age = joint_dist.sum(axis=1)
        actual_income = joint_dist.sum(axis=0)
        
        # Calculate errors
        age_errors = {
            self.age_groups[i]: {
                "target": float(age_targets[i] * 100),
                "actual": float(actual_age[i] * 100),
                "error": float(abs(actual_age[i] - age_targets[i]) * 100)
            }
            for i in range(len(self.age_groups))
        }
        
        income_errors = {
            self.income_groups[i]: {
                "target": float(income_targets[i] * 100),
                "actual": float(actual_income[i] * 100),
                "error": float(abs(actual_income[i] - income_targets[i]) * 100)
            }
            for i in range(len(self.income_groups))
        }
        
        # Calculate confidence score (0-100%)
        # 100% if max_error = 0, decreases as error increases
        confidence = max(0, 100 * (1 - (max_error / 0.01)))  # 1% error = 0% confidence
        
        # Check if converged
        converged = max_error < self.convergence_threshold
        
        return {
            "converged": converged,
            "iterations": iterations,
            "max_error": float(max_error * 100),  # Convert to percentage
            "confidence_score": float(confidence),
            "age_distribution": age_errors,
            "income_distribution": income_errors,
            "joint_distribution_sum": float(joint_dist.sum())
        }
    
    def sample_agents(
        self,
        joint_dist: np.ndarray,
        n_agents: int,
        random_seed: Optional[int] = None
    ) -> List[Tuple[str, str]]:
        """
        Sample agents from joint distribution using multinomial sampling.
        
        Args:
            joint_dist: Joint probability distribution matrix
            n_agents: Number of agents to sample
            random_seed: Random seed for reproducibility
        
        Returns:
            List of (age_group, income_level) tuples
        """
        if n_agents < 5:
            logger.warning(f"Sampling only {n_agents} agents may result in high variance")
        
        if n_agents > 1000:
            logger.warning(f"Sampling {n_agents} agents may impact performance")
        
        # Set random seed if provided
        if random_seed is not None:
            np.random.seed(random_seed)
        
        # Flatten joint distribution to 1D probability array
        probs = joint_dist.flatten()
        
        # Ensure probabilities sum to 1.0
        probs = probs / probs.sum()
        
        # Sample from multinomial distribution
        samples = np.random.multinomial(n_agents, probs)
        
        # Convert samples to agent list
        agents = []
        idx = 0
        for i, age_group in enumerate(self.age_groups):
            for j, income_level in enumerate(self.income_groups):
                count = samples[idx]
                agents.extend([(age_group, income_level)] * count)
                idx += 1
        
        logger.info(f"Sampled {len(agents)} agents from joint distribution")
        
        return agents
    
    def validate_sample(
        self,
        agents: List[Tuple[str, str]],
        age_targets: Dict[str, float],
        income_targets: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Validate sampled agents against target distributions.
        
        Args:
            agents: List of (age_group, income_level) tuples
            age_targets: Target age distribution (percentages)
            income_targets: Target income distribution (percentages)
        
        Returns:
            Validation report with error metrics
        """
        n_agents = len(agents)
        
        # Count actual distribution
        age_counts = {ag: 0 for ag in self.age_groups}
        income_counts = {ig: 0 for ig in self.income_groups}
        
        for age_group, income_level in agents:
            age_counts[age_group] += 1
            income_counts[income_level] += 1
        
        # Calculate actual percentages
        age_actual = {ag: (count / n_agents) * 100 for ag, count in age_counts.items()}
        income_actual = {ig: (count / n_agents) * 100 for ig, count in income_counts.items()}
        
        # Calculate errors
        age_errors = {
            ag: abs(age_actual[ag] - age_targets.get(ag, 0.0))
            for ag in self.age_groups
        }
        
        income_errors = {
            ig: abs(income_actual[ig] - income_targets.get(ig, 0.0))
            for ig in self.income_groups
        }
        
        max_age_error = max(age_errors.values())
        max_income_error = max(income_errors.values())
        
        return {
            "n_agents": n_agents,
            "age_distribution": {
                ag: {
                    "target": age_targets.get(ag, 0.0),
                    "actual": age_actual[ag],
                    "error": age_errors[ag]
                }
                for ag in self.age_groups
            },
            "income_distribution": {
                ig: {
                    "target": income_targets.get(ig, 0.0),
                    "actual": income_actual[ig],
                    "error": income_errors[ig]
                }
                for ig in self.income_groups
            },
            "max_age_error": max_age_error,
            "max_income_error": max_income_error,
            "overall_max_error": max(max_age_error, max_income_error)
        }
