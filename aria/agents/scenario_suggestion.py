"""
Scenario Suggestion Agent for ARIA.
Analyzes user questions and suggests relevant simulation scenarios.
Enhanced with real-world context from News API and DOSM economic data.
"""

from typing import Dict, Any, List
from aria.llm import LLMClient, prompts
from aria.external.news_api import NewsAPIClient
from aria.external.dosm import DOSMClient
from aria.external.malaysia_calendar import MalaysiaCalendarClient
from aria.config import NEWS_API_KEY
import logging
import json

logger = logging.getLogger(__name__)


class ScenarioSuggestionAgent:
    """Agent for suggesting simulation scenarios based on user questions."""
    
    def __init__(self):
        """Initialize Scenario Suggestion Agent."""
        self.llm_client = LLMClient()
        self.news_client = NewsAPIClient(api_key=NEWS_API_KEY) if NEWS_API_KEY else None
        self.dosm_client = DOSMClient()
        self.calendar_client = MalaysiaCalendarClient(state="pulau-pinang")
    
    async def gather_context(
        self,
        user_question: str,
        business_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Gather real-world context from News API and DOSM economic data.
        Called only when user has opted in via the real-world context toggle.
        
        Args:
            user_question: User's question or concern
            business_profile: Business profile data
        
        Returns:
            Dictionary with context from multiple sources:
                - news_articles: Relevant news articles
                - economic_indicators: DOSM economic data
                - context_summary: Brief summary of gathered context
        """
        print("=" * 60)
        print("STEP 1: GATHERING CONTEXT")
        print("=" * 60)
        
        context = {
            "news_articles": [],
            "economic_indicators": {},
            "holiday_context": "",
            "context_summary": ""
        }
        
        # Build search query from user question
        print(f"User question: '{user_question}'")
        keywords = self._build_search_query(user_question)
        print(f"âœ“ Search query: '{keywords}'")
        
        # Gather news context if News API is available
        if self.news_client and keywords:
            try:
                print(f"â†’ Searching News API with query: '{keywords}'")
                
                # Search for relevant news (English only, Malaysia)
                news_articles = await self.news_client.search_news(
                    query=keywords,
                    max_articles=5  # Top 5 most relevant
                )
                
                context["news_articles"] = news_articles[:3]  # Keep top 3
                print(f"âœ“ News API: Found {len(news_articles)} articles (using top 3)")
                
                if news_articles:
                    for i, article in enumerate(news_articles[:3], 1):
                        print(f"  {i}. {article['title'][:60]}...")
                
            except Exception as e:
                print(f"âœ— News API failed: {e}")
                print("  â†’ Continuing without news context")
        else:
            if not self.news_client:
                print("âœ— News API client not initialized (NEWS_API_KEY missing)")
            else:
                print("âœ— Could not build search query from question")
        
        # Gather DOSM economic indicators
        try:
            print("â†’ Loading DOSM economic data")
            
            # Get district from business location
            location = business_profile.get("location", "")
            district = self.dosm_client.map_location_to_district(location)
            print(f"  Mapped location '{location}' â†’ district '{district}'")
            
            # Get demographic and economic data
            demographics = await self.dosm_client.get_demographics(district)
            
            context["economic_indicators"] = {
                "district": district,
                "income_distribution": demographics.get("income_distribution", {}),
                "spending_patterns": demographics.get("spending_patterns", {}),
                "source": demographics.get("source", "DOSM")
            }
            
            print(f"âœ“ DOSM data loaded for district: {district}")
            
            # Log income distribution
            income_dist = demographics.get("income_distribution", {})
            if income_dist:
                print("  Income distribution:")
                for group, data in income_dist.items():
                    pct = data.get('percentage', 0)
                    median = data.get('median_income_rm', 0)
                    print(f"    {group}: {pct}% (median: RM{median:,})")
            
        except Exception as e:
            print(f"âœ— DOSM data loading failed: {e}")
            print("  â†’ Continuing without economic indicators")
        
        # Gather Malaysia holiday context (always available, no API key needed)
        try:
            print("â†’ Loading Malaysia holiday data (Pulau Pinang)")
            holiday_summary = await self.calendar_client.get_holiday_context_summary()
            context["holiday_context"] = holiday_summary
            print(f"âœ“ Holiday context loaded")
        except Exception as e:
            print(f"âœ— Holiday data loading failed: {e}")
            print("  â†’ Continuing without holiday context")
        
        # Generate context summary
        context["context_summary"] = self._summarize_context(
            news_articles=context["news_articles"],
            economic_indicators=context["economic_indicators"]
        )
        
        print("âœ“ Context gathering complete")
        print("=" * 60)
        
        return context
    
    def _is_holiday_relevant(self, user_question: str) -> bool:
        """
        Check if the user's question is related to holidays, school calendar,
        seasonal demand, or festive periods.
        
        Args:
            user_question: User's question text
            
        Returns:
            True if the question is holiday/calendar-related
        """
        question_lower = user_question.lower()
        
        holiday_keywords = [
            # Public holidays
            "holiday", "cuti", "hari raya", "raya", "aidilfitri", "aidiladha",
            "chinese new year", "cny", "tahun baru cina", "deepavali", "diwali",
            "thaipusam", "wesak", "vesak", "christmas", "merdeka", "national day",
            "malaysia day", "nuzul quran", "israk mikraj", "maal hijrah",
            # School-related
            "school", "sekolah", "exam", "peperiksaan", "spm", "stpm", "muet",
            "pt3", "semester", "term break", "cuti sekolah", "school holiday",
            # Seasonal / demand timing
            "festive", "season", "peak", "busy period", "long weekend",
            "demand surge", "rush", "balik kampung",
            # General calendar
            "calendar", "when", "date", "month", "weekend",
        ]
        
        return any(kw in question_lower for kw in holiday_keywords)
    
    def _build_search_query(self, user_question: str) -> str:
        """
        Build a news search query from the user's question.
        Since the user has explicitly opted in to real-world context,
        we always attempt to build a meaningful query.
        
        Args:
            user_question: User's question
        
        Returns:
            Search query string for News API
        """
        question_lower = user_question.lower()
        
        # Keyword mapping for specific economic factors
        keyword_map = {
            "fuel": "fuel price Malaysia",
            "petrol": "petrol price Malaysia",
            "gas": "fuel price Malaysia",
            "inflation": "inflation Malaysia",
            "price": "consumer price Malaysia",
            "cost": "cost of living Malaysia",
            "economy": "economy Malaysia",
            "spending": "consumer spending Malaysia",
            "wage": "minimum wage Malaysia",
            "salary": "salary Malaysia",
            "subsidy": "subsidy Malaysia",
            "tax": "tax Malaysia",
            "competition": "business competition Malaysia",
            "competitor": "business competition Malaysia",
            "tourism": "tourism Malaysia",
            "covid": "covid business Malaysia",
            "pandemic": "pandemic business Malaysia",
            "food": "food industry Malaysia",
            "retail": "retail Malaysia",
            "rent": "rental cost Malaysia",
            "supply": "supply chain Malaysia",
        }
        
        # Find matching keywords
        for key, query in keyword_map.items():
            if key in question_lower:
                return query
        
        # Fallback: use first few meaningful words + Malaysia
        words = user_question.split()
        if len(words) <= 4:
            return f"{user_question} Malaysia"
        else:
            return f"{' '.join(words[:4])} Malaysia"
    
    def _summarize_context(
        self,
        news_articles: List[Dict[str, Any]],
        economic_indicators: Dict[str, Any]
    ) -> str:
        """
        Create a brief summary of gathered context.
        
        Args:
            news_articles: List of news articles
            economic_indicators: Economic data from DOSM
        
        Returns:
            Context summary string
        """
        summary_parts = []
        
        # News summary
        if news_articles:
            summary_parts.append(f"Recent news ({len(news_articles)} articles):")
            for article in news_articles[:2]:  # Top 2
                summary_parts.append(f"  - {article['title']}")
        
        # Economic indicators summary
        if economic_indicators:
            district = economic_indicators.get("district", "")
            if district:
                summary_parts.append(f"\nEconomic data for {district}:")
                
                income_dist = economic_indicators.get("income_distribution", {})
                if income_dist:
                    b40_pct = income_dist.get("B40", {}).get("percentage", 0)
                    summary_parts.append(f"  - B40 households: {b40_pct}%")
        
        return "\n".join(summary_parts) if summary_parts else "No additional context available"
    
    async def analyze_question(
        self,
        business_profile: Dict[str, Any],
        user_question: str,
        use_external_context: bool = False,
        active_spark=None,  # Optional[SparkRecord] â€” type hint via string to avoid circular import
    ) -> Dict[str, Any]:
        """
        Analyze user's open-ended question and suggest scenarios.
        Enhanced with real-world context from News API and DOSM when enabled.
        
        Returns ONLY LLM-generated custom scenarios (no templates).
        Templates are shown in the frontend UI only.
        
        Args:
            business_profile: Business profile data
            user_question: User's question or concern
            use_external_context: Whether to gather news/economic data
        
        Returns:
            Dictionary with:
                - analysis: Understanding of user's question
                - recommended_action: Brief advice
                - scenarios: LLM-generated scenarios specific to the question
                - context: Real-world context (news + economic data) if enabled
        """
        # Use print() to ensure output appears in terminal
        print("\n" + "=" * 60)
        print("SCENARIO GENERATION WORKFLOW")
        print("=" * 60)
        print(f"Business: {business_profile.get('business_name', 'Unknown')}")
        print(f"Question: '{user_question}'")
        print(f"Real-world context: {'ENABLED' if use_external_context else 'DISABLED'}")
        print("=" * 60)
        
        # STEP 1: Gather real-world context (only if user opted in)
        if use_external_context:
            context = await self.gather_context(user_question, business_profile)
        else:
            print("\nSTEP 1: SKIPPING FULL CONTEXT (toggle off)")
            context = {
                "news_articles": [],
                "economic_indicators": {},
                "holiday_context": "",
                "context_summary": "Real-world context not requested"
            }
            # Load holiday context only if the question is relevant
            if self._is_holiday_relevant(user_question):
                print("  â†’ Holiday-related question detected, loading calendar data")
                try:
                    holiday_summary = await self.calendar_client.get_holiday_context_summary()
                    context["holiday_context"] = holiday_summary
                    print(f"  âœ“ Holiday context loaded")
                except Exception as e:
                    print(f"  âœ— Holiday data unavailable: {e}")
            else:
                print("  â†’ No holiday keywords detected, skipping calendar API")
            print("=" * 60)
        
        # STEP 2: Generate custom LLM scenarios
        print("\nSTEP 2: GENERATING CUSTOM SCENARIOS (LLM)")
        print("=" * 60)
        
        scenarios = []
        analysis = ""
        recommended_action = ""
        
        try:
            print("â†’ Building LLM prompt with context")

            # Build Spark context section (lazy import to avoid circular dependency)
            spark_section = ""
            if active_spark is not None:
                from aria.sparks.spark_templates import SPARK_TEMPLATES
                from aria.sparks.spark_context_injector import SparkContextInjector
                template = SPARK_TEMPLATES.get(active_spark.template_id)
                spark_section = SparkContextInjector.build_spark_section(active_spark, template)
            
            # Generate scenario suggestions with context
            prompt = prompts.scenario_suggestion_with_context(
                business_profile=business_profile,
                user_question=user_question,
                news_articles=context["news_articles"],
                economic_indicators=context["economic_indicators"],
                holiday_context=context.get("holiday_context", ""),
                spark_section=spark_section,
            )
            
            print(f"  Prompt length: {len(prompt)} characters")
            print("â†’ Calling Ollama LLM...")
            
            response = await self.llm_client.generate(
                prompt=prompt,
                temperature=0.7,
                max_tokens=4000
            )
            
            print(f"âœ“ LLM response received ({len(response['response'])} characters)")
            print("â†’ Parsing LLM response...")
            
            # Debug: log first/last 100 chars to help diagnose parse failures
            raw_resp = response["response"]
            print(f"  [debug] Response starts with: {repr(raw_resp[:80])}")
            print(f"  [debug] Response ends with: {repr(raw_resp[-80:])}")
            
            # Parse JSON response directly
            try:
                result = json.loads(raw_resp)
            except json.JSONDecodeError as e:
                print(f"âœ— JSON parsing failed: {e}")
                # Try to extract JSON from response if it contains extra text
                import re
                json_match = re.search(r'\{.*\}', raw_resp, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    raise ValueError(f"Could not parse JSON from LLM response: {e}")
            
            scenarios = result.get("scenarios", [])
            analysis = result.get("analysis", "")
            recommended_action = result.get("recommended_action", "")
            
            print(f"âœ“ Successfully generated {len(scenarios)} custom scenarios")
            for i, scenario in enumerate(scenarios, 1):
                print(f"  {i}. {scenario['scenario_name']} (relevance: {scenario.get('relevance_score', 'N/A')}/100)")
            
        except Exception as e:
            print(f"âœ— LLM scenario generation failed: {e}")
            import traceback
            traceback.print_exc()
            
            # Generate fallback response
            analysis = f"I understand you're asking about: '{user_question}'"
            recommended_action = "I'm having trouble generating specific scenarios right now. Please try rephrasing your question or check if Ollama is running."
        
        print("=" * 60)
        
        # STEP 3: Compile final result
        print("\nSTEP 3: COMPILING FINAL RESULT")
        print("=" * 60)
        print(f"Generated scenarios: {len(scenarios)}")
        print("=" * 60)
        print("âœ“ Scenario generation complete\n")
        
        return {
            "analysis": analysis,
            "recommended_action": recommended_action,
            "scenarios": scenarios,
            "context": context
        }
