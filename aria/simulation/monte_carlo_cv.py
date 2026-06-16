"""
Monte Carlo Coefficient of Variation (CV) stopping criterion.

Instead of running a fixed number of simulations, ARIA uses a dynamic stopping rule
based on statistical convergence. The Coefficient of Variation (CV) measures the 
relative variability of results:

    CV = (standard_deviation / mean) * 100

When CV drops below a threshold (e.g., 5%), the results are statistically stable
and we can stop early, saving LLM API costs and computation time.

This module provides real-time CV tracking across multiple simulation runs.
"""

import statistics
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class MonteCarloConfig:
    """Configuration for Monte Carlo simulation stopping criterion."""
    min_runs: int = 5           # Always run at least this many times
    max_runs: int = 30          # Never exceed this limit
    cv_threshold: float = 5.0   # Stop when CV <= this % (relative std dev)
    
    # Weighted Composite Index (WCI) weights
    # WCI = (visits × visit_weight) + (skips × skip_weight) + (churns × churn_weight)
    visit_weight: float = 1.0   # Full value: customer visited, revenue generated
    skip_weight: float = 0.5    # Half value: customer retained, no revenue this week
    churn_weight: float = 0.0   # Zero value: customer lost permanently
    
    primary_metric: str = "wci"  # Default to Weighted Composite Index
    
    def __post_init__(self):
        """Validate configuration."""
        if self.min_runs < 2:
            raise ValueError("min_runs must be at least 2 for CV calculation")
        if self.max_runs < self.min_runs:
            raise ValueError("max_runs must be >= min_runs")
        if self.cv_threshold <= 0:
            raise ValueError("cv_threshold must be positive")
        if self.primary_metric not in ["wci", "churn_rate", "total_visits"]:
            raise ValueError(f"primary_metric must be one of: wci, churn_rate, total_visits")


@dataclass
class RunResult:
    """Results from a single simulation run."""
    run_number: int
    visits: int              # Number of agents who visited
    skips: int               # Number of agents who skipped
    churns: int              # Number of agents who churned
    churn_rate: float        # Percentage of agents who churned (for compatibility)
    total_visits: int        # Total visits across all weeks (for compatibility)
    total_revenue: float     # Total revenue generated
    active_agents: int       # Number of agents still active at end
    metadata: Optional[Dict[str, Any]] = None  # Additional run-specific data


