"""
Demo: Monte Carlo CV Stopping Criterion with Weighted Composite Index

This example demonstrates how ARIA's Monte Carlo CV tracker automatically
stops simulations when results converge, saving LLM API costs.
"""

import random
from aria.simulation.monte_carlo_cv import MonteCarloConfig, MonteCarloTracker, RunResult


def simulate_scenario(scenario_type: str, run_number: int, total_agents: int = 100):
    """
    Simulate agent behavior with controlled variance.
    
    Args:
        scenario_type: "stable", "unstable", or "gradual_convergence"
        run_number: Current run number (affects variance)
        total_agents: Total number of agents
    
    Returns:
        Tuple of (visits, skips, churns)
    """
    if scenario_type == "stable":
        # Low variance from the start
        visits = random.randint(68, 72)
        churns = random.randint(18, 22)
        skips = total_agents - visits - churns
        
    elif scenario_type == "unstable":
        # High variance throughout
        visits = random.randint(50, 90)
        churns = random.randint(10, 40)
        skips = max(0, total_agents - visits - churns)
        
    elif scenario_type == "gradual_convergence":
        # Variance decreases as more runs complete
        base_visits = 70
        base_churns = 20
        
        # Variance reduces with each run
        variance_scale = max(1, 15 - run_number)
        
        visits = int(random.gauss(base_visits, variance_scale))
        churns = int(random.gauss(base_churns, variance_scale * 0.5))
        
        # Clamp to valid ranges
        visits = max(0, min(total_agents, visits))
        churns = max(0, min(total_agents - visits, churns))
        skips = total_agents - visits - churns
    
    else:
        raise ValueError(f"Unknown scenario: {scenario_type}")
    
    return visits, skips, churns


def run_demo(scenario_type: str, config: MonteCarloConfig):
    """
    Run a full Monte Carlo simulation demo.
    
    Args:
        scenario_type: Type of scenario to simulate
        config: Monte Carlo configuration
    """
    print("\n" + "="*80)
    print(f"SCENARIO: {scenario_type.upper()}")
    print("="*80)
    print(f"Config: min={config.min_runs}, max={config.max_runs}, CV≤{config.cv_threshold}%")
    print(f"Weights: Visit={config.visit_weight}, Skip={config.skip_weight}, Churn={config.churn_weight}")
    print("-"*80)
    
    tracker = MonteCarloTracker(config)
    total_agents = 100
    
    for run_num in range(config.max_runs):
        # Simulate agent behavior
        visits, skips, churns = simulate_scenario(scenario_type, run_num + 1, total_agents)
        
        # Create result
        result = RunResult(
            run_number=run_num + 1,
            visits=visits,
            skips=skips,
            churns=churns,
            churn_rate=(churns / total_agents) * 100,
            total_visits=visits,
            total_revenue=visits * 50.0,  # Assume RM50 per visit
            active_agents=total_agents - churns
        )
        
        # Add to tracker
        should_stop = tracker.add_run(result)
        
        # Calculate WCI for display
        wci = visits * config.visit_weight + skips * config.skip_weight + churns * config.churn_weight
        
        # Show progress
        status = tracker.get_status_message()
        print(f"Run {run_num + 1:2d}: V={visits:2d} S={skips:2d} C={churns:2d} → WCI={wci:5.1f} | {status}")
        
        if should_stop:
            break
    
    # Print summary
    print("-"*80)
    summary = tracker.get_summary()
    
    print(f"\n✓ STOPPED: {summary['stopped_reason'].upper()}")
    print(f"  Total Runs: {summary['num_runs']}")
    print(f"\n  Weighted Composite Index (WCI):")
    print(f"    Mean: {summary['wci']['mean']:.2f}")
    print(f"    Std Dev: {summary['wci']['std_dev']:.2f}")
    print(f"    CV: {summary['wci']['cv']:.2f}%")
    print(f"    95% CI: [{summary['wci']['confidence_interval_95'][0]:.2f}, {summary['wci']['confidence_interval_95'][1]:.2f}]")
    
    print(f"\n  Behavioral Breakdown:")
    print(f"    Avg Visits: {summary['visits']['mean']:.1f} ± {summary['visits']['std_dev']:.1f} (CV: {summary['visits']['cv']:.1f}%)")
    print(f"    Avg Skips:  {summary['skips']['mean']:.1f} ± {summary['skips']['std_dev']:.1f} (CV: {summary['skips']['cv']:.1f}%)")
    print(f"    Avg Churns: {summary['churns']['mean']:.1f} ± {summary['churns']['std_dev']:.1f} (CV: {summary['churns']['cv']:.1f}%)")
    
    # Cost analysis
    cost_per_call = 0.002
    total_cost = summary['num_runs'] * 100 * cost_per_call
    fixed_cost = 20 * 100 * cost_per_call
    savings = ((fixed_cost - total_cost) / fixed_cost) * 100
    
    print(f"\n  Cost Analysis:")
    print(f"    Dynamic CV: ${total_cost:.2f} ({summary['num_runs']} runs)")
    print(f"    Fixed 20:   ${fixed_cost:.2f} (20 runs)")
    print(f"    Savings:    ${fixed_cost - total_cost:.2f} ({savings:.0f}%)")
    
    print("="*80)


