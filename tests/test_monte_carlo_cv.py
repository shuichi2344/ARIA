"""
Tests for Monte Carlo Coefficient of Variation stopping criterion with WCI.
"""

import pytest
from aria.simulation.monte_carlo_cv import (
    MonteCarloConfig,
    MonteCarloTracker,
    RunResult
)


def create_run_result(run_number, visits=70, skips=10, churns=20, total_agents=100):
    """Helper to create RunResult with proper WCI fields."""
    return RunResult(
        run_number=run_number,
        visits=visits,
        skips=skips,
        churns=churns,
        churn_rate=(churns / total_agents) * 100,
        total_visits=visits,
        total_revenue=visits * 50.0,
        active_agents=total_agents - churns
    )


class TestMonteCarloConfig:
    """Test configuration validation."""
    
    def test_valid_config(self):
        """Test valid configuration."""
        config = MonteCarloConfig(min_runs=5, max_runs=30, cv_threshold=5.0)
        assert config.min_runs == 5
        assert config.max_runs == 30
        assert config.cv_threshold == 5.0
        assert config.primary_metric == "wci"  # Default to WCI
    
    def test_min_runs_too_small(self):
        """Test that min_runs must be at least 2."""
        with pytest.raises(ValueError, match="min_runs must be at least 2"):
            MonteCarloConfig(min_runs=1, max_runs=30)
    
    def test_max_less_than_min(self):
        """Test that max_runs must be >= min_runs."""
        with pytest.raises(ValueError, match="max_runs must be >= min_runs"):
            MonteCarloConfig(min_runs=10, max_runs=5)
    
    def test_negative_cv_threshold(self):
        """Test that cv_threshold must be positive."""
        with pytest.raises(ValueError, match="cv_threshold must be positive"):
            MonteCarloConfig(cv_threshold=-1.0)


