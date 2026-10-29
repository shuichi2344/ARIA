"""
Response Consistency Test for LLM Agent Decision-Making.

Runs the same scenario 10 times with a fixed agent profile and records
the decision (visit, skip, churn) each time to measure consistency.

Usage:
    python scripts/test_response_consistency.py
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aria.simulation.llm_agent_brain import LLMAgentBrain


# ── Fixed agent profile (same every run) ──────────────────────────────────────
AGENT_PROFILE = """Customer type: price-conscious regular visitor
Income level: B40 (household income below RM4,850/month)
Age range: 30-39 years old
Visit frequency: 2-3 times per week
Values: affordability, value for money, familiar local taste
Spending habit: spends RM8-12 per visit, budgets carefully
Loyalty factor: loyal as long as price stays reasonable, will switch if cost increases significantly"""

# ── Fixed scenario (same every run) ───────────────────────────────────────────
SCENARIO = {
    "scenario_name": "Price Increase +10%",
    "scenario_type": "price_change",
    "description": "The cafe has raised its prices by 10% across all menu items.",
    "parameters": {"price_change_percent": 10},
    "expected_impact": "Moderate churn expected among price-sensitive customers",
}

# ── Fixed business context ─────────────────────────────────────────────────────
BUSINESS = {
    "business_name": "Chew Cafe",
    "business_type": "Cafe",
    "location": "Georgetown, Penang",
    "district": "Timur Laut",
    "price_range_min": 5.0,
    "price_range_max": 20.0,
}

NUM_RUNS = 10


async def run_once(brain: LLMAgentBrain, run_number: int) -> str:
    """Run a single agent decision and return the decision."""
    result = await brain.make_decision_and_message(
        agent_profile=AGENT_PROFILE,
        scenario_context=SCENARIO,
        business_context=BUSINESS,
        peer_messages=None,
        income_level="B40",
    )
    decision = result.get("decision", "unknown")
    reasoning = result.get("message", "")[:120]  # First 120 chars only
    print(f"  Run {run_number:2d}: {decision.upper():<6}  | {reasoning}...")
    return decision


async def main():
    print("=" * 70)
    print("ARIA — Response Consistency Test")
    print("=" * 70)
    print(f"Scenario : Price Increase +10%")
    print(f"Agent    : B40, 30-39, Georgetown, Cafe")
    print(f"Runs     : {NUM_RUNS}")
    print("-" * 70)

    brain = LLMAgentBrain()
    decisions = []

    for i in range(1, NUM_RUNS + 1):
        decision = await run_once(brain, i)
        decisions.append(decision)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("-" * 70)
    print("\nSUMMARY")
    print(f"  Decisions recorded: {decisions}")

    counts = {d: decisions.count(d) for d in set(decisions)}
    majority = max(counts, key=counts.get)
    majority_count = counts[majority]
    agreement_rate = (majority_count / NUM_RUNS) * 100

    print(f"\n  Decision counts:")
    for decision, count in sorted(counts.items()):
        print(f"    {decision:<6}: {count} / {NUM_RUNS}  ({count/NUM_RUNS*100:.0f}%)")

    print(f"\n  Majority decision : {majority.upper()} ({majority_count}/{NUM_RUNS} runs)")
    print(f"  Agreement rate    : {agreement_rate:.0f}%")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