def demo_false_convergence():
    """
    Demonstrate the false convergence problem that WCI solves.
    """
    print("\n" + "="*80)
    print("DEMO: False Convergence Problem")
    print("="*80)
    print("Showing why tracking churn rate alone is insufficient...")
    print("-"*80)
    
    # Manually create runs with constant churn but varying visits/skips
    runs = [
        (80, 0, 20),   # 80 visits, 0 skips, 20 churns
        (60, 20, 20),  # 60 visits, 20 skips, 20 churns
        (70, 10, 20),  # 70 visits, 10 skips, 20 churns
        (65, 15, 20),  # 65 visits, 15 skips, 20 churns
        (75, 5, 20),   # 75 visits, 5 skips, 20 churns
    ]
    
    print("\nManual Run Data (Churn Rate = 20% every time):")
    print("Run  Visits  Skips  Churns  Churn%  WCI")
    print("-"*50)
    
    wci_scores = []
    for i, (v, s, c) in enumerate(runs, 1):
        wci = v * 1.0 + s * 0.5 + c * 0.0
        churn_pct = (c / 100) * 100
        wci_scores.append(wci)
        print(f"{i:2d}   {v:3d}     {s:2d}     {c:2d}      {churn_pct:.0f}%   {wci:.1f}")
    
    # Calculate CVs
    import statistics
    
    churn_cv = 0.0  # All churn rates are identical (20%)
    wci_mean = statistics.mean(wci_scores)
    wci_std = statistics.stdev(wci_scores)
    wci_cv = (wci_std / wci_mean) * 100
    
    print("-"*50)
    print(f"\nChurn Rate CV: {churn_cv:.2f}% ✓ (Falsely appears stable!)")
    print(f"WCI CV:        {wci_cv:.2f}% ✗ (Correctly shows instability)")
    
    print("\nConclusion:")
    print("  Even though churn stayed at 20%, the business outcome varied")
    print("  significantly (WCI ranged from 70 to 80). WCI correctly identifies")
    print("  that the simulation has NOT converged.")
    print("="*80)


if __name__ == "__main__":
    # Set random seed for reproducibility
    random.seed(42)
    
    # Standard configuration
    standard_config = MonteCarloConfig(
        min_runs=5,
        max_runs=30,
        cv_threshold=5.0,
        visit_weight=1.0,
        skip_weight=0.5,
        churn_weight=0.0,
        primary_metric="wci"
    )
    
    print("\n" + "╔" + "═"*78 + "╗")
    print("║" + " "*15 + "ARIA Monte Carlo CV Demo: Weighted Composite Index" + " "*12 + "║")
    print("╚" + "═"*78 + "╝")
    
    # Demo 1: False convergence problem
    demo_false_convergence()
    
    input("\nPress Enter to continue to next demo...")
    
    # Demo 2: Stable scenario (converges quickly)
    run_demo("stable", standard_config)
    
    input("\nPress Enter to continue to next demo...")
    
    # Demo 3: Gradual convergence
    run_demo("gradual_convergence", standard_config)
    
    input("\nPress Enter to continue to next demo...")
    
    # Demo 4: Unstable scenario (hits max runs)
    run_demo("unstable", standard_config)
    
    input("\nPress Enter to continue to next demo...")
    
    # Demo 5: Custom weights for subscription business
    print("\n" + "="*80)
    print("DEMO: Custom Weights for Subscription Business")
    print("="*80)
    print("In a subscription model, skips are almost as valuable as visits")
    print("because retained customers have high lifetime value.")
    print("="*80)
    
    subscription_config = MonteCarloConfig(
        min_runs=5,
        max_runs=30,
        cv_threshold=5.0,
        visit_weight=1.0,
        skip_weight=0.8,  # Higher weight for retention
        churn_weight=0.0,
        primary_metric="wci"
    )
    
    run_demo("gradual_convergence", subscription_config)
    
    print("\n✓ Demo complete! Check docs/MONTE_CARLO_CV.md for more details.")
