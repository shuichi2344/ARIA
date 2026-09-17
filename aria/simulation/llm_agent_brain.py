"""
LLM Agent Brain - Core LLM integration for agent decision-making.

The LLM serves as the 'brain' of customer agents, generating:
1. Rich agent profiles
2. Unified decisions + messages (decision and reasoning in one call)
"""

import re
import json
from aria.llm.llm_client import LLMClient
from typing import Dict, List, Optional

# Regex patterns compiled once
THINK_PATTERN = re.compile(r'<think>.*?</think>', re.DOTALL)
EMOJI_PATTERN = re.compile("["
    u"\U0001F600-\U0001F64F"
    u"\U0001F300-\U0001F5FF"
    u"\U0001F680-\U0001F6FF"
    u"\U0001F1E0-\U0001F1FF"
    u"\U00002702-\U000027B0"
    u"\U000024C2-\U0001F251"
    "]+", flags=re.UNICODE)


def _clean_response(raw: str) -> str:
    """Strip thinking tags, emojis, word counts, and explanation artifacts from LLM output."""
    text = THINK_PATTERN.sub('', raw).strip()
    text = text.split('**Explanation:**')[0].strip()
    text = text.split('Explanation:')[0].strip()
    text = text.split('**Note:**')[0].strip()
    text = text.split('Note:')[0].strip()
    text = text.split('**Test:**')[0].strip()
    text = text.split('Test:')[0].strip()
    text = text.split('This is a test')[0].strip()
    text = EMOJI_PATTERN.sub('', text)
    
    # Strip trailing word/character count annotations like "(70 words)" or "(68 words)"
    text = re.sub(r'\s*\(\d+\s+words?\)\s*$', '', text, flags=re.IGNORECASE).strip()
    
    # Fix malformed "They asked:" or similar prefixes
    # Pattern: "They asked: 'They' is..." or "They: 'They is..."
    text = re.sub(r'^(They|He|She)\s+(asked|said)?:\s*[\'"]?\1[\'"]?\s+is\s+', r'\1 is ', text, flags=re.IGNORECASE)
    
    # Also fix quoted pronoun at start: "'They' is a..." → "They are a..."
    text = re.sub(r'^[\'"]?(They|He|She)[\'"]?\s+is\s+a\s+', r'\1 are a ', text, flags=re.IGNORECASE)
    
    # Remove "Profile:" prefix if present
    text = re.sub(r'^Profile:\s*', '', text, flags=re.IGNORECASE)
    
    return text.strip()


def _format_structured_personality(
    customer_type: str,
    visit_frequency: str, 
    values: str,
    spending_habit: str,
    loyalty_factor: str
) -> str:
    """
    Format personality using a fixed structure to ensure consistency.
    
    Args:
        customer_type: e.g., "student", "working professional", "family with kids"
        visit_frequency: e.g., "2-3 times per week", "once weekly", "occasionally"
        values: What they prioritize, e.g., "convenience and WiFi", "affordable family meals"
        spending_habit: How they manage budget, e.g., "stays under RM20", "compares prices"
        loyalty_factor: What keeps or breaks loyalty, e.g., "switches if WiFi becomes unreliable"
    
    Returns:
        Formatted personality string (50-70 words)
    """
    return (
        f"Customer type: {customer_type}. "
        f"Visits {visit_frequency}. "
        f"Values {values} most. "
        f"Spending: {spending_habit}. "
        f"Loyalty: {loyalty_factor}."
    )