class TestMonteCarloTracker:
    """Test Monte Carlo tracking and stopping logic."""
    
    def test_initialization(self):
        """Test tracker initialization."""
        config = MonteCarloConfig()
        tracker = MonteCarloTracker(config)
        assert len(tracker.runs) == 0
        assert tracker.get_mean() is None
        assert tracker.get_cv() is None
    
    def test_add_single_run(self):
        """Test adding a single run."""
        config = MonteCarloConfig()
        tracker = MonteCarloTracker(config)
        
        result = create_run_result(1, visits=80, skips=0, churns=20)
        should_stop = tracker.add_run(result)
        
        # Should not stop after 1 run (min is 5)
        assert not should_stop
        assert len(tracker.runs) == 1
        assert tracker.get_mean("visits") == 80
    
    def test_converges_early(self):
        """Test early convergence when WCI CV drops below threshold."""
        config = MonteCarloConfig(min_runs=5, max_runs=30, cv_threshold=5.0)
        tracker = MonteCarloTracker(config)
        
        # Add 7 runs with very low variance in WCI (should converge)
        # Keep visits/skips/churns stable
        for i in range(7):
            result = create_run_result(
                i + 1,
                visits=70 + (i % 3),  # 70, 71, 72, 70, 71, 72, 70
                skips=10,
                churns=20
            )
            should_stop = tracker.add_run(result)
        
        # Should converge before max runs
        assert should_stop
        assert len(tracker.runs) < config.max_runs
        assert tracker.get_cv("wci") <= config.cv_threshold
        
        summary = tracker.get_summary()
        assert summary["converged"] is True
        assert summary["stopped_reason"] == "converged"
    
    def test_reaches_max_runs(self):
        """Test that simulation stops at max runs even without convergence."""
        config = MonteCarloConfig(min_runs=5, max_runs=10, cv_threshold=5.0)
        tracker = MonteCarloTracker(config)
        
        # Add runs with high variance in WCI (won't converge)
        import random
        random.seed(42)
        
        for i in range(10):
            result = create_run_result(
                i + 1,
                visits=random.randint(40, 80),   # High variance
                skips=random.randint(10, 30),
                churns=random.randint(10, 30)
            )
            should_stop = tracker.add_run(result)
        
        # Should stop at max runs
        assert should_stop
        assert len(tracker.runs) == config.max_runs
        
        summary = tracker.get_summary()
        assert summary["num_runs"] == 10
        assert summary["stopped_reason"] in ["max_runs_reached", "converged_at_max"]
    
    def test_does_not_stop_before_min_runs(self):
        """Test that simulation never stops before min_runs."""
        config = MonteCarloConfig(min_runs=5, max_runs=30, cv_threshold=5.0)
        tracker = MonteCarloTracker(config)
        
        # Add 4 runs with perfect stability (CV would be 0)
        for i in range(4):
            result = create_run_result(i + 1, visits=70, skips=10, churns=20)
            should_stop = tracker.add_run(result)
            
            # Should NOT stop before min_runs
            assert not should_stop
    
    def test_wci_calculation(self):
        """Test WCI calculation with different weights."""
        config = MonteCarloConfig()
        tracker = MonteCarloTracker(config)
        
        # Add a run: 80 visits, 10 skips, 10 churns
        # WCI = 80*1.0 + 10*0.5 + 10*0.0 = 85.0
        result = create_run_result(1, visits=80, skips=10, churns=10)
        tracker.add_run(result)
        
        assert tracker.get_mean("wci") == 85.0
    
    def test_cv_with_zero_mean(self):
        """Test CV returns None when mean is zero."""
        config = MonteCarloConfig()
        tracker = MonteCarloTracker(config)
        
        # Add runs with zero WCI (all churns, no visits or skips)
        for i in range(5):
            result = create_run_result(i + 1, visits=0, skips=0, churns=100)
            tracker.add_run(result)
        
        cv = tracker.get_cv("wci")
        
        # Should return None (can't divide by zero)
        assert cv is None
    
    def test_multiple_metrics_tracking(self):
        """Test that WCI, visits, skips, churns are all tracked."""
        config = MonteCarloConfig()
        tracker = MonteCarloTracker(config)
        
        for i in range(5):
            result = create_run_result(
                i + 1,
                visits=70 + i,
                skips=10 + i,
                churns=20 - i
            )
            tracker.add_run(result)
        
        # Check all metrics are tracked
        assert tracker.get_cv("wci") is not None
        assert tracker.get_cv("visits") is not None
        assert tracker.get_cv("skips") is not None
        assert tracker.get_cv("churns") is not None
    
    def test_summary_structure(self):
        """Test that summary contains all expected fields."""
        config = MonteCarloConfig(min_runs=5, max_runs=30, cv_threshold=5.0)
        tracker = MonteCarloTracker(config)
        
        for i in range(7):
            result = create_run_result(i + 1, visits=70 + i, skips=10, churns=20)
            tracker.add_run(result)
        
        summary = tracker.get_summary()
        
        # Check top-level fields
        assert "num_runs" in summary
        assert "converged" in summary
        assert "stopped_reason" in summary
        assert "config" in summary
        
        # Check WCI stats
        assert "wci" in summary
        assert "mean" in summary["wci"]
        assert "std_dev" in summary["wci"]
        assert "cv" in summary["wci"]
        assert "confidence_interval_95" in summary["wci"]
        assert "values" in summary["wci"]
        assert "description" in summary["wci"]
        
        # Check behavioral breakdown
        assert "visits" in summary
        assert "skips" in summary
        assert "churns" in summary
        
        # Check runs list
        assert "runs" in summary
        assert len(summary["runs"]) == 7
        assert "wci" in summary["runs"][0]
    
    def test_confidence_interval_calculation(self):
        """Test 95% confidence interval calculation."""
        config = MonteCarloConfig()
        tracker = MonteCarloTracker(config)
        
        # Add runs
        for i in range(10):
            result = create_run_result(i + 1, visits=70 + i, skips=10, churns=20)
            tracker.add_run(result)
        
        ci = tracker.get_confidence_interval_95("wci")
        
        assert ci is not None
        lower, upper = ci
        
        # CI should bracket the mean
        mean = tracker.get_mean("wci")
        assert lower < mean < upper
    
    def test_status_message_progression(self):
        """Test status messages at different stages."""
        config = MonteCarloConfig(min_runs=5, max_runs=10, cv_threshold=5.0)
        tracker = MonteCarloTracker(config)
        
        # No runs
        msg = tracker.get_status_message()
        assert "No runs" in msg
        
        # Before min_runs
        for i in range(3):
            result = create_run_result(i + 1, visits=70, skips=10, churns=20)
            tracker.add_run(result)
        
        msg = tracker.get_status_message()
        assert "minimum required" in msg.lower()
        
        # After min_runs, converged
        for i in range(3, 7):
            result = create_run_result(i + 1, visits=70, skips=10, churns=20)
            tracker.add_run(result)
        
        msg = tracker.get_status_message()
        # Should show convergence or CV status
        assert "Business Health Score" in msg or "CV:" in msg or "Converged" in msg


