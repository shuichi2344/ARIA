"""
Profile Sensitivity Test for LLM Agent Decision-Making.

Mirrors the actual system flow:
  1. Generate a real LLM agent profile for each income group (same as production)
  2. Run 10 decisions per group using that generated profile
  3. Compare churn/skip/visit rates across B40, M40, T20

Usage:
    python scripts/test_profile_sensitivity.py
    python scripts/test_profile_sensitivity.py --provider ollama
    python scripts/test_profile_sensitivity.py --provider ilmu
"""

import asyncio
import sys
import os
import argparse
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Fixed scenario (identical for all income groups) ──────────────────────────
SCENARIO = {
    "scenario_name": "Price Increase +30%",
    "scenario_type": "price_change",
    "description": "The cafe has raised its prices by 30% across all menu items.",
    "parameters": {"price_change_percent": 30},
    "expected_impact": "High negative reaction expected among price-sensitive customers",
}

# ── Fixed business context (same as a real Chew Cafe simulation) ──────────────
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

# ── Agent demographics per income group (fixed, representative) ───────────────
AGENT_DEMOGRAPHICS = {
    "B40": {"income_level": "B40", "age_range": "30-39"},
    "M40": {"income_level": "M40", "age_range": "30-39"},
    "T20": {"income_level": "T20", "age_range": "30-39"},
}

AGENTS_PER_GROUP = 10


async def generate_profile(brain, income_level: str) -> str:
    """Generate a real LLM profile using the same function the system uses."""
    demo = AGENT_DEMOGRAPHICS[income_level]
    print(f"\n  [{income_level}] Generating LLM profile...")
    profile = await brain.generate_agent_profile(
        age_range=demo["age_range"],
        income_level=demo["income_level"],
        location=BUSINESS["location"],
        district=BUSINESS["district"],
        business_profile=BUSINESS,
        assigned_personality=None,
    )
    # Print a preview
    preview = profile[:150].replace("\n", " ")
    print(f"  [{income_level}] Profile: {preview}...")
    return profile


async def run_decisions(brain, income_level: str, profile: str) -> dict:
    """Run AGENTS_PER_GROUP decisions using the generated profile."""
    decisions = []
    print(f"\n  [{income_level}] Running {AGENTS_PER_GROUP} decisions...")

    for i in range(1, AGENTS_PER_GROUP + 1):
        try:
            result = await brain.make_decision_and_message(
                agent_profile=profile,
                scenario_context=SCENARIO,
                business_context=BUSINESS,
                peer_messages=None,
                income_level=income_level,
            )
            decision = result.get("decision", "unknown")
            reasoning = result.get("message", "")[:100]
            decisions.append(decision)
            status = "✓" if decision in ("visit", "skip", "churn") else "?"
            print(f"    {status} Run {i:2d}: {decision.upper():<6}  {reasoning}...")
        except Exception as e:
            print(f"    ✗ Run {i:2d}: ERROR — {e}")
            decisions.append("error")

    total = len([d for d in decisions if d != "error"])
    visit_count = decisions.count("visit")
    skip_count  = decisions.count("skip")
    churn_count = decisions.count("churn")

    visit_pct = (visit_count / total * 100) if total > 0 else 0
    skip_pct  = (skip_count  / total * 100) if total > 0 else 0
    churn_pct = (churn_count / total * 100) if total > 0 else 0

    return {
        "income_level": income_level,
        "total_runs":   total,
        "visit":        visit_count,
        "skip":         skip_count,
        "churn":        churn_count,
        "visit_pct":    visit_pct,
        "skip_pct":     skip_pct,
        "churn_pct":    churn_pct,
        "decisions":    decisions,
    }


