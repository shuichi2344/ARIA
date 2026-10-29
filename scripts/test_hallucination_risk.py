"""
Hallucination Risk Test — Reasoning Output Collector.

Generates 10 agent decisions and prints the full reasoning for each one.
The outputs are intended for MANUAL human review to identify unsupported claims.

A claim is considered a hallucination if it references information NOT present in:
  - The agent profile
  - The scenario description
  - The business context

Reviewers should check each reasoning for:
  - References to specific past dates/events not in the context
  - References to external news, articles, or sources not provided
  - Competitor details not mentioned in the scenario
  - Invented statistics or price comparisons beyond what was given
  - Any other fabricated information

Usage:
    python scripts/test_hallucination_risk.py
    python scripts/test_hallucination_risk.py --provider ollama
    python scripts/test_hallucination_risk.py --provider ilmu
"""

import asyncio
import sys
import os
import argparse
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

NUM_RUNS    = 10
INCOME      = "M40"
AGE_RANGE   = "30-39"

SCENARIO = {
    "scenario_name": "Price Increase +10%",
    "scenario_type": "price_change",
    "description": "The cafe has raised its prices by 10% across all menu items.",
    "parameters": {"price_change_percent": 10},
    "expected_impact": "Moderate negative reaction expected",
}

BUSINESS = {
    "name": "Chew Cafe",
    "business_name": "Chew Cafe",
    "business_type": "Cafe",
    "type": "Cafe",
    "location": "Georgetown, Penang",
    "district": "Timur Laut",
    "price_range_min": 5.0,
    "price_range_max": 20.0,
    "unique_selling_points": "Affordable local coffee and breakfast sets",
    "b2c_target_segments": ["working professionals", "students", "families"],
    "customer_type": "B2C",
}


async def main(provider: str):
    print("=" * 70)
    print("ARIA — Hallucination Risk Test (Manual Review Output)")
    print("=" * 70)
    print(f"Scenario  : Price Increase +10%")
    print(f"Business  : {BUSINESS['name']}, {BUSINESS['location']}")
    print(f"Agent     : {INCOME}, age {AGE_RANGE}")
    print(f"Provider  : {provider.upper()}")
    print(f"Runs      : {NUM_RUNS}")
    print()
    print("PROVIDED CONTEXT (ground truth for review):")
    print(f"  Profile fields  : income level, age range, customer type,")
    print(f"                    visit frequency, values, spending habit, loyalty")
    print(f"  Scenario fields : 10% price increase, cafe, all menu items")
    print(f"  Business fields : Chew Cafe, Georgetown Penang, RM5-20 price range,")
    print(f"                    affordable local coffee and breakfast sets")
    print()
    print("Any claim in the reasoning NOT traceable to the above is a hallucination.")
    print("=" * 70)

    if provider == "ollama":
        os.environ["ILMU_API_KEY"] = ""
        print("  → Ilmu AI disabled. Using Ollama.\n")
    elif provider == "ilmu":
        print("  → Using Ilmu AI as primary provider.\n")

    from aria.simulation.llm_agent_brain import LLMAgentBrain
    brain = LLMAgentBrain()

    # Generate a real system profile
    print("Generating LLM agent profile...")
    profile = await brain.generate_agent_profile(
        age_range=AGE_RANGE,
        income_level=INCOME,
        location=BUSINESS["location"],
        district=BUSINESS["district"],
        business_profile=BUSINESS,
        assigned_personality=None,
    )

    print(f"\nGENERATED PROFILE:")
    print("-" * 70)
    print(profile)
    print("-" * 70)
    print()

    # Run decisions
    print("Running decisions...\n")
    start_time = time.time()
    outputs = []

    for i in range(1, NUM_RUNS + 1):
        try:
            result = await brain.make_decision_and_message(
                agent_profile=profile,
                scenario_context=SCENARIO,
                business_context=BUSINESS,
                peer_messages=None,
                income_level=INCOME,
            )
            decision  = result.get("decision", "unknown")
            reasoning = result.get("message", "")
            outputs.append({"run": i, "decision": decision, "reasoning": reasoning})
            print(f"  Run {i:2d}: {decision.upper()}")
        except Exception as e:
            print(f"  Run {i:2d}: ERROR — {e}")
            outputs.append({"run": i, "decision": "error", "reasoning": str(e)})

    elapsed = time.time() - start_time

    # ── Full output for manual review ─────────────────────────────────────────
    print("\n" + "=" * 70)
    print("FULL REASONING OUTPUTS — REVIEW EACH ONE MANUALLY")
    print(f"Provider : {provider.upper()}")
    print(f"Time     : {elapsed:.1f}s")
    print("=" * 70)
    print()
    print("For each run, mark in your report:")
    print("  ✓ Clean     — all claims supported by the provided context")
    print("  ✗ Hallucin. — contains at least one unsupported fabricated claim")
    print()

    for o in outputs:
        print(f"{'─' * 70}")
        print(f"Run {o['run']:2d} | Decision: {o['decision'].upper()}")
        print(f"Reasoning:")
        print(f"  {o['reasoning']}")
        print()

    print("=" * 70)
    print("MANUAL REVIEW CHECKLIST")
    print("-" * 70)
    print("For each reasoning above, ask:")
    print("  1. Does it reference a specific past date or event?")
    print("     (e.g. 'last Tuesday', '2 weeks ago', 'when I visited last month')")
    print("  2. Does it cite a news article, report, or external source?")
    print("     (e.g. 'I read that...', 'according to news...')")
    print("  3. Does it mention competitor names or specific prices not in the scenario?")
    print("     (e.g. 'the kopitiam next door charges RM8')")
    print("  4. Does it mention a named person not in the profile?")
    print("  5. Does it reference a specific branch or outlet not in the context?")
    print()
    print("If YES to any of the above → mark as hallucination.")
    print("If NO to all → mark as clean.")
    print()
    print("Unsupported-claim rate = (flagged runs / total runs) × 100%")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hallucination Risk Test")
    parser.add_argument(
        "--provider",
        choices=["ilmu", "ollama", "auto"],
        default="auto",
        help="LLM provider: ilmu, ollama, or auto (uses .env config)"
    )
    args = parser.parse_args()
    asyncio.run(main(args.provider))