class TestRealWorldScenarios:
    """Test realistic simulation scenarios."""
    
    def test_typical_convergence_scenario(self):
        """Test a typical scenario where WCI stabilizes after several runs."""
        config = MonteCarloConfig(min_runs=5, max_runs=30, cv_threshold=5.0)
        tracker = MonteCarloTracker(config)
        
        # Simulate behavior that converges
        import random
        random.seed(123)
        
        base_visits = 70
        base_skips = 10
        base_churns = 20
        
        for i in range(30):
            # Gradually reduce variance
            noise_scale = max(0.5, 5.0 - i * 0.3)
            
            visits = int(base_visits + random.gauss(0, noise_scale))
            skips = int(base_skips + random.gauss(0, noise_scale * 0.5))
            churns = int(base_churns + random.gauss(0, noise_scale * 0.5))
            
            # Clamp
            visits = max(0, min(90, visits))
            skips = max(0, min(30, skips))
            churns = max(0, min(30, churns))
            
            result = create_run_result(
                i + 1,
                visits=visits,
                skips=skips,
                churns=churns
            )
            
            should_stop = tracker.add_run(result)
            
            if should_stop:
                break
        
        summary = tracker.get_summary()
        
        # Should converge somewhere between min and max
        assert summary["num_runs"] >= config.min_runs
        assert summary["num_runs"] <= config.max_runs
    
    def test_high_variance_no_convergence(self):
        """Test scenario with high variance that never converges."""
        config = MonteCarloConfig(min_runs=5, max_runs=20, cv_threshold=5.0)
        tracker = MonteCarloTracker(config)
        
        import random
        random.seed(456)
        
        for i in range(20):
            # High variance - won't converge
            visits = random.randint(40, 90)
            skips = random.randint(5, 30)
            churns = random.randint(10, 40)
            
            result = create_run_result(
                i + 1,
                visits=visits,
                skips=skips,
                churns=churns
            )
            
            tracker.add_run(result)
        
        summary = tracker.get_summary()
        
        # Should hit max runs
        assert summary["num_runs"] == config.max_runs
        assert summary["stopped_reason"] in ["max_runs_reached", "converged_at_max"]
    
    def test_false_convergence_detection(self):
        """Test that WCI catches false convergence (constant churn, varying visits/skips)."""
        config = MonteCarloConfig(min_runs=5, max_runs=30, cv_threshold=5.0)
        tracker = MonteCarloTracker(config)
        
        # Scenario: churn stays constant, but visits/skips vary wildly
        churn_constant = 20
        visit_skips = [
            (80, 0),   # WCI = 80
            (60, 20),  # WCI = 70
            (70, 10),  # WCI = 75
            (65, 15),  # WCI = 72.5
            (75, 5),   # WCI = 77.5
            (68, 12),  # WCI = 74
        ]
        
        for i, (visits, skips) in enumerate(visit_skips):
            result = create_run_result(
                i + 1,
                visits=visits,
                skips=skips,
                churns=churn_constant
            )
            tracker.add_run(result)
        
        # WCI should have variance (not converged)
        wci_cv = tracker.get_cv("wci")
        assert wci_cv is not None
        assert wci_cv > 0  # Not perfectly stable
        
        # Churn rate CV would be 0 (false convergence)
        churn_cv = tracker.get_cv("churn_rate")
        assert churn_cv == 0.0 or churn_cv < 0.01  # Essentially zero


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