class LLMAgentBrain:
    """
    LLM serves as the 'brain' of customer agents, generating:
    1. Rich agent profiles
    2. Unified decisions + messages
    """
    
    # Shared income level descriptions so the model understands Malaysian context
    INCOME_DESCRIPTIONS = {
        "B40": "B40 (Bottom 40% - household income below RM4,850/month). Price-conscious with limited disposable income and minimal spending power. A 5-10% increase is uncomfortable but you'll still visit occasionally. You will SKIP or CHURN if the change is extremely unreasonable/high.",
        "M40": "M40 (Middle 40% - household income RM4,850-RM10,970/month). Low to oderate spending power. A 5-15% increase is noticeable — you'll may still consider visit. You will SKIP or CHURN if the change is extremely unreasonable/high.",
        "T20": "T20 (Top 20% - household income above RM10,970/month). Higher disposable income,compared to M40 and B40. Price is not a major concern for you but you will SKIP or CHURN if the change is extremely unreasonable/high.",
    }
    
    def __init__(self, model_name: str = "qwen2.5:7b"):
        self.client = LLMClient()
        self.model = model_name
        
    async def generate_agent_profiles_batch(
        self,
        agents: List[Dict],
        business_profile: Optional[Dict] = None,
        assigned_personalities: List[Optional[str]] = None
    ) -> List[str]:
        """
        Generate personalities for ALL agents in one LLM call.
        More reliable and faster than individual calls.
        
        Args:
            agents: List of agent dicts with age_range, income_level, etc.
            business_profile: Business info
            assigned_personalities: Pre-assigned personality types for each agent
        
        Returns:
            List of formatted personality strings (one per agent)
        """
        if not agents:
            return []
        
        # Build prompt for batch generation
        location = business_profile.get('location', 'Georgetown') if business_profile else 'Georgetown'
        business_name = business_profile.get('name', business_profile.get('business_name', '')) if business_profile else ''
        business_type = business_profile.get('type', business_profile.get('business_type', '')) if business_profile else ''
        
        business_info = ""
        if business_profile:
            price_min = business_profile.get('price_range_min', 0)
            price_max = business_profile.get('price_range_max', 0)
            target_audience = business_profile.get('target_audience', '')
            usp = business_profile.get('unique_selling_points', '')
            
            business_info = f"\nBusiness: {business_name}"
            if business_type:
                business_info += f" ({business_type})"
            if price_min > 0 and price_max > 0:
                business_info += f"\nPrice range: RM{price_min:.2f} - RM{price_max:.2f}"
            if target_audience:
                business_info += f"\nTarget audience: {target_audience}"
            if usp:
                business_info += f"\nWhat makes it special: {usp}"
        
        # Build agent list for prompt
        agent_specs = []
        for i, agent in enumerate(agents):
            income_level = agent.get('income_level', 'M40')
            age_range = agent.get('age_range', '25-34')
            assigned_type = assigned_personalities[i] if assigned_personalities and i < len(assigned_personalities) else None
            
            income_desc = self.INCOME_DESCRIPTIONS.get(income_level, self.INCOME_DESCRIPTIONS["M40"])
            
            agent_spec = f"Agent {i+1}: {age_range} years old, {income_level} income"
            if assigned_type:
                agent_spec += f", must be a {assigned_type}"
            
            agent_specs.append(agent_spec)
        
        prompt = f"""Generate {len(agents)} distinct Malaysian customer personalities for a business simulation.

Business Context:
{business_info}
Location: {location}

Agents to create:
{chr(10).join(agent_specs)}

CRITICAL: Respond with ONLY a valid JSON array containing {len(agents)} complete personality objects. NO explanations, NO thinking process, NO commentary.

Required format - JSON array with {len(agents)} objects:
[
  {{
    "customer_type": "3-6 word description",
    "visit_frequency": "how often they visit",
    "values": "15-25 words about priorities",
    "spending_habit": "10-20 words about budget",
    "loyalty_factor": "15-25 words about loyalty"
  }},
  ... ({len(agents)} total objects)
]

MANDATORY RULES:
1. Output ONLY the JSON array - nothing else
2. Array must have EXACTLY {len(agents)} objects
3. Each object must have ALL 5 fields complete
4. NO meta-commentary, NO "seems incomplete", NO thinking process
5. Each personality must be UNIQUE and DIFFERENT
6. Use Malaysian context (RM currency, local habits, behaviors)
7. Match assigned personality types where specified
8. Income levels guide spending:
   - B40: Very price-conscious, budgets carefully, RM5-15 per visit
   - M40: Moderate spending, balances price and quality, RM15-30 per visit
   - T20: Comfortable spending, values quality, RM30-50+ per visit

GOOD EXAMPLE (for 2 agents):
[
  {{
    "customer_type": "university student from nearby campus",
    "visit_frequency": "2-3 times weekly between classes",
    "values": "free WiFi and power outlets for study sessions, quiet corners, affordable drinks",
    "spending_habit": "orders cheapest drink (RM6-8), stays 2-3 hours, never buys food to save money",
    "loyalty_factor": "will switch to library or cheaper kopitiam if prices increase or if long-stay customers get asked to leave"
  }},
  {{
    "customer_type": "retired teacher enjoying morning routine",
    "visit_frequency": "every weekday morning at 9am sharp",
    "values": "familiar faces, traditional kopi-o preparation, consistent taste, peaceful morning atmosphere",
    "spending_habit": "always orders kopi-o and toast, spends exactly RM9.50 daily, tips RM0.50 for good service",
    "loyalty_factor": "extremely loyal after 15 years of daily visits, only closure or major recipe changes would drive away"
  }}
]

Now generate the complete JSON array for all {len(agents)} agents:"""

        try:
            response = await self.client.generate(
                prompt=prompt,
                temperature=0.9,  # Higher temp for more variety
                max_tokens=6000   # Allow for large output
            )
            
            raw_response = response['response'].strip()
            
            # Clean markdown code blocks
            json_text = raw_response
            if '```json' in json_text:
                json_text = json_text.split('```json')[1].split('```')[0].strip()
            elif '```' in json_text:
                json_text = json_text.split('```')[1].split('```')[0].strip()
            
            # Find JSON array
            array_match = re.search(r'\[[\s\S]*\]', json_text)
            if array_match:
                json_text = array_match.group()
            
            # Parse JSON
            personalities_data = json.loads(json_text)
            
            if not isinstance(personalities_data, list):
                raise ValueError("Response is not a JSON array")
            
            if len(personalities_data) != len(agents):
                print(f"   ⚠ LLM returned {len(personalities_data)} personalities, expected {len(agents)}")
                # Pad or trim to match
                while len(personalities_data) < len(agents):
                    personalities_data.append(personalities_data[-1])  # Duplicate last one
                personalities_data = personalities_data[:len(agents)]
            
            # Format each personality
            formatted = []
            for i, data in enumerate(personalities_data):
                required = ['customer_type', 'visit_frequency', 'values', 'spending_habit', 'loyalty_factor']
                if all(k in data for k in required):
                    formatted.append(_format_structured_personality(
                        customer_type=data['customer_type'],
                        visit_frequency=data['visit_frequency'],
                        values=data['values'],
                        spending_habit=data['spending_habit'],
                        loyalty_factor=data['loyalty_factor']
                    ))
                else:
                    # Missing fields - use fallback
                    print(f"   ⚠ Agent {i+1} missing fields: {[k for k in required if k not in data]}")
                    formatted.append(self._get_fallback_personality(agents[i], assigned_personalities[i] if assigned_personalities and i < len(assigned_personalities) else None))
            
            return formatted
            
        except Exception as e:
            print(f"   ⚠ Batch generation failed: {e}")
            print(f"   ⚠ Falling back to individual generation")
            # Fall back to individual generation
            return await self._generate_individual_fallback(agents, business_profile, assigned_personalities)
    
    def _get_fallback_personality(self, agent: Dict, assigned_type: Optional[str]) -> str:
        """Generate a basic fallback personality when parsing fails."""
        income = agent.get('income_level', 'M40')
        age = agent.get('age_range', '25-34')
        customer_type = assigned_type or 'regular customer'
        
        return _format_structured_personality(
            customer_type=f"{customer_type} in {age} age range",
            visit_frequency="regularly visits",
            values="quality service and good value for money",
            spending_habit=f"budgets based on {income} income, spends moderately",
            loyalty_factor="price-sensitive but values consistency, compares alternatives occasionally"
        )
    
    async def _generate_individual_fallback(
        self,
        agents: List[Dict],
        business_profile: Optional[Dict],
        assigned_personalities: List[Optional[str]]
    ) -> List[str]:
        """Fallback to individual generation if batch fails."""
        results = []
        for i, agent in enumerate(agents):
            assigned = assigned_personalities[i] if assigned_personalities and i < len(assigned_personalities) else None
            try:
                personality = await self.generate_agent_profile(
                    age_range=agent.get('age_range', '25-34'),
                    income_level=agent.get('income_level', 'M40'),
                    location=business_profile.get('location', 'Georgetown') if business_profile else 'Georgetown',
                    business_profile=business_profile,
                    assigned_personality=assigned
                )
                results.append(personality)
            except Exception as e:
                print(f"   ⚠ Agent {i+1} individual generation failed: {e}")
                results.append(self._get_fallback_personality(agent, assigned))
        return results
    
    async def generate_agent_profile(
        self, 
        age_range: str, 
        income_level: str, 
        location: str,
        district: Optional[str] = None,
        business_profile: Optional[Dict] = None,
        assigned_personality: Optional[str] = None
    ) -> str:
        """
        Generate a rich personality profile for a customer agent.
        Auto-detects B2B vs B2C from business_profile.customer_type.
        
        Args:
            age_range: e.g. "25-34" (for B2C) or business size (for B2B)
            income_level: B40, M40, T20 (for B2C) or Micro/Small/Medium (for B2B)
            location: Location string
            district: District (optional)
            business_profile: Business info dict (optional)
            assigned_personality: Pre-assigned personality type (e.g. "student", "freelancer")
        
        Returns:
            Rich personality profile (3-5 sentences, ~60-80 words)
        """
        customer_type = (business_profile or {}).get('customer_type', 'B2C')
        
        if customer_type == 'B2B':
            return await self._generate_b2b_profile(business_profile, age_range, income_level)
        
        # Income level descriptions so model understands Malaysian context
        income_desc = self.INCOME_DESCRIPTIONS.get(income_level, self.INCOME_DESCRIPTIONS["M40"])
        
        # Build business context
        business_info = ""
        target_audience = ""
        if business_profile:
            business_name = business_profile.get('name', business_profile.get('business_name', ''))
            business_type = business_profile.get('type', business_profile.get('business_type', ''))
            price_min = business_profile.get('price_range_min', 0)
            price_max = business_profile.get('price_range_max', 0)
            target_audience = business_profile.get('target_audience', '')
            if not target_audience:
                # Build from separate segment columns
                segments = business_profile.get('b2c_target_segments', []) or []
                b2b = business_profile.get('b2b_target_types', []) or []
                all_targets = segments + b2b
                target_audience = ', '.join(all_targets) if all_targets else ''
            usp = business_profile.get('unique_selling_points', '')
            
            business_info = f"\nBusiness: {business_name}"
            if business_type:
                business_info += f" ({business_type})"
            if price_min > 0 and price_max > 0:
                business_info += f"\nPrice range: RM{price_min:.2f} - RM{price_max:.2f}"
            if target_audience:
                business_info += f"\nTarget audience: {target_audience}"
            if usp:
                business_info += f"\nWhat makes it special: {usp}"
        
        # Build personality guidance from target customers or assigned personality
        personality_guidance = ""
        if assigned_personality:
            personality_guidance = f"\nIMPORTANT: This person is a {assigned_personality}. Build their entire profile around this identity — their daily routine, why they visit this business, and how it fits their lifestyle as a {assigned_personality}."
        elif target_audience:
            personality_guidance = f"\nIMPORTANT: This person should clearly be one of these customer types: {target_audience}. Make their lifestyle and occupation match one of these types."
        
        prompt = f"""Generate a realistic Malaysian customer profile for a simulation. This profile will be used by an AI to make decisions about whether to visit a business.

Demographics:
- Age: {age_range}
- Income Level: {income_desc}
- Location: {location}{f', {district}' if district else ''}
{business_info}
{personality_guidance}

YOU MUST RESPOND WITH ONLY A VALID JSON OBJECT. NO EXPLANATIONS. NO THINKING PROCESS. NO COMMENTARY.

Required JSON format (all 5 fields are mandatory):
{{
  "customer_type": "3-6 word description of who they are",
  "visit_frequency": "how often they visit",
  "values": "15-25 words about what they prioritize",
  "spending_habit": "10-20 words about budget management",
  "loyalty_factor": "15-25 words about what keeps or breaks loyalty"
}}

CRITICAL RULES:
1. Output ONLY the JSON object above - nothing else
2. ALL 5 fields must be present and complete
3. NO meta-commentary like "seems incomplete", "let me correct", "we guess"
4. NO thinking process - just the final JSON
5. NO partial JSON - complete all fields before responding
6. Customer type must match: {assigned_personality if assigned_personality else 'appropriate target customer'}
7. Use Malaysian context (RM currency, local habits)

GOOD EXAMPLE:
{{
  "customer_type": "retired teacher enjoying cafe culture",
  "visit_frequency": "twice weekly in the mornings",
  "values": "familiar atmosphere, traditional coffee preparation, and affordable prices for daily visits",
  "spending_habit": "orders kopi-o and toast daily, spends RM8-12 per visit, never exceeds RM15",
  "loyalty_factor": "extremely loyal due to 10-year routine, only major closure or price doubling would drive away"
}}

BAD EXAMPLE (DO NOT DO THIS):
{{
  "customer_type": "parent with school-aged children",
  "visit_frequency": "once every two weeks",
  "values": "affordable meals",
  "spending_habit": "seems incomplete. Let me correct it based on

^ This is WRONG. Complete ALL fields properly before responding.

Now generate ONLY the complete JSON for a {assigned_personality if assigned_personality else 'customer'}:"""

        response = await self.client.generate(
            prompt=prompt,
            temperature=0.85,
            max_tokens=400
        )
        
        raw_response = response['response'].strip()
        
        # Try to parse as JSON
        try:
            # Clean up response - remove markdown code blocks if present
            json_text = raw_response
            if '```json' in json_text:
                json_text = json_text.split('```json')[1].split('```')[0].strip()
            elif '```' in json_text:
                json_text = json_text.split('```')[1].split('```')[0].strip()
            
            # Remove any text before/after the JSON object
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', json_text, re.DOTALL)
            if json_match:
                json_text = json_match.group()
            
            data = json.loads(json_text)
            
            # Validate required fields
            required = ['customer_type', 'visit_frequency', 'values', 'spending_habit', 'loyalty_factor']
            if all(k in data for k in required):
                # Format using structured template
                result = _format_structured_personality(
                    customer_type=data['customer_type'],
                    visit_frequency=data['visit_frequency'],
                    values=data['values'],
                    spending_habit=data['spending_habit'],
                    loyalty_factor=data['loyalty_factor']
                )
                return result
            else:
                print(f"   ⚠ JSON missing required fields, falling back to text cleaning")
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            print(f"   ⚠ JSON parsing failed ({e}), falling back to text cleaning")
        
        # Fallback: clean the text response
        result = _clean_response(raw_response)
        
        if not result or len(result) < 20:
            # Last resort fallback
            result = f"Customer type: {assigned_personality or 'regular customer'}. Visits regularly. Values {', '.join(business_profile.get('unique_selling_points', 'quality service').split(',')[:2]) if business_profile else 'convenience'}. Spending: stays within budget based on {income_level} income. Loyalty: price-sensitive, compares alternatives."
        
        return result
    
    async def _generate_b2b_profile(
        self,
        business_profile: Optional[Dict],
        business_size: str,
        segment: str,
    ) -> str:
        """
        Generate a B2B customer profile (a business buying from another business).
        
        Args:
            business_profile: The supplier business profile
            business_size: Micro/Small/Medium
            segment: Customer business segment (e.g., "Workshop", "Retail Shop")
        """
        business_name = ""
        business_type = ""
        location = ""
        b2b = {}
        if business_profile:
            business_name = business_profile.get('name', '')
            business_type = business_profile.get('business_type', '')
            location = business_profile.get('location', '')
            b2b = business_profile.get('b2b_profile', {}) or {}
        
        avg_transaction = b2b.get('avg_transaction_rm', 500)
        purchase_frequency = b2b.get('purchase_frequency', 'monthly')
        decision_factors = b2b.get('decision_factors', ['price', 'quality', 'reliability'])
        
        prompt = f"""Generate a realistic Malaysian B2B customer profile for a simulation. This is a business that buys from another business as a supplier.

Supplier Business: {business_name} ({business_type}) in {location}

Customer Business Details:
- Business size: {business_size}
- Segment: {segment}
- Typical transaction: RM{avg_transaction}
- Purchase frequency: {purchase_frequency}
- Key decision factors: {', '.join(decision_factors[:3])}

Write a 3-5 sentence profile covering:
1. What kind of business they are (size, segment, what they do)
2. Their procurement relationship with this supplier (how long, how often, contract type)
3. What they prioritize when buying (price? quality? reliability? delivery speed?)
4. Their payment behavior (pays on time? negotiates terms? switches for better deals?)
5. One unique trait affecting their loyalty (e.g., "loyal due to long relationship", "always shopping for better prices", "values consistent quality over cheapness")

Rules:
- Use third person ("This business" or "They")
- Be specific to Malaysian MSME context
- Keep under 80 words
- No business names

Profile:"""

        response = await self.client.generate(
            prompt=prompt,
            temperature=0.9,
            max_tokens=2000
        )
        
        result = _clean_response(response['response'])
        
        if not result:
            result = f"A {business_size} {segment} that orders {purchase_frequency} from this supplier. Values reliability and competitive pricing."
        
        return result
    
    async def check_peer_susceptibility(
        self,
        agent_profile: str,
        scenario_desc: str,
        peer_messages: List[str],
        current_decision: str,
        direction: str,
    ) -> Dict:
        """
        Ask the LLM whether this agent would even pay attention to peer opinions,
        given who they are and what the scenario is.

        Replaces hardcoded PERSONALITY_GATE / GATE_PROBABILITY tables so the
        decision is scenario-aware and personality-aware rather than a static prior.

        Args:
            agent_profile: The agent's rich profile text.
            scenario_desc: Description of the scenario being simulated.
            peer_messages: What peers are saying (1-3 messages).
            current_decision: The agent's current decision ("visit" or "skip").
            direction: "negative" (peers are unhappy) or "positive" (peers are happy).

        Returns:
            {"susceptible": bool, "reason": str}
        """
        peer_block = "\n".join(f'- "{m}"' for m in peer_messages[:3])

        if direction == "negative":
            prompt_question = (
                "Your friends seem unhappy about this. "
                "Given who you are, your lifestyle, and this specific situation — "
                "would you actually pay attention to their complaints and reconsider going?"
            )
        else:
            prompt_question = (
                "Your friends seem to have enjoyed it despite the situation. "
                "Given who you are, your lifestyle, and this specific situation — "
                "would their positive experience make you reconsider skipping?"
            )

        prompt = f"""You are: {agent_profile}

Scenario: {scenario_desc}
Your current decision: {current_decision.upper()}

What friends are saying:
{peer_block}

{prompt_question}

Reply in EXACTLY this format (2 lines only):
Susceptible: yes OR no
Reason: [one short sentence — why you would or would not care about what your friends say here]"""

        response = await self.client.generate(
            prompt=prompt,
            temperature=0.3,
            max_tokens=80,
        )
        raw = _clean_response(response["response"])

        susceptible = False
        reason = ""
        for line in raw.split("\n"):
            line_stripped = line.strip()
            line_lower = line_stripped.lower()
            if line_lower.startswith("susceptible:"):
                answer = line_lower.replace("susceptible:", "").strip()
                susceptible = answer.startswith("y")
            elif line_lower.startswith("reason:"):
                reason = line_stripped[len("Reason:"):].strip().strip('"').strip("'")

        return {"susceptible": susceptible, "reason": reason or "No specific reason given."}

    async def make_decision_and_message(
        self,
        agent_profile: str,
        scenario_context: Dict,
        business_context: Optional[Dict] = None,
        peer_messages: Optional[List[str]] = None,
        income_level: Optional[str] = None,
    ) -> Dict:
        """
        Unified LLM call: decides (visit/skip/churn) AND generates a message
        in one shot, ensuring consistency between decision and reasoning.
        Auto-detects B2B vs B2C from business_context.customer_type.
        
        Uses scenario-aware prompting — only mentions price sensitivity when
        the scenario is actually about pricing.
        """
        customer_type = (business_context or {}).get('customer_type', 'B2C')
        
        if customer_type == 'B2B':
            return await self._b2b_decision(agent_profile, scenario_context, business_context, peer_messages, income_level)
        
        scenario_desc = scenario_context.get('description', '')
        scenario_type = scenario_context.get('scenario_type', '')
        
        # Build business block
        business_block = ""
        business_name = ""
        if business_context:
            business_name = business_context.get('name', business_context.get('business_name', ''))
            business_type = business_context.get('type', business_context.get('business_type', ''))
            location = business_context.get('location', '')
            price_min = business_context.get('price_range_min', 0)
            price_max = business_context.get('price_range_max', 0)
            
            business_block = f"\nBusiness: {business_name}" if business_name else ""
            if business_type:
                business_block += f" ({business_type})"
            if location:
                business_block += f" in {location}"
            if price_min > 0 and price_max > 0:
                business_block += f"\nTypical prices: RM{price_min:.0f}-RM{price_max:.0f}"
            usp = business_context.get('unique_selling_points', '')
            if usp:
                business_block += f"\nWhat makes it special: {usp}"
            years = business_context.get('years_operating')
            if years and years > 0:
                if years >= 5:
                    business_block += f"\nEstablished business ({years} years operating) with a loyal regular customer base."
                else:
                    business_block += f"\nRelatively new business ({years} year{'s' if years != 1 else ''} operating), still building its customer base."
        
        # Build peer context
        peer_block = ""
        if peer_messages:
            peer_block = "\nWhat friends are saying:\n" + "\n".join(f"- {m}" for m in peer_messages[:3])
        
        # Income level — only relevant for price-related scenarios
        income_block = ""
        if income_level and scenario_type in ('price_change', 'pricing'):
            income_block = f"\n\nYOUR INCOME LEVEL: {self.INCOME_DESCRIPTIONS.get(income_level, self.INCOME_DESCRIPTIONS['M40'])}"
        
        # Scenario-specific decision guidelines
        if scenario_type in ('price_change', 'pricing'):
            guidelines = """DECISION GUIDELINES (Price Change Scenario):
- VISIT: The price increase is within your tolerance. You can still afford it and will keep coming.
- SKIP: The increase is noticeable — you'll reduce how often you visit, but won't stop entirely.
- CHURN: The increase is far beyond what you can justify. You'll find an alternative permanently."""
        elif scenario_type == 'demand_surge':
            guidelines = """DECISION GUIDELINES (Demand Surge Scenario):
- VISIT: You still want to go despite it being busier. You're loyal or it's worth the wait.
- SKIP: The crowds and longer wait times put you off this time. You'll come back when it's quieter.
- CHURN: The consistently overcrowded experience has permanently turned you away."""
        elif scenario_type == 'operating_hours_change':
            guidelines = """DECISION GUIDELINES (Operating Hours Change):
- VISIT: The new hours work for your schedule, or you already visit during normal hours.
- SKIP: The hours don't align well with your routine this time.
- CHURN: The change makes it permanently inconvenient for you to visit."""
        else:
            guidelines = """DECISION GUIDELINES:
- VISIT: The change is acceptable or doesn't significantly affect you.
- SKIP: The change is somewhat inconvenient — you'll visit less often.
- CHURN: The change makes this business no longer suitable for you."""
        
        prompt = f"""You are this person: {agent_profile}
{business_block}

SCENARIO: {scenario_desc}
{peer_block}{income_block}
Based on who you are and the scenario above, decide: will you VISIT, SKIP, or CHURN (stop going permanently)?

{guidelines}

IMPORTANT RULES:
- Base your decision ONLY on the scenario described above
- Do NOT assume or invent details not mentioned in the scenario
- Do NOT mention price changes unless the scenario is specifically about pricing
- Your message should reflect the ACTUAL scenario, not a different one
- All three decisions (visit, skip, churn) are equally valid — pick the one that fits YOUR situation

Reply in EXACTLY this format (3 lines only, nothing else):
Decision: visit OR skip OR churn
Message: [a short 15-25 word message you'd tell a friend about this — must relate to the actual scenario]
Spend: [amount in RM you'd spend if visiting, or 0]"""

        response = await self.client.generate(
            prompt=prompt,
            temperature=0.7,
            max_tokens=2000
        )
        
        raw = _clean_response(response['response'])
        
        # Parse structured response
        decision = "visit"
        message = ""
        spend = 0.0
        
        for line in raw.split('\n'):
            line_stripped = line.strip()
            line_lower = line_stripped.lower()
            if line_lower.startswith('decision:'):
                d = line_lower.replace('decision:', '').strip()
                if 'churn' in d:
                    decision = 'churn'
                elif 'skip' in d:
                    decision = 'skip'
                else:
                    decision = 'visit'
            elif line_lower.startswith('message:'):
                message = line_stripped[len('Message:'):].strip().strip('"').strip("'")
            elif line_lower.startswith('spend:'):
                try:
                    spend_str = re.sub(r'[^\d.]', '', line_lower.replace('spend:', ''))
                    spend = float(spend_str) if spend_str else 0.0
                except ValueError:
                    spend = 0.0
        
        # Fallback if parsing failed
        if not message:
            place = business_name or 'the place'
            if decision == 'visit':
                message = f"Went to {place} this week."
            elif decision == 'churn':
                message = f"Not going back to {place} anymore."
            else:
                message = f"Skipping {place} this week."
        
        return {
            "decision": decision,
            "message": message,
            "spend_amount": spend
        }

    async def _b2b_decision(
        self,
        agent_profile: str,
        scenario_context: Dict,
        business_context: Optional[Dict] = None,
        peer_messages: Optional[List[str]] = None,
        business_size: Optional[str] = None,
    ) -> Dict:
        """
        B2B-specific decision making. Uses procurement/relationship logic
        instead of consumer impulse logic.
        
        For B2B agents, decisions reflect:
        - VISIT = continue ordering / renew contract
        - SKIP = reduce order volume or delay this cycle
        - CHURN = switch supplier / terminate relationship
        """
        scenario_desc = scenario_context.get('description', '')
        
        # Build supplier business block
        supplier_block = ""
        supplier_name = ""
        if business_context:
            supplier_name = business_context.get('name', business_context.get('business_name', ''))
            business_type = business_context.get('type', business_context.get('business_type', ''))
            location = business_context.get('location', '')
            
            supplier_block = f"\nSupplier: {supplier_name}" if supplier_name else ""
            if business_type:
                supplier_block += f" ({business_type})"
            if location:
                supplier_block += f" in {location}"
            
            b2b = business_context.get('b2b_profile', {}) or {}
            avg_transaction = b2b.get('avg_transaction_rm', 500)
            if avg_transaction:
                supplier_block += f"\nTypical order value: RM{avg_transaction}"
        
        # Build peer context (other businesses in same segment)
        peer_block = ""
        if peer_messages:
            peer_block = "\nWhat other businesses are saying:\n" + "\n".join(f"- {m}" for m in peer_messages[:3])
        
        # B2B size sensitivity 
        size_block = ""
        if business_size:
            size_map = {
                "Micro": (
                    "You are a Micro business in Malaysia (less than RM300,000 turnover or fewer than 5 employees). "
                    "You have tight margins and limited cash flow — every cost increase directly impacts your bottom line. "
                    "However, switching suppliers is still risky for you (lost credit terms, delivery disruption). "
                    "A 5-10% price increase hurts but you'll likely absorb it while looking for alternatives. "
                    "A 10-20% increase makes you consider reducing orders or finding a cheaper supplier. "
                    "Above 20% you will likely switch because your margins cannot sustain it."
                ),
                "Small": (
                    "You are a Small business in Malaysia (RM300,000 to less than RM3 million turnover or 5-30 employees). "
                    "You have moderate margins and established procurement processes. "
                    "Switching suppliers means retraining staff, renegotiating terms, and risking delivery disruptions. "
                    "A 5-15% price increase is manageable — you'll negotiate or absorb it rather than switch. "
                    "A 15-25% increase makes you reduce orders or actively seek alternatives. "
                    "You would only switch if the increase exceeds 25% or service quality declines significantly."
                ),
                "Medium": (
                    "You are a Medium-sized business in Malaysia (RM3 million to less than RM20 million turnover or 30-75 employees). "
                    "You have healthy margins, formal procurement processes, and long-term supplier contracts. "
                    "Switching suppliers requires board approval, contract renegotiation, and transition planning. "
                    "A 5-15% price increase is a normal cost of doing business — you budget for annual increases. "
                    "A 15-25% increase is notable but you'll negotiate rather than switch. "
                    "Only increases above 25% or fundamental service failures would trigger a supplier change."
                ),
            }
            size_block = f"\n\nYOUR BUSINESS PROFILE:\n{size_map.get(business_size, size_map['Small'])}"
        
        prompt = f"""You are a Malaysian business represented by this profile: {agent_profile}
{supplier_block}

Your supplier has made this change: {scenario_desc}
{peer_block}{size_block}
As a business customer, decide: will you CONTINUE (keep ordering as usual), REDUCE (order less or delay), or SWITCH (find a new supplier)?

DECISION GUIDELINES:
- CONTINUE: The change is within normal business expectations. (output as "visit")
- REDUCE: The change is significant enough to make you cautious — you'll order less or delay, but switching is too costly/risky right now. (output as "skip")
- SWITCH: The change is extreme or breaks trust entirely. Only switch if the cost increase exceeds your budget and affordability, quality drops drastically, or the relationship is fundamentally broken. (output as "churn")

IMPORTANT: Businesses are sticky. Switching suppliers is expensive (lost credit terms, retraining, delivery risk, contract penalties). Most businesses absorb moderate price increases (5-15%) rather than switch. Only SWITCH for extreme changes.

Consider: your business size, the actual cost impact on your operations, the strength of your relationship, the cost of switching suppliers, and what your peers are doing.

Reply in EXACTLY this format (3 lines only):
Decision: visit OR skip OR churn
Message: [a short 15-25 word message about your business decision]
Spend: [monthly spend in RM if continuing, or 0 if switching]"""

        response = await self.client.generate(
            prompt=prompt,
            temperature=0.7,
            max_tokens=2000
        )
        
        raw = _clean_response(response['response'])
        
        decision = "visit"
        message = ""
        spend = 0.0
        
        for line in raw.split('\n'):
            line_stripped = line.strip()
            line_lower = line_stripped.lower()
            if line_lower.startswith('decision:'):
                d = line_lower.replace('decision:', '').strip()
                if 'churn' in d or 'switch' in d:
                    decision = 'churn'
                elif 'skip' in d or 'reduce' in d:
                    decision = 'skip'
                else:
                    decision = 'visit'
            elif line_lower.startswith('message:'):
                message = line_stripped[len('Message:'):].strip().strip('"').strip("'")
            elif line_lower.startswith('spend:'):
                try:
                    spend_str = re.sub(r'[^\d.]', '', line_lower.replace('spend:', ''))
                    spend = float(spend_str) if spend_str else 0.0
                except ValueError:
                    spend = 0.0
        
        if not message:
            place = supplier_name or 'this supplier'
            if decision == 'visit':
                message = f"Continuing to order from {place}."
            elif decision == 'churn':
                message = f"Switching away from {place} to a new supplier."
            else:
                message = f"Reducing orders with {place} this cycle."
        
        return {
            "decision": decision,
            "message": message,
            "spend_amount": spend
        }