async def main(provider: str):
    print("=" * 70)
    print("ARIA — Profile Sensitivity Test (System-Generated Profiles)")
    print("=" * 70)
    print(f"Scenario : Price Increase +30%")
    print(f"Business : Chew Cafe, Georgetown")
    print(f"Groups   : B40, M40, T20  ({AGENTS_PER_GROUP} agents each)")
    print(f"Provider : {provider.upper()}")
    print(f"Method   : LLM-generated profiles (mirrors production system)")
    print(f"Metric   : Non-visit rate (skip + churn) as sensitivity measure")
    print("=" * 70)

    # ── Force provider ─────────────────────────────────────────────────────────
    if provider == "ollama":
        os.environ["ILMU_API_KEY"] = ""
        print("  → Ilmu AI disabled. Using Ollama as sole provider.\n")
    elif provider == "ilmu":
        print("  → Using Ilmu AI as primary provider.\n")

    from aria.simulation.llm_agent_brain import LLMAgentBrain
    brain = LLMAgentBrain()

    start_time = time.time()
    results = []

    print("PHASE 1: Generating LLM Profiles")
    print("-" * 70)

    profiles = {}
    for income_level in ["B40", "M40", "T20"]:
        profiles[income_level] = await generate_profile(brain, income_level)

    print("\n\nPHASE 2: Running Decisions")
    print("-" * 70)

    for income_level in ["B40", "M40", "T20"]:
        result = await run_decisions(brain, income_level, profiles[income_level])
        results.append(result)

    elapsed = time.time() - start_time

    # ── Summary table ──────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("PROFILE SENSITIVITY RESULTS")
    print(f"Scenario : Price Increase +30%")
    print(f"Provider : {provider.upper()}")
    print("-" * 70)
    print(f"{'Income':<8} {'Visit':>8} {'Skip':>8} {'Churn':>8} {'Non-Visit':>12}")
    print("-" * 70)

    for r in results:
        non_visit_pct = r["skip_pct"] + r["churn_pct"]
        print(
            f"{r['income_level']:<8} "
            f"{r['visit_pct']:>6.0f}%  "
            f"{r['skip_pct']:>6.0f}%  "
            f"{r['churn_pct']:>6.0f}%  "
            f"{non_visit_pct:>10.0f}%"
        )

    print("-" * 70)

    print("\nDECISION BREAKDOWN")
    print("-" * 70)
    for r in results:
        print(f"  {r['income_level']}: {', '.join(r['decisions'])}")

    print(f"\nTotal time: {elapsed:.1f}s  (~{elapsed/3:.1f}s per group)")

    # ── Sensitivity check ──────────────────────────────────────────────────────
    print("\nSENSITIVITY CHECK")
    print("-" * 70)
    b40 = next(r for r in results if r["income_level"] == "B40")
    m40 = next(r for r in results if r["income_level"] == "M40")
    t20 = next(r for r in results if r["income_level"] == "T20")

    # Non-visit rate = skip + churn (any negative reaction to price change)
    b40_nonvisit = b40["skip_pct"] + b40["churn_pct"]
    m40_nonvisit = m40["skip_pct"] + m40["churn_pct"]
    t20_nonvisit = t20["skip_pct"] + t20["churn_pct"]
    nonvisit_diff = b40_nonvisit - t20_nonvisit

    b40_visit = b40["visit_pct"]
    t20_visit = t20["visit_pct"]
    visit_diff = t20_visit - b40_visit

    print(f"  B40 non-visit rate (skip+churn) : {b40_nonvisit:.0f}%")
    print(f"  M40 non-visit rate (skip+churn) : {m40_nonvisit:.0f}%")
    print(f"  T20 non-visit rate (skip+churn) : {t20_nonvisit:.0f}%")
    print(f"  B40 visit rate                  : {b40_visit:.0f}%")
    print(f"  T20 visit rate                  : {t20_visit:.0f}%")
    print()
    print(f"  Non-visit spread (B40 vs T20)   : {nonvisit_diff:+.0f} pp")
    print(f"  Visit spread (T20 vs B40)        : {visit_diff:+.0f} pp")

    # Check for monotonic gradient (B40 >= M40 >= T20 for non-visit)
    monotonic = b40_nonvisit >= m40_nonvisit >= t20_nonvisit

    if nonvisit_diff > 10:
        verdict = "✓ PASS"
        note = "B40 reacts significantly more negatively than T20 — income sensitivity confirmed"
    elif nonvisit_diff > 0:
        verdict = "~ PARTIAL"
        note = "Some sensitivity detected but difference is small (< 10 pp)"
    else:
        verdict = "✗ FAIL"
        note = "No meaningful sensitivity between income groups"

    gradient = "✓ Monotonic gradient (B40 ≥ M40 ≥ T20 non-visit)" if monotonic else "✗ No clear gradient across income groups"

    print(f"\n  {verdict} — {note}")
    print(f"  {gradient}")
    print("=" * 70)

    # ── Print generated profiles for report inclusion ──────────────────────────
    print("\nGENERATED PROFILES (for report reference)")
    print("-" * 70)
    for income_level in ["B40", "M40", "T20"]:
        print(f"\n[{income_level}]\n{profiles[income_level]}")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Profile Sensitivity Test")
    parser.add_argument(
        "--provider",
        choices=["ilmu", "ollama", "auto"],
        default="auto",
        help="LLM provider: ilmu, ollama, or auto (uses .env config)"
    )
    args = parser.parse_args()
    asyncio.run(main(args.provider))
