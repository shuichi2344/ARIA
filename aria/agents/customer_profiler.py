"""
Customer Profile Inference Agent

Uses LLM to automatically infer customer profiles based on business information,
with smart follow-up questions and user confirmation/correction flow.
"""

import json
import re
from typing import Dict, Any
from aria.llm import LLMClient


class CustomerProfiler:
    """
    Agent for inferring customer profiles using LLM with user confirmation.
    """
    
    def __init__(self):
        self.llm_client = LLMClient()
    
    async def infer_profile(self, business_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Infer customer profile based on business information using LLM.
        
        Args:
            business_info: Dictionary containing:
                - business_sector: str
                - business_subsector: str
                - business_type: str
                - location: str
                - district: str
                - unique_selling_points: str (optional)
        
        Returns:
            Dictionary with inferred customer profile including confidence level
        """
        system_prompt = """You are a business analyst specializing in Malaysian MSME (Micro, Small, Medium Enterprises) customer profiling. Your task is to infer typical customer profiles based on business information.

Context:
- Location: Penang, Malaysia
- Focus: MSME businesses
- Income levels: B40 (<RM4,850/month), M40 (RM4,851-RM10,970/month), T20 (>RM10,970/month)
- Age groups: 18-24, 25-34, 35-44, 45-54, 55-64, 65+

Your output must be a valid JSON object with the specified structure. Be concise and practical."""
        
        user_prompt = f"""Analyze this Malaysian MSME business and infer their typical customer profile:

Business Information:
- Business Type: {business_info.get('business_type', 'Unknown')}
- Location: {business_info.get('location', 'Penang')}, {business_info.get('district', 'Unknown')}
- Unique Selling Points: {business_info.get('unique_selling_points', 'Not specified')}

Instructions:
1. Determine if customers are B2C (individuals), B2B (businesses), or Both
2. For B2C: identify target customer segments (e.g., students, working professionals, families, foodies, tourists), income levels, avg transaction per visit
3. For B2B: identify target business types, business sizes, purchase frequency, avg transaction per order
4. Estimate price range (min and max) for individual items/services
5. Estimate items_per_transaction: how many items/services customers typically buy in one visit
6. Provide brief reasoning (1-2 sentences)

CRITICAL: Return ONLY valid JSON. No extra text before or after. No trailing commas.

Output format:
{{
  "customer_type": "B2C",
  "target_customers": "students, working professionals, foodies",
  "price_range": {{
    "min": 5,
    "max": 25
  }},
  "items_per_transaction": 2.5,
  "b2c_profile": {{
    "target_segments": ["students", "working professionals", "foodies"],
    "typical_income_levels": ["B40", "M40"],
    "avg_transaction_rm": 0
  }},
  "b2b_profile": null,
  "reasoning": "string explaining the inference"
}}

Return the JSON now:"""
        
        # Call LLM
        response = await self.llm_client.generate(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.3  # Lower temperature for more consistent output
        )
        
        # Extract response text
        response_text = response.get("response", "").strip()
        
        # Debug: Check if response is empty
        if not response_text:
            print(f"   âš  LLM returned empty response, using default profile")
            return self._get_default_profile(business_info)
        
        # Debug: Show first 200 chars of response
        # print(f"   [DEBUG] LLM response preview: {response_text[:200]}...")
        
        # Parse JSON response
        try:
            profile = json.loads(response_text)
            
            # Calculate avg_transaction_rm based on price_range and items_per_transaction
            profile = self._calculate_avg_transaction(profile)
            
            return profile
        except json.JSONDecodeError:
            # Fallback: try to extract JSON from response
            import re
            
            # Try to find JSON object in the response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    # Clean up common JSON issues
                    json_str = json_match.group()
                    # Remove trailing commas before closing braces/brackets
                    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
                    profile = json.loads(json_str)
                    
                    # Calculate avg_transaction_rm
                    profile = self._calculate_avg_transaction(profile)
                    
                    return profile
                except Exception as parse_error:
                    print(f"   âš  Failed to extract JSON: {parse_error}")
                    print(f"   âš  LLM response was malformed, using default profile")
            
            # If parsing fails, return default profile with low confidence
            return self._get_default_profile(business_info)
    
    def _get_default_profile(self, business_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a default profile when LLM inference fails.
        """
        return {
            "customer_type": "B2C",
            "target_customers": "working professionals, students",
            "price_range": {"min": 10, "max": 50},
            "items_per_transaction": 1.5,
            "b2c_profile": {
                "target_segments": ["working professionals", "students"],
                "typical_income_levels": ["B40", "M40"],
                "avg_transaction_rm": 0
            },
            "b2b_profile": None,
            "reasoning": "Default profile generated due to inference error"
        }
    
    def _calculate_avg_transaction(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate average transaction amount based on price range and items per transaction.
        
        For food businesses: customers typically order multiple items (e.g., coffee + pastry)
        For retail: customers may buy 1-3 items
        For services: usually 1 service per visit
        For B2B: bulk orders with multiple items
        
        Formula: avg_transaction = (price_min + price_max) / 2 * items_per_transaction
        """
        # Get price range
        price_range = profile.get('price_range', {})
        price_min = price_range.get('min', 10)
        price_max = price_range.get('max', 50)
        
        # Get items per transaction (default to 1.5 if not provided)
        items_per_transaction = profile.get('items_per_transaction', 1.5)
        
        # Calculate average item price
        avg_item_price = (price_min + price_max) / 2
        
        # Calculate average transaction
        avg_transaction = round(avg_item_price * items_per_transaction, 2)
        
        # Add to B2C profile if exists
        if profile.get('b2c_profile'):
            profile['b2c_profile']['avg_transaction_rm'] = avg_transaction
        
        # Add to B2B profile if exists (B2B typically has higher transaction values)
        if profile.get('b2b_profile'):
            # B2B transactions are typically larger (more items, bulk orders)
            b2b_multiplier = 3.0  # B2B customers typically order 3x more
            profile['b2b_profile']['avg_transaction_rm'] = round(avg_transaction * b2b_multiplier, 2)
        
        return profile
