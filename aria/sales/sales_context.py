"""
Sales context builder for simulation grounding.

Fetches a business's recent sales records and produces a compact
natural-language summary that can be injected into agent decision prompts.
This anchors simulation behaviour to the business's real observed patterns
rather than demographic averages alone.
"""

from __future__ import annotations

import statistics
from typing import Optional

import aiohttp

from aria.database.supabase_client import SupabaseClient


async def build_sales_context(profile_id: str, lookback_days: int = 90) -> str:
    """
    Fetch recent sales records for a profile and return a short paragraph
    summarising the business's real revenue patterns.

    Returns an empty string if there are no records or if the fetch fails —
    the caller should treat an empty string as "no sales context available".

    Args:
        profile_id: Business profile UUID.
        lookback_days: How many days of history to include (default 90).

    Returns:
        A 2–4 sentence summary string, or "" if no data.
    """
    try:
        from datetime import date, timedelta

        supabase = SupabaseClient()
        date_from = (date.today() - timedelta(days=lookback_days)).isoformat()

        url = f"{supabase.base_url}/rest/v1/sales_records"
        params = {
            "profile_id": f"eq.{profile_id}",
            "sale_date": f"gte.{date_from}",
            "select": "sale_date,total_sales,transaction_count",
            "order": "sale_date.asc",
            "limit": "200",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=supabase.headers) as resp:
                if resp.status != 200:
                    return ""
                records = await resp.json()

        if not records:
            return ""

        # ── Compute summary statistics ────────────────────────────────────
        daily_sales = [r["total_sales"] for r in records if r.get("total_sales") is not None]
        num_days = len(daily_sales)

        if num_days < 3:
            # Too few data points — not useful context
            return ""

        avg_daily = statistics.mean(daily_sales)
        max_daily = max(daily_sales)
        min_daily = min(daily_sales)
        total = sum(daily_sales)

        # Week-over-week trend: compare first half vs second half
        mid = num_days // 2
        first_half_avg = statistics.mean(daily_sales[:mid]) if mid > 0 else avg_daily
        second_half_avg = statistics.mean(daily_sales[mid:]) if mid < num_days else avg_daily
        trend_pct = ((second_half_avg - first_half_avg) / first_half_avg * 100) if first_half_avg > 0 else 0

        if trend_pct > 5:
            trend_desc = f"Sales have been trending upward ({trend_pct:.0f}% increase over the period)."
        elif trend_pct < -5:
            trend_desc = f"Sales have been trending downward ({abs(trend_pct):.0f}% decline over the period)."
        else:
            trend_desc = "Sales have been relatively stable over this period."

        # Transaction count context if available
        tx_records = [r["transaction_count"] for r in records if r.get("transaction_count")]
        tx_context = ""
        if tx_records:
            avg_tx = statistics.mean(tx_records)
            tx_context = f" The business averages approximately {avg_tx:.0f} transactions per day."

        # Build the context paragraph
        summary = (
            f"## Historical Sales Context (last {lookback_days} days)\n"
            f"This business recorded sales data across {num_days} days. "
            f"Average daily revenue: RM{avg_daily:.0f} "
            f"(range: RM{min_daily:.0f}–RM{max_daily:.0f}, total: RM{total:.0f})."
            f"{tx_context} "
            f"{trend_desc} "
            f"Use this real sales history to calibrate how sensitive this business's customers "
            f"are to changes — a business with declining sales likely has customers who are "
            f"already on the edge of churning."
        )

        return summary.strip()

    except Exception:
        # Never let sales context fetch break the simulation
        return ""
