# Monte Carlo Coefficient of Variation (CV) Stopping Criterion

## Overview

ARIA uses **dynamic Monte Carlo simulation** with a **Weighted Composite Index (WCI)** to determine when simulation results have statistically converged. This approach saves LLM API costs and computation time by stopping as soon as results stabilize, rather than running a fixed number of iterations.

## The Problem

LLM-based agent simulations have natural randomness. A single run might produce an outlier result. To get reliable predictions, we need multiple runs—but how many?

**Fixed Iteration Approach (Bad):**
```python
# Always run exactly 20 times
for i in range(20):
    run_simulation()
```

**Problems:**
- If results stabilize after 8 runs, you waste 12 expensive LLM calls
- If results haven't stabilized by run 20, you stop too early
- No statistical rigor

## The Solution: Weighted Composite Index (WCI)

Instead of tracking single metrics in isolation, WCI combines all agent decisions into a **single business health score**.

### Formula

```
WCI = (visits × 1.0) + (skips × 0.5) + (churns × 0.0)
```

### Weights Explained

| Decision | Weight | Economic Rationale |
|----------|--------|-------------------|
| **Visit** | 1.0 | Full value: customer came, spent money, generated revenue |
| **Skip** | 0.5 | Half value: customer retained but no revenue this week (still has lifetime value) |
| **Churn** | 0.0 | Zero value: customer lost permanently (worst outcome) |

### Why WCI Beats Individual Metrics

**Example: The False Convergence Problem**

```
Run 1: 80 visits, 0 skips, 20 churns  → Churn Rate: 20%
Run 2: 60 visits, 20 skips, 20 churns → Churn Rate: 20%
Run 3: 70 visits, 10 skips, 20 churns → Churn Rate: 20%

❌ Churn Rate CV = 0% (perfectly stable!)
```

**But look at WCI:**

```
Run 1: WCI = (80 × 1.0) + (0 × 0.5) + (20 × 0.0) = 80.0
Run 2: WCI = (60 × 1.0) + (20 × 0.5) + (20 × 0.0) = 70.0
Run 3: WCI = (70 × 1.0) + (10 × 0.5) + (20 × 0.0) = 75.0

✓ WCI CV = 6.5% (unstable!)
```

WCI correctly identifies that even though churn stayed constant, the **business outcome** is volatile.

## Coefficient of Variation (CV)

CV measures relative variability:

```
CV = (standard_deviation / mean) × 100
```

**CV < 5%** means results are **statistically stable** with less than 5% relative variation.

## Stopping Rules

```python
Stop simulation when:
  1. Runs ≥ 5 (minimum for statistical validity)
  2. WCI CV ≤ 5% (business health stabilized)
  3. Runs ≤ 30 (hard cap to prevent runaway costs)
```

## Usage

### Basic Usage

```python
from aria.simulation.monte_carlo_cv import MonteCarloConfig, MonteCarloTracker, RunResult

# Configure stopping criterion
config = MonteCarloConfig(
    min_runs=5,
    max_runs=30,
    cv_threshold=5.0,
    primary_metric="wci"
)

tracker = MonteCarloTracker(config)

# Run simulations until convergence
for run_num in range(config.max_runs):
    # Run your simulation...
    visits, skips, churns = run_simulation()
    
    result = RunResult(
        run_number=run_num + 1,
        visits=visits,
        skips=skips,
        churns=churns,
        churn_rate=churns / total_agents * 100,
        total_visits=visits,
        total_revenue=calculate_revenue(),
        active_agents=total_agents - churns
    )
    
    should_stop = tracker.add_run(result)
    
    print(tracker.get_status_message())
    
    if should_stop:
        break

# Get final results
summary = tracker.get_summary()
print(f"Converged after {summary['num_runs']} runs")
print(f"Average WCI: {summary['wci']['mean']:.1f} ± {summary['wci']['std_dev']:.1f}")
print(f"CV: {summary['wci']['cv']:.2f}%")
```

### Custom Weights (Advanced)

Different business models may want different weights:

**High-LTV Subscription Business:**
```python
config = MonteCarloConfig(
    min_runs=5,
    max_runs=30,
    cv_threshold=5.0,
    visit_weight=1.0,
    skip_weight=0.8,  # Skips are almost as valuable (retained subscribers)
    churn_weight=0.0
)
```

