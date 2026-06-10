"""
Prompt templates for ARIA LLM use cases.
All templates include Malaysian cultural context.
"""

from typing import Dict, Any, List, Optional


def business_profile_synthesis(
    questionnaire_data: Optional[Dict[str, Any]],
    manual_data: Optional[Dict[str, Any]]
) -> str:
    """Generate prompt for synthesizing business profile from multiple sources."""
    prompt = """You are a business analyst helping Malaysian micro-business owners understand their business profile.

Your task is to synthesize business information from multiple sources into a coherent profile.

Data Sources:
"""
    if questionnaire_data:
        prompt += f"\nQuestionnaire Data:\n{_format_dict(questionnaire_data)}\n"
    if manual_data:
        prompt += f"\nManual Entry Data:\n{_format_dict(manual_data)}\n"

    prompt += """
Instructions:
1. Merge the data, prioritizing: Manual Entry > Questionnaire
2. Resolve any conflicts by choosing the most specific/recent information
3. Infer missing fields based on available data and Malaysian business context
4. Return a JSON object with these fields:
   - business_name
   - business_type
   - location
   - district
   - price_level (1-4)
   - target_audience
   - unique_selling_points
   - operating_hours

Respond ONLY with valid JSON, no additional text."""
    return prompt


def scenario_suggestion(
    business_profile: Dict[str, Any],
    user_question: str
) -> str:
    """Generate prompt for suggesting scenarios based on user question."""
    prompt = f"""You are a business strategy advisor for Malaysian micro-businesses.

Business Profile:
{_format_dict(business_profile)}

User Question: "{user_question}"

Your task is to:
1. Analyze the user's question to understand their concern or goal
2. Suggest 3-5 relevant "what-if" scenarios to simulate
3. Rank scenarios by relevance to the question

For each scenario, provide:
- scenario_name: Short descriptive name
- scenario_type: A concise snake_case label describing the scenario (e.g. price_change, branch_expansion, loyalty_program, staff_reduction). Invent the right type for the situation — do not limit yourself to a fixed list.
- description: Clear explanation of the scenario from the customer's perspective — what changes and how customers experience it
- parameters: Specific values to simulate (e.g., {"price_change_percent": -10}). Include "price_change_percent" if prices change, otherwise use descriptive keys relevant to the scenario.
- relevance_score: 0-100 (how relevant to user's question)
- expected_impact: Brief prediction of potential impact

Return a JSON object with:
- analysis: Your understanding of the user's question
- recommended_action: Brief advice on what action to take
- scenarios: Array of scenario objects sorted by relevance_score (highest first)

Respond ONLY with valid JSON."""
    return prompt