class MonteCarloTracker:
    """
    Tracks Monte Carlo simulation runs and determines when to stop based on CV.
    
    Usage:
        config = MonteCarloConfig(min_runs=5, max_runs=30, cv_threshold=5.0)
        tracker = MonteCarloTracker(config)
        
        for run in range(config.max_runs):
            # Run simulation...
            result = RunResult(
                run_number=run + 1,
                churn_rate=calculate_churn_rate(),
                total_visits=count_visits(),
                total_revenue=sum_revenue(),
                active_agents=count_active()
            )
            
            should_stop = tracker.add_run(result)
            
            if should_stop:
                print(f"Converged after {run + 1} runs!")
                break
    """
    
    def __init__(self, config: MonteCarloConfig):
        """Initialize tracker with configuration."""
        self.config = config
        self.runs: List[RunResult] = []
        
        # Track individual metrics
        self._churn_rates: List[float] = []
        self._total_visits: List[int] = []
        
        # Track behavioral counts
        self._visits: List[int] = []
        self._skips: List[int] = []
        self._churns: List[int] = []
        
        # Track Weighted Composite Index
        self._wci_scores: List[float] = []
    
    def _calculate_wci(self, visits: int, skips: int, churns: int) -> float:
        """
        Calculate Weighted Composite Index for a run.
        
        WCI = (visits × visit_weight) + (skips × skip_weight) + (churns × churn_weight)
        
        This creates a single business health score that captures the economic
        impact of all agent decisions in a run.
        
        Args:
            visits: Number of agents who visited
            skips: Number of agents who skipped
            churns: Number of agents who churned
        
        Returns:
            Weighted composite index score
        """
        return (
            visits * self.config.visit_weight +
            skips * self.config.skip_weight +
            churns * self.config.churn_weight
        )
    
    def add_run(self, result: RunResult) -> bool:
        """
        Add a run result and check if we should stop.
        
        Args:
            result: Results from the latest simulation run
        
        Returns:
            True if simulation should stop (converged or hit max runs), False otherwise
        """
        self.runs.append(result)
        self._churn_rates.append(result.churn_rate)
        self._total_visits.append(result.total_visits)
        
        # Track behavioral counts
        self._visits.append(result.visits)
        self._skips.append(result.skips)
        self._churns.append(result.churns)
        
        # Calculate and track WCI
        wci_score = self._calculate_wci(result.visits, result.skips, result.churns)
        self._wci_scores.append(wci_score)
        
        # Check stopping criteria
        return self.should_stop()
    
    def should_stop(self) -> bool:
        """
        Determine if simulation should stop based on convergence or limits.
        
        Returns:
            True if we should stop, False if we should continue
        """
        num_runs = len(self.runs)
        
        # Always stop at max runs
        if num_runs >= self.config.max_runs:
            return True
        
        # Don't stop before minimum runs
        if num_runs < self.config.min_runs:
            return False
        
        # Check if primary metric has converged
        cv = self.get_cv(self.config.primary_metric)
        
        if cv is not None and cv <= self.config.cv_threshold:
            return True
        
        return False
    
    def get_cv(self, metric: str = "wci") -> Optional[float]:
        """
        Calculate Coefficient of Variation for a metric.
        
        CV = (std_dev / mean) * 100
        
        Args:
            metric: Which metric to calculate CV for 
                   ("wci", "churn_rate", "total_visits", "visits", "skips", "churns")
        
        Returns:
            CV percentage, or None if not enough data or mean is zero
        """
        if len(self.runs) < 2:
            return None
        
        if metric == "wci":
            values = self._wci_scores
        elif metric == "churn_rate":
            values = self._churn_rates
        elif metric == "total_visits":
            values = self._total_visits
        elif metric == "visits":
            values = self._visits
        elif metric == "skips":
            values = self._skips
        elif metric == "churns":
            values = self._churns
        else:
            raise ValueError(f"Unknown metric: {metric}")
        
        mean = statistics.mean(values)
        
        # Can't calculate CV if mean is zero (avoid division by zero)
        if mean == 0:
            return None
        
        std_dev = statistics.stdev(values)
        cv = (std_dev / mean) * 100
        
        return cv
    
    def get_mean(self, metric: str = "wci") -> Optional[float]:
        """Get mean value of a metric across all runs."""
        if not self.runs:
            return None
        
        if metric == "wci":
            return statistics.mean(self._wci_scores)
        elif metric == "churn_rate":
            return statistics.mean(self._churn_rates)
        elif metric == "total_visits":
            return statistics.mean(self._total_visits)
        elif metric == "total_revenue":
            return statistics.mean([r.total_revenue for r in self.runs])
        elif metric == "active_agents":
            return statistics.mean([r.active_agents for r in self.runs])
        elif metric == "visits":
            return statistics.mean(self._visits)
        elif metric == "skips":
            return statistics.mean(self._skips)
        elif metric == "churns":
            return statistics.mean(self._churns)
        else:
            raise ValueError(f"Unknown metric: {metric}")
    
    def get_std_dev(self, metric: str = "wci") -> Optional[float]:
        """Get standard deviation of a metric across all runs."""
        if len(self.runs) < 2:
            return None
        
        if metric == "wci":
            return statistics.stdev(self._wci_scores)
        elif metric == "churn_rate":
            return statistics.stdev(self._churn_rates)
        elif metric == "total_visits":
            return statistics.stdev(self._total_visits)
        elif metric == "total_revenue":
            return statistics.stdev([r.total_revenue for r in self.runs])
        elif metric == "active_agents":
            return statistics.stdev([r.active_agents for r in self.runs])
        elif metric == "visits":
            return statistics.stdev(self._visits)
        elif metric == "skips":
            return statistics.stdev(self._skips)
        elif metric == "churns":
            return statistics.stdev(self._churns)
        else:
            raise ValueError(f"Unknown metric: {metric}")
    
    def get_confidence_interval_95(self, metric: str = "wci") -> Optional[tuple[float, float]]:
        """
        Calculate 95% confidence interval for the mean.
        
        Uses t-distribution for small sample sizes.
        
        Args:
            metric: Which metric to calculate CI for
        
        Returns:
            Tuple of (lower_bound, upper_bound), or None if not enough data
        """
        if len(self.runs) < 2:
            return None
        
        import math
        
        mean = self.get_mean(metric)
        std_dev = self.get_std_dev(metric)
        
        if mean is None or std_dev is None:
            return None
        
        n = len(self.runs)
        
        # Use t-distribution critical value for 95% CI
        # For simplicity, use approximation: t ≈ 2 for small samples
        # (For exact values, would need scipy.stats.t.ppf)
        t_critical = 2.0 if n < 30 else 1.96
        
        margin_of_error = t_critical * (std_dev / math.sqrt(n))
        
        return (mean - margin_of_error, mean + margin_of_error)
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive summary of all runs and convergence status.
        
        Returns:
            Dictionary with statistics and convergence info
        """
        num_runs = len(self.runs)
        
        if num_runs == 0:
            return {
                "num_runs": 0,
                "converged": False,
                "stopped_reason": "no_runs"
            }
        
        # Calculate CVs for all metrics
        wci_cv = self.get_cv("wci")
        churn_cv = self.get_cv("churn_rate")
        visits_cv = self.get_cv("total_visits")
        
        # Check convergence based on primary metric
        primary_cv = self.get_cv(self.config.primary_metric)
        converged = (
            num_runs >= self.config.min_runs and 
            primary_cv is not None and 
            primary_cv <= self.config.cv_threshold
        )
        
        hit_max = num_runs >= self.config.max_runs
        
        if converged and not hit_max:
            stopped_reason = "converged"
        elif hit_max and not converged:
            stopped_reason = "max_runs_reached"
        elif hit_max and converged:
            stopped_reason = "converged_at_max"
        else:
            stopped_reason = "in_progress"
        
        # Calculate confidence intervals
        wci_ci = self.get_confidence_interval_95("wci")
        churn_ci = self.get_confidence_interval_95("churn_rate")
        visits_ci = self.get_confidence_interval_95("total_visits")
        
        return {
            "num_runs": num_runs,
            "converged": converged,
            "stopped_reason": stopped_reason,
            
            # Configuration
            "config": {
                "min_runs": self.config.min_runs,
                "max_runs": self.config.max_runs,
                "cv_threshold": self.config.cv_threshold,
                "primary_metric": self.config.primary_metric,
                "visit_weight": self.config.visit_weight,
                "skip_weight": self.config.skip_weight,
                "churn_weight": self.config.churn_weight,
            },
            
            # Weighted Composite Index (Primary Metric)
            "wci": {
                "mean": self.get_mean("wci"),
                "std_dev": self.get_std_dev("wci"),
                "cv": wci_cv,
                "confidence_interval_95": wci_ci,
                "values": self._wci_scores,
                "description": "Business health score: (visits × {:.1f}) + (skips × {:.1f}) + (churns × {:.1f})".format(
                    self.config.visit_weight, self.config.skip_weight, self.config.churn_weight
                )
            },
            
            # Behavioral Breakdown
            "visits": {
                "mean": self.get_mean("visits"),
                "std_dev": self.get_std_dev("visits"),
                "cv": self.get_cv("visits"),
                "values": self._visits
            },
            "skips": {
                "mean": self.get_mean("skips"),
                "std_dev": self.get_std_dev("skips"),
                "cv": self.get_cv("skips"),
                "values": self._skips
            },
            "churns": {
                "mean": self.get_mean("churns"),
                "std_dev": self.get_std_dev("churns"),
                "cv": self.get_cv("churns"),
                "values": self._churns
            },
            
            # Legacy Metrics (for compatibility)
            "churn_rate": {
                "mean": self.get_mean("churn_rate"),
                "std_dev": self.get_std_dev("churn_rate"),
                "cv": churn_cv,
                "confidence_interval_95": churn_ci,
                "values": self._churn_rates
            },
            "total_visits": {
                "mean": self.get_mean("total_visits"),
                "std_dev": self.get_std_dev("total_visits"),
                "cv": visits_cv,
                "confidence_interval_95": visits_ci,
                "values": self._total_visits
            },
            
            # Revenue Statistics
            "total_revenue": {
                "mean": self.get_mean("total_revenue"),
                "std_dev": self.get_std_dev("total_revenue"),
            },
            
            # All run results
            "runs": [
                {
                    "run_number": r.run_number,
                    "wci": self._calculate_wci(r.visits, r.skips, r.churns),
                    "visits": r.visits,
                    "skips": r.skips,
                    "churns": r.churns,
                    "churn_rate": r.churn_rate,
                    "total_visits": r.total_visits,
                    "total_revenue": r.total_revenue,
                    "active_agents": r.active_agents
                }
                for r in self.runs
            ]
        }
    
    def get_status_message(self) -> str:
        """
        Get human-readable status message for display.
        
        Returns:
            String describing current convergence status
        """
        num_runs = len(self.runs)
        
        if num_runs == 0:
            return "No runs completed yet"
        
        if num_runs < self.config.min_runs:
            return f"Run {num_runs}/{self.config.min_runs} (minimum required before checking convergence)"
        
        primary_cv = self.get_cv(self.config.primary_metric)
        
        if primary_cv is None:
            return f"Run {num_runs}/{self.config.max_runs} - Calculating statistics..."
        
        # Get metric name for display
        metric_display = {
            "wci": "Business Health Score",
            "churn_rate": "Churn Rate",
            "total_visits": "Total Visits"
        }.get(self.config.primary_metric, self.config.primary_metric)
        
        if primary_cv <= self.config.cv_threshold:
            return f"✓ Converged after {num_runs} runs ({metric_display} CV: {primary_cv:.2f}% ≤ {self.config.cv_threshold}%)"
        
        if num_runs >= self.config.max_runs:
            return f"⚠ Stopped at maximum {num_runs} runs ({metric_display} CV: {primary_cv:.2f}% > {self.config.cv_threshold}%)"
        
        return f"Run {num_runs}/{self.config.max_runs} - {metric_display} CV: {primary_cv:.2f}% (target: ≤{self.config.cv_threshold}%)"
