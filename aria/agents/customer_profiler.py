"""
Customer Profile Inference Agent

Uses LLM to automatically infer customer profiles based on business information,
with smart follow-up questions and user confirmation/correction flow.
"""

import json
from typing import Dict, List, Optional, Any
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
            print(f"   ⚠ LLM returned empty response, using default profile")
            return self._get_default_profile(business_info)
        
        # Debug: Show first 200 chars of response
        # print(f"   [DEBUG] LLM response preview: {response_text[:200]}...")
        
        # Parse JSON response
        try:
            profile = json.loads(response_text)
            
            # Calculate avg_transaction_rm based on price_range and items_per_transaction
            profile = self._calculate_avg_transaction(profile)
            
            return profile
        except json.JSONDecodeError as e:
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
                    print(f"   ⚠ Failed to extract JSON: {parse_error}")
                    print(f"   ⚠ LLM response was malformed, using default profile")
            
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
    
    async def ask_clarifying_questions(
        self, 
        profile: Dict[str, Any],
        business_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Ask targeted clarifying questions when profile needs refinement.
        
        Args:
            profile: Initial inferred profile
            business_info: Original business information
        
        Returns:
            Updated profile with clarifications
        """
        clarifications = {}
        
        # Question 1: Customer type if ambiguous
        if profile['customer_type'] == 'Both':
            print(f"\n   We're analyzing your business profile...")
            print(f"\n   Your business type suggests you might serve:")
            print(f"   - Individual customers (B2C), OR")
            print(f"   - Other businesses (B2B), OR")
            print(f"   - Both individuals and businesses")
            print(f"\n   Which best describes your PRIMARY customers?")
            print(f"      1. Individual consumers (B2C)")
            print(f"      2. Other businesses (B2B)")
            print(f"      3. Both (mixed)")
            
            while True:
                choice = input(f"   > ").strip()
                if choice == '1':
                    clarifications['customer_type'] = 'B2C'
                    break
                elif choice == '2':
                    clarifications['customer_type'] = 'B2B'
                    break
                elif choice == '3':
                    clarifications['customer_type'] = 'Both'
                    break
                else:
                    print(f"   ⚠ Please enter 1, 2, or 3")
        
        # Question 2: B2B target businesses if unclear
        if clarifications.get('customer_type', profile['customer_type']) in ['B2B', 'Both']:
            if (profile.get('b2b_profile') and 
                'Unknown' in str(profile['b2b_profile'].get('target_business_types', []))):
                print(f"\n   What types of businesses are your main customers?")
                print(f"   (e.g., 'Restaurants', 'Retail shops', 'Construction companies')")
                target_businesses = input(f"   > ").strip()
                if target_businesses:
                    clarifications['target_business_types'] = [
                        b.strip() for b in target_businesses.split(',')
                    ]
        
        # If we have clarifications, refine the profile with LLM
        if clarifications:
            refined_profile = await self._refine_profile_with_clarifications(
                profile, business_info, clarifications
            )
            return refined_profile
        
        return profile
    
    async def _refine_profile_with_clarifications(
        self,
        profile: Dict[str, Any],
        business_info: Dict[str, Any],
        clarifications: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Manually apply user clarifications to the profile.
        Skips LLM refinement to avoid JSON parsing issues.
        """
        # Apply customer type clarification
        if 'customer_type' in clarifications:
            profile['customer_type'] = clarifications['customer_type']
            
            # Adjust profiles based on customer type
            if clarifications['customer_type'] == 'B2B':
                # B2B business - remove B2C profile, ensure B2B profile exists
                profile['b2c_profile'] = None
                if not profile.get('b2b_profile'):
                    profile['b2b_profile'] = {
                        "target_business_types": ["Businesses"],
                        "business_size": ["Micro", "Small", "Medium"],
                        "purchase_frequency": "weekly",
                        "avg_transaction_rm": 500,
                        "price_sensitivity": "medium"
                    }
            elif clarifications['customer_type'] == 'B2C':
                # B2C business - remove B2B profile, ensure B2C profile exists
                profile['b2b_profile'] = None
                if not profile.get('b2c_profile'):
                    profile['b2c_profile'] = {
                        "typical_age_groups": ["25-34", "35-44", "45-54"],
                        "typical_income_levels": ["B40", "M40"],
                        "purchase_frequency": "weekly",
                        "avg_transaction_rm": 50,
                        "price_sensitivity": "medium"
                    }
        
        # Apply target business types for B2B
        if 'target_business_types' in clarifications:
            if not profile.get('b2b_profile'):
                profile['b2b_profile'] = {
                    "target_business_types": clarifications['target_business_types'],
                    "business_size": ["Micro", "Small", "Medium"],
                    "purchase_frequency": "weekly",
                    "avg_transaction_rm": 500,
                    "price_sensitivity": "medium"
                }
            else:
                profile['b2b_profile']['target_business_types'] = clarifications['target_business_types']
        
        # Apply purchase frequency
        if 'purchase_frequency' in clarifications:
            if profile.get('b2c_profile'):
                profile['b2c_profile']['purchase_frequency'] = clarifications['purchase_frequency']
            if profile.get('b2b_profile'):
                profile['b2b_profile']['purchase_frequency'] = clarifications['purchase_frequency']
        
        # Update target_customers based on customer type
        if profile['customer_type'] == 'B2B':
            target_types = profile.get('b2b_profile', {}).get('target_business_types', ['businesses'])
            profile['target_customers'] = ', '.join(target_types[:3])
        elif profile['customer_type'] == 'B2C':
            segments = profile.get('b2c_profile', {}).get('target_segments', ['individual consumers'])
            profile['target_customers'] = ', '.join(segments[:3])
        
        profile['reasoning'] = "Profile refined based on user clarifications"
        
        return profile
    
    def display_profile(self, profile: Dict[str, Any]) -> None:
        """
        Display the inferred customer profile in a formatted way.
        """
        from scripts.test_simulation import Colors
        
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'Customer Profile Analysis'.center(70)}{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.ENDC}\n")
        
        print(f"{Colors.CYAN}Based on your business information, we identified your typical customers:{Colors.ENDC}\n")
        
        # Customer type
        print(f"   {Colors.BOLD}Customer Type:{Colors.ENDC} {profile['customer_type']}")
        if profile['customer_type'] == 'B2C':
            print(f"   (Business to Consumer - Individual customers)")
        elif profile['customer_type'] == 'B2B':
            print(f"   (Business to Business - Other businesses)")
        else:
            print(f"   (Mixed - Both individuals and businesses)")
        
        # Description
        print(f"\n   {Colors.BOLD}Primary Customers:{Colors.ENDC}")
        print(f"   {profile.get('target_customers', '')}")
        
        # B2C Profile
        if profile.get('b2c_profile'):
            b2c = profile['b2c_profile']
            print(f"\n   {Colors.BOLD}Consumer Profile (B2C):{Colors.ENDC}")
            print(f"   • Age Groups: {', '.join(b2c['typical_age_groups'])}")
            print(f"   • Income Levels: {', '.join(b2c['typical_income_levels'])}")
            print(f"   • Purchase Frequency: {b2c['purchase_frequency'].capitalize()}")
            print(f"   • Average Transaction: RM{b2c['avg_transaction_rm']}")
            print(f"   • Price Sensitivity: {b2c['price_sensitivity'].capitalize()}")
        
        # B2B Profile
        if profile.get('b2b_profile'):
            b2b = profile['b2b_profile']
            print(f"\n   {Colors.BOLD}Business Profile (B2B):{Colors.ENDC}")
            print(f"   • Target Businesses: {', '.join(b2b['target_business_types'])}")
            print(f"   • Business Size: {', '.join(b2b['business_size'])}")
            print(f"   • Purchase Frequency: {b2b['purchase_frequency'].capitalize()}")
            print(f"   • Average Transaction: RM{b2b['avg_transaction_rm']}")
            print(f"   • Price Sensitivity: {b2b['price_sensitivity'].capitalize()}")
        
        # Reasoning
        print(f"\n   {Colors.BOLD}Analysis:{Colors.ENDC}")
        print(f"   {profile['reasoning']}")
        
        print(f"\n{Colors.CYAN}{'-' * 70}{Colors.ENDC}\n")
    
    async def confirm_with_user(self, profile: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
        """
        Show profile to user and get confirmation or corrections.
        
        Returns:
            Tuple of (final_profile, user_confirmed)
        """
        from scripts.test_simulation import Colors
        
        self.display_profile(profile)
        
        print(f"{Colors.CYAN}Is this customer profile accurate? (Y/N){Colors.ENDC}")
        response = input(f"{Colors.BOLD}> {Colors.ENDC}").strip().upper()
        
        if response == 'Y':
            return profile, True
        
        # User wants to make corrections
        return await self._handle_corrections(profile)
    
    async def _handle_corrections(self, profile: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
        """
        Handle user corrections to the profile.
        """
        from scripts.test_simulation import Colors
        
        corrections_made = []
        
        while True:
            print(f"\n{Colors.CYAN}What would you like to correct?{Colors.ENDC}")
            print(f"   1. Customer type (B2C/B2B/Both)")
            print(f"   2. Customer description")
            print(f"   3. Purchase frequency")
            print(f"   4. Average transaction size")
            print(f"   5. Price sensitivity")
            print(f"   6. Accept current profile")
            print(f"   0. Start over with manual entry")
            
            choice = input(f"{Colors.BOLD}> {Colors.ENDC}").strip()
            
            if choice == '1':
                print(f"\n   Select customer type:")
                print(f"      1. B2C (Individual consumers)")
                print(f"      2. B2B (Other businesses)")
                print(f"      3. Both")
                type_choice = input(f"   > ").strip()
                if type_choice == '1':
                    profile['customer_type'] = 'B2C'
                elif type_choice == '2':
                    profile['customer_type'] = 'B2B'
                elif type_choice == '3':
                    profile['customer_type'] = 'Both'
                corrections_made.append('customer_type')
                print(f"   {Colors.GREEN}✓{Colors.ENDC} Updated customer type")
            
            elif choice == '2':
                print(f"\n   Enter target customers (comma-separated):")
                new_desc = input(f"   > ").strip()
                if new_desc:
                    profile['target_customers'] = new_desc
                    corrections_made.append('target_customers')
                    print(f"   {Colors.GREEN}✓{Colors.ENDC} Updated target customers")
            
            elif choice == '3':
                print(f"\n   Select purchase frequency:")
                print(f"      1. Daily")
                print(f"      2. Weekly")
                print(f"      3. Monthly")
                print(f"      4. Quarterly")
                freq_choice = input(f"   > ").strip()
                freq_map = {'1': 'daily', '2': 'weekly', '3': 'monthly', '4': 'quarterly'}
                if freq_choice in freq_map:
                    new_freq = freq_map[freq_choice]
                    if profile.get('b2c_profile'):
                        profile['b2c_profile']['purchase_frequency'] = new_freq
                    if profile.get('b2b_profile'):
                        profile['b2b_profile']['purchase_frequency'] = new_freq
                    corrections_made.append('purchase_frequency')
                    print(f"   {Colors.GREEN}✓{Colors.ENDC} Updated purchase frequency")
            
            elif choice == '4':
                print(f"\n   Enter average transaction amount (RM):")
                try:
                    amount = float(input(f"   > ").strip())
                    if profile.get('b2c_profile'):
                        profile['b2c_profile']['avg_transaction_rm'] = amount
                    if profile.get('b2b_profile'):
                        profile['b2b_profile']['avg_transaction_rm'] = amount
                    corrections_made.append('avg_transaction')
                    print(f"   {Colors.GREEN}✓{Colors.ENDC} Updated transaction amount")
                except ValueError:
                    print(f"   {Colors.YELLOW}⚠{Colors.ENDC} Invalid amount")
            
            elif choice == '5':
                print(f"\n   Select price sensitivity:")
                print(f"      1. Low (not price-sensitive)")
                print(f"      2. Medium")
                print(f"      3. High (very price-sensitive)")
                sens_choice = input(f"   > ").strip()
                sens_map = {'1': 'low', '2': 'medium', '3': 'high'}
                if sens_choice in sens_map:
                    new_sens = sens_map[sens_choice]
                    if profile.get('b2c_profile'):
                        profile['b2c_profile']['price_sensitivity'] = new_sens
                    if profile.get('b2b_profile'):
                        profile['b2b_profile']['price_sensitivity'] = new_sens
                    corrections_made.append('price_sensitivity')
                    print(f"   {Colors.GREEN}✓{Colors.ENDC} Updated price sensitivity")
            
            elif choice == '6':
                # Show final profile and confirm
                self.display_profile(profile)
                print(f"{Colors.CYAN}Accept this profile? (Y/N){Colors.ENDC}")
                confirm = input(f"{Colors.BOLD}> {Colors.ENDC}").strip().upper()
                if confirm == 'Y':
                    profile['user_corrections'] = corrections_made
                    return profile, True
                # Otherwise loop back to corrections
            
            elif choice == '0':
                return profile, False  # Signal to use manual entry
            
            else:
                print(f"   {Colors.YELLOW}⚠{Colors.ENDC} Invalid choice")

    async def collect_b2b_details(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Collect additional B2B-specific information for simulation.
        
        Args:
            profile: The B2B customer profile
            
        Returns:
            Enhanced profile with B2B simulation data
        """
        from scripts.test_simulation import Colors
        
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'B2B Customer Details Collection'.center(70)}{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.ENDC}\n")
        
        print(f"{Colors.CYAN}To simulate B2B customer behavior, we need additional information:{Colors.ENDC}\n")
        
        b2b_details = {}
        
        # 1. Number of active business customers
        print(f"{Colors.BOLD}1. How many active business customers do you currently have?{Colors.ENDC}")
        print(f"   (This helps us create a realistic simulation size)")
        while True:
            try:
                count_input = input(f"   > ").strip()
                count = int(count_input)
                if count > 0:
                    b2b_details['active_customers'] = count
                    print(f"   {Colors.GREEN}✓{Colors.ENDC} {count} active business customers")
                    break
                else:
                    print(f"   {Colors.YELLOW}⚠{Colors.ENDC} Please enter a positive number")
            except ValueError:
                print(f"   {Colors.YELLOW}⚠{Colors.ENDC} Please enter a valid number")
        
        # 2. Customer segments
        print(f"\n{Colors.BOLD}2. What are your main customer segments?{Colors.ENDC}")
        print(f"   (e.g., 'Small workshops', 'Medium repair shops', 'Large dealerships')")
        print(f"   Enter segments separated by commas:")
        segments_input = input(f"   > ").strip()
        if segments_input:
            segments = [s.strip() for s in segments_input.split(',')]
            b2b_details['customer_segments'] = segments
            print(f"   {Colors.GREEN}✓{Colors.ENDC} Segments: {', '.join(segments)}")
        else:
            b2b_details['customer_segments'] = profile.get('b2b_profile', {}).get('target_business_types', ['Businesses'])
        
        # 3. Decision-making process
        print(f"\n{Colors.BOLD}3. How do your business customers typically make purchase decisions?{Colors.ENDC}")
        print(f"   1. Single decision-maker (owner/manager)")
        print(f"   2. Small team (2-3 people)")
        print(f"   3. Committee/multiple stakeholders")
        while True:
            choice = input(f"   > ").strip()
            if choice == '1':
                b2b_details['decision_process'] = 'single'
                b2b_details['decision_makers'] = 1
                print(f"   {Colors.GREEN}✓{Colors.ENDC} Single decision-maker")
                break
            elif choice == '2':
                b2b_details['decision_process'] = 'small_team'
                b2b_details['decision_makers'] = 2
                print(f"   {Colors.GREEN}✓{Colors.ENDC} Small team decision")
                break
            elif choice == '3':
                b2b_details['decision_process'] = 'committee'
                b2b_details['decision_makers'] = 3
                print(f"   {Colors.GREEN}✓{Colors.ENDC} Committee decision")
                break
            else:
                print(f"   {Colors.YELLOW}⚠{Colors.ENDC} Please enter 1, 2, or 3")
        
        # 4. Relationship duration
        print(f"\n{Colors.BOLD}4. What is the typical relationship duration with your customers?{Colors.ENDC}")
        print(f"   1. Short-term (< 6 months)")
        print(f"   2. Medium-term (6 months - 2 years)")
        print(f"   3. Long-term (> 2 years)")
        while True:
            choice = input(f"   > ").strip()
            if choice == '1':
                b2b_details['relationship_duration'] = 'short'
                b2b_details['avg_relationship_months'] = 3
                print(f"   {Colors.GREEN}✓{Colors.ENDC} Short-term relationships")
                break
            elif choice == '2':
                b2b_details['relationship_duration'] = 'medium'
                b2b_details['avg_relationship_months'] = 12
                print(f"   {Colors.GREEN}✓{Colors.ENDC} Medium-term relationships")
                break
            elif choice == '3':
                b2b_details['relationship_duration'] = 'long'
                b2b_details['avg_relationship_months'] = 36
                print(f"   {Colors.GREEN}✓{Colors.ENDC} Long-term relationships")
                break
            else:
                print(f"   {Colors.YELLOW}⚠{Colors.ENDC} Please enter 1, 2, or 3")
        
        # 5. Contract/Agreement type
        print(f"\n{Colors.BOLD}5. How do you typically work with business customers?{Colors.ENDC}")
        print(f"   1. Spot purchases (no contract)")
        print(f"   2. Informal agreements")
        print(f"   3. Formal contracts")
        while True:
            choice = input(f"   > ").strip()
            if choice == '1':
                b2b_details['contract_type'] = 'spot'
                print(f"   {Colors.GREEN}✓{Colors.ENDC} Spot purchases")
                break
            elif choice == '2':
                b2b_details['contract_type'] = 'informal'
                print(f"   {Colors.GREEN}✓{Colors.ENDC} Informal agreements")
                break
            elif choice == '3':
                b2b_details['contract_type'] = 'formal'
                print(f"   {Colors.GREEN}✓{Colors.ENDC} Formal contracts")
                break
            else:
                print(f"   {Colors.YELLOW}⚠{Colors.ENDC} Please enter 1, 2, or 3")
        
        # 6. Payment terms
        print(f"\n{Colors.BOLD}6. What are your typical payment terms?{Colors.ENDC}")
        print(f"   1. Cash on delivery (COD)")
        print(f"   2. Net 7-15 days")
        print(f"   3. Net 30 days")
        print(f"   4. Net 60+ days")
        while True:
            choice = input(f"   > ").strip()
            if choice == '1':
                b2b_details['payment_terms'] = 'cod'
                b2b_details['payment_days'] = 0
                print(f"   {Colors.GREEN}✓{Colors.ENDC} Cash on delivery")
                break
            elif choice == '2':
                b2b_details['payment_terms'] = 'net_15'
                b2b_details['payment_days'] = 15
                print(f"   {Colors.GREEN}✓{Colors.ENDC} Net 7-15 days")
                break
            elif choice == '3':
                b2b_details['payment_terms'] = 'net_30'
                b2b_details['payment_days'] = 30
                print(f"   {Colors.GREEN}✓{Colors.ENDC} Net 30 days")
                break
            elif choice == '4':
                b2b_details['payment_terms'] = 'net_60'
                b2b_details['payment_days'] = 60
                print(f"   {Colors.GREEN}✓{Colors.ENDC} Net 60+ days")
                break
            else:
                print(f"   {Colors.YELLOW}⚠{Colors.ENDC} Please enter 1, 2, 3, or 4")
        
        # 7. Key decision factors
        print(f"\n{Colors.BOLD}7. What are the TOP 3 factors your customers consider when choosing you?{Colors.ENDC}")
        print(f"   (Select 3 numbers, separated by commas)")
        print(f"   1. Price/Cost")
        print(f"   2. Product Quality")
        print(f"   3. Delivery Speed")
        print(f"   4. Reliability/Consistency")
        print(f"   5. Technical Support")
        print(f"   6. Product Range/Variety")
        print(f"   7. Payment Terms")
        print(f"   8. Relationship/Trust")
        
        factor_map = {
            '1': 'price', '2': 'quality', '3': 'delivery_speed',
            '4': 'reliability', '5': 'technical_support', '6': 'product_range',
            '7': 'payment_terms', '8': 'relationship'
        }
        
        while True:
            choices = input(f"   > ").strip().split(',')
            choices = [c.strip() for c in choices]
            if len(choices) == 3 and all(c in factor_map for c in choices):
                b2b_details['decision_factors'] = [factor_map[c] for c in choices]
                factor_names = [factor_map[c].replace('_', ' ').title() for c in choices]
                print(f"   {Colors.GREEN}✓{Colors.ENDC} Key factors: {', '.join(factor_names)}")
                break
            else:
                print(f"   {Colors.YELLOW}⚠{Colors.ENDC} Please select exactly 3 numbers from 1-8, separated by commas")
        
        # 8. Churn risk factors
        print(f"\n{Colors.BOLD}8. What would most likely cause a customer to switch to a competitor?{Colors.ENDC}")
        print(f"   1. Better pricing elsewhere")
        print(f"   2. Quality issues")
        print(f"   3. Delivery delays")
        print(f"   4. Poor service")
        print(f"   5. Limited product availability")
        
        churn_map = {
            '1': 'price_competition',
            '2': 'quality_issues',
            '3': 'delivery_delays',
            '4': 'poor_service',
            '5': 'product_availability'
        }
        
        while True:
            choice = input(f"   > ").strip()
            if choice in churn_map:
                b2b_details['primary_churn_risk'] = churn_map[choice]
                print(f"   {Colors.GREEN}✓{Colors.ENDC} Primary churn risk: {churn_map[choice].replace('_', ' ').title()}")
                break
            else:
                print(f"   {Colors.YELLOW}⚠{Colors.ENDC} Please enter 1, 2, 3, 4, or 5")
        
        # 9. Seasonal patterns
        print(f"\n{Colors.BOLD}9. Does your business have seasonal demand patterns?{Colors.ENDC}")
        print(f"   1. No, demand is consistent year-round")
        print(f"   2. Yes, moderate seasonal variation")
        print(f"   3. Yes, strong seasonal peaks")
        
        while True:
            choice = input(f"   > ").strip()
            if choice == '1':
                b2b_details['seasonality'] = 'none'
                b2b_details['seasonal_factor'] = 1.0
                print(f"   {Colors.GREEN}✓{Colors.ENDC} Consistent demand")
                break
            elif choice == '2':
                b2b_details['seasonality'] = 'moderate'
                b2b_details['seasonal_factor'] = 1.3
                print(f"   {Colors.GREEN}✓{Colors.ENDC} Moderate seasonality")
                break
            elif choice == '3':
                b2b_details['seasonality'] = 'strong'
                b2b_details['seasonal_factor'] = 2.0
                print(f"   {Colors.GREEN}✓{Colors.ENDC} Strong seasonality")
                break
            else:
                print(f"   {Colors.YELLOW}⚠{Colors.ENDC} Please enter 1, 2, or 3")
        
        # Add B2B details to profile
        if 'b2b_profile' not in profile:
            profile['b2b_profile'] = {}
        
        profile['b2b_profile']['simulation_data'] = b2b_details
        
        # Display summary
        print(f"\n{Colors.BOLD}{Colors.GREEN}{'=' * 70}{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.GREEN}{'B2B Profile Complete'.center(70)}{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.GREEN}{'=' * 70}{Colors.ENDC}\n")
        
        print(f"{Colors.CYAN}Summary:{Colors.ENDC}")
        print(f"   • Active Customers: {b2b_details['active_customers']}")
        print(f"   • Segments: {', '.join(b2b_details['customer_segments'])}")
        print(f"   • Decision Process: {b2b_details['decision_process'].replace('_', ' ').title()}")
        print(f"   • Relationship Duration: {b2b_details['relationship_duration'].title()}-term")
        print(f"   • Contract Type: {b2b_details['contract_type'].title()}")
        print(f"   • Payment Terms: {b2b_details['payment_terms'].upper()}")
        print(f"   • Key Factors: {', '.join([f.replace('_', ' ').title() for f in b2b_details['decision_factors']])}")
        print(f"   • Churn Risk: {b2b_details['primary_churn_risk'].replace('_', ' ').title()}")
        print(f"   • Seasonality: {b2b_details['seasonality'].title()}")
        print()
        
        return profile