**Low-Margin Retail:**
```python
config = MonteCarloConfig(
    min_runs=5,
    max_runs=30,
    cv_threshold=5.0,
    visit_weight=1.0,
    skip_weight=0.2,  # Skips are concerning (need constant visits)
    churn_weight=0.0
)
```

**B2B with High Acquisition Costs:**
```python
config = MonteCarloConfig(
    min_runs=5,
    max_runs=30,
    cv_threshold=5.0,
    visit_weight=1.0,
    skip_weight=0.9,   # Retention is critical
    churn_weight=-2.0  # Churn is doubly negative (lost investment)
)
```

## Output Summary

After convergence, `tracker.get_summary()` returns:

```json
{
  "num_runs": 12,
  "converged": true,
  "stopped_reason": "converged",
  
  "wci": {
    "mean": 78.5,
    "std_dev": 3.2,
    "cv": 4.08,
    "confidence_interval_95": [76.4, 80.6],
    "values": [80.0, 75.0, 78.0, ...],
    "description": "Business health score: (visits × 1.0) + (skips × 0.5) + (churns × 0.0)"
  },
  
  "visits": {
    "mean": 68.3,
    "cv": 5.2,
    "values": [70, 65, 68, ...]
  },
  
  "skips": {
    "mean": 20.4,
    "cv": 12.3,
    "values": [18, 22, 20, ...]
  },
  
  "churns": {
    "mean": 11.3,
    "cv": 8.1,
    "values": [12, 10, 11, ...]
  }
}
```

## Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_runs` | 5 | Minimum runs before checking convergence |
| `max_runs` | 30 | Maximum runs to prevent runaway costs |
| `cv_threshold` | 5.0 | Stop when CV ≤ this % |
| `visit_weight` | 1.0 | Weight for visit decisions |
| `skip_weight` | 0.5 | Weight for skip decisions |
| `churn_weight` | 0.0 | Weight for churn decisions |
| `primary_metric` | "wci" | Metric to track ("wci", "churn_rate", or "total_visits") |

## Best Practices

### 1. Always Use WCI as Primary Metric
```python
primary_metric="wci"  # ✓ Captures full business health
```

### 2. Set Realistic Min/Max Bounds
```python
min_runs=5   # At least 5 for statistical validity
max_runs=30  # Cap at 30 to control costs
```

### 3. Use 5% CV Threshold
```python
cv_threshold=5.0  # Industry standard for convergence
```

### 4. Tune Weights for Your Business Model
- **Subscription**: Higher skip weight (0.7-0.9)
- **Retail**: Lower skip weight (0.2-0.4)
- **B2B**: Consider negative churn weight (-1.0 to -3.0)

## Statistical Rigor

### Why 5 Minimum Runs?
- CV calculation requires at least 2 runs
- 5 runs provides reasonable statistical power
- Below 5, confidence intervals are too wide

### Why 5% CV Threshold?
- Standard in Monte Carlo literature
- Balances accuracy vs. computational cost
- Translates to ±5% relative uncertainty

### Confidence Intervals
95% confidence intervals use t-distribution for small samples:
```
CI = mean ± t_critical × (std_dev / √n)
```

## Comparison to Alternatives

| Approach | Pros | Cons | ARIA Uses? |
|----------|------|------|------------|
| **Fixed iterations** | Simple | Wastes money or stops too early | ❌ No |
| **Single metric CV** | Fast | Misses false convergence | ❌ No |
| **Dual metric AND** | Comprehensive | Can run forever if metrics diverge | ❌ No |
| **Weighted Composite Index** | Single target, economically meaningful | Requires weight tuning | ✓ **Yes** |
| **Bayesian credible intervals** | More sophisticated | Overkill for business use | ❌ No |

## Cost Savings Example

**Scenario: Price increase simulation**

Fixed 20 runs:
- 20 runs × 25 agents × $0.002/call = **$1.00**

Dynamic CV stopping (converges at run 11):
- 11 runs × 25 agents × $0.002/call = **$0.55**
- **45% cost savings**

Over 100 simulations per day:
- Fixed: $100/day
- Dynamic: $55/day
- **Saves $16,425/year**

## References

- Coefficient of Variation: [Wikipedia](https://en.wikipedia.org/wiki/Coefficient_of_variation)
- Monte Carlo Methods: Metropolis & Ulam (1949)
- Composite Indices in Economics: OECD Handbook (2008)

## Support

For questions or custom weight recommendations, contact the ARIA team.