def scenario_suggestion_with_context(
    business_profile: Dict[str, Any],
    user_question: str,
    news_articles: List[Dict[str, Any]],
    economic_indicators: Dict[str, Any],
    holiday_context: str = "",
    spark_section: str = ""
) -> str:
    """
    Generate prompt for suggesting scenarios with real-world context.
    Enhanced with News API, DOSM economic data, and Malaysia holiday calendar.
    """
    prompt = f"""You are a business strategy advisor for Malaysian micro-businesses with access to real-time economic data and news.

Business Profile:
{_format_dict(business_profile)}

User Question: "{user_question}"

Real-World Context:
"""
    if news_articles:
        prompt += "\nRecent News:\n"
        for i, article in enumerate(news_articles[:3], 1):
            prompt += f"{i}. {article['title']}\n"
            if article.get('description'):
                prompt += f"   {article['description']}\n"
            prompt += f"   Source: {article['source']} | Published: {article['published_at']}\n"

    if economic_indicators:
        prompt += "\nEconomic Indicators:\n"
        district = economic_indicators.get('district', '')
        if district:
            prompt += f"District: {district}\n"
        income_dist = economic_indicators.get('income_distribution', {})
        if income_dist:
            prompt += "Income Distribution:\n"
            for group, data in income_dist.items():
                pct = data.get('percentage', 0)
                median = data.get('median_income_rm', 0)
                prompt += f"  - {group}: {pct}% (median: RM{median})\n"
        spending = economic_indicators.get('spending_patterns', {})
        if spending:
            food_bev = spending.get('food_beverage', {})
            if food_bev:
                prompt += f"Food & Beverage Spending: {food_bev.get('percentage', 0)}% of income (avg RM{food_bev.get('avg_monthly_rm', 0)}/month)\n"

    if holiday_context:
        prompt += f"\nMalaysia Public Holidays (Pulau Pinang):\n{holiday_context}\n"

    if spark_section:
        prompt += f"\n{spark_section}\n"

    prompt += """
Your task is to generate 2-3 CUSTOM scenarios that can be SIMULATED with consumer agents making visit/purchase decisions.

CRITICAL: These scenarios will be simulated with AI customer agents who decide whether to visit the business each week. Scenarios MUST affect customer behavior (visit frequency, spending, churn).

IMPORTANT GUIDELINES:
1. Create scenarios that SPECIFICALLY address the user's question
2. Use actual data from news articles and economic indicators
3. Focus on factors that affect CUSTOMER DECISIONS (not business operations)
4. Each scenario should test how customers REACT to changes
5. Include concrete parameters that affect customer behavior
6. Invent the right scenario_type for the situation — use a concise snake_case label (e.g. branch_expansion, loyalty_program, delivery_launch). Do NOT limit yourself to a fixed list.

WHAT MAKES A GOOD SIMULATABLE SCENARIO:
- It describes a change that customers directly experience (price, availability, convenience, competition, promotion)
- It gives agents enough context to decide: will I visit more, less, or stop entirely?
- The description is written from the customer's perspective

WHAT CANNOT BE SIMULATED:
- ❌ Pure internal operations (staff training, supplier negotiation, accounting changes)
- ❌ Abstract strategy (market analysis, brand positioning) with no customer-facing change
- ❌ Anything where customers wouldn't notice or react differently

EXAMPLE FOR "How will fuel prices affect my business?":
{
  "analysis": "Rising fuel prices affect your business in two ways: (1) customers have less disposable income for dining out, especially B40 households, and (2) your supply costs may increase, forcing you to raise prices.",
  "recommended_action": "Monitor customer visit frequency and consider absorbing some cost increases initially to maintain customer loyalty.",
  "scenarios": [
    {
      "scenario_name": "Customers Reduce Visits Due to Fuel Costs",
      "scenario_type": "economic_shock",
      "description": "Fuel prices increased 10%. B40 customers (40% of your area) reduce dining out by 20% to save money. M40 customers reduce by 10%.",
      "parameters": {"price_change_percent": 0, "b40_visit_reduction_percent": 20, "m40_visit_reduction_percent": 10, "duration_weeks": 4},
      "relevance_score": 95,
      "expected_impact": "15-20% reduction in total visits, especially from B40 customers"
    },
    {
      "scenario_name": "Price Increase to Cover Fuel Costs",
      "scenario_type": "price_change",
      "description": "You raise prices by 5% to cover increased supply costs from fuel price hike. Price-sensitive customers may reduce visits.",
      "parameters": {"price_change_percent": 5},
      "relevance_score": 90,
      "expected_impact": "B40 customers highly sensitive to price increase, may reduce visits by 15-25%"
    }
  ],
  "context_summary": "Fuel prices up 10% affects customer spending power and your supply costs"
}

EXAMPLE FOR "What happens if I open a new branch in Bayan Lepas?":
{
  "analysis": "Opening a new branch means customers in Bayan Lepas will encounter your cafe for the first time. We can simulate how they adopt it, whether pricing draws them in, and how loyal they become.",
  "recommended_action": "Test customer adoption at the new location with different opening strategies.",
  "scenarios": [
    {
      "scenario_name": "New Branch Grand Opening",
      "scenario_type": "branch_expansion",
      "description": "Your cafe opens a new branch in Bayan Lepas. Customers in the area now have access to your cafe for the first time. Simulate how many would visit, return, or ignore it based on their income level and habits.",
      "parameters": {"price_change_percent": 0, "new_location": true, "grand_opening": true},
      "relevance_score": 95,
      "expected_impact": "Measure initial adoption rate and which customer segments are most likely to become regulars"
    },
    {
      "scenario_name": "Introductory Discount at New Branch",
      "scenario_type": "branch_expansion_with_promotion",
      "description": "New branch opens with a 15% introductory discount for the first month. Customers weigh the savings against the effort of trying a new place.",
      "parameters": {"price_change_percent": -15, "new_location": true, "promotion_duration_weeks": 4},
      "relevance_score": 88,
      "expected_impact": "Higher initial footfall from price-sensitive B40/M40 customers; test if they return after discount ends"
    }
  ],
  "context_summary": "Bayan Lepas has mixed income demographics; new branch success depends on customer adoption and local competition"
}

Now generate scenarios for the user's actual question. Remember: scenarios must be SIMULATABLE with customer agents making visit/purchase decisions. Return ONLY valid JSON with the structure shown above."""
    return prompt


def _format_dict(data: Dict[str, Any], indent: int = 0) -> str:
    """Format dictionary for prompt display."""
    lines = []
    prefix = "  " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_format_dict(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}: {', '.join(str(v) for v in value)}")
        else:
            lines.append(f"{prefix}{key}: {value}")
    return "\n".join(lines)


def _format_list(items: List[str]) -> str:
    """Format list for prompt display."""
    return "\n".join(f"- {item}" for item in items)
