"""
News API client for economic context gathering.

Fetches and processes news articles relevant to Malaysian economy and micro-businesses.
Uses newsdata.io to gather real-time economic news.
"""

import aiohttp
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class NewsAPIClient:
    """
    Client for newsdata.io integration.
    
    Fetches economic news to provide context for simulations:
    - Malaysian economic news (inflation, consumer spending, etc.)
    - Industry-specific news (F&B, retail, tourism)
    - Local news (Penang, Kuala Lumpur, etc.)
    """
    
    BASE_URL = "https://newsdata.io/api/1/latest"
    
    def __init__(self, api_key: str):
        """
        Initialize newsdata.io client.
        
        Args:
            api_key: newsdata.io API key
        """
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """Close aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def _make_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make request to newsdata.io API.
        
        Args:
            params: Query parameters
        
        Returns:
            API response as dictionary
        """
        session = await self._get_session()
        params['apikey'] = self.api_key
        
        try:
            async with session.get(self.BASE_URL, params=params, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('status') == 'success':
                        return data
                    else:
                        logger.error(f"newsdata.io error: {data.get('results', {}).get('message', 'Unknown error')}")
                        return {'status': 'error', 'results': []}
                else:
                    logger.error(f"newsdata.io HTTP {response.status}: {await response.text()}")
                    return {'status': 'error', 'results': []}
        
        except asyncio.TimeoutError:
            logger.error("newsdata.io request timeout")
            return {'status': 'error', 'results': []}
        except Exception as e:
            logger.error(f"newsdata.io request failed: {e}")
            return {'status': 'error', 'results': []}
    
    async def fetch_economic_news(
        self,
        country: str = "my",
        category: str = "business",
        max_articles: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent economic news for Malaysia.
        
        Args:
            country: Country code (default: 'my' for Malaysia)
            category: News category (default: 'business')
            max_articles: Maximum articles to return (default: 10)
        
        Returns:
            List of article dictionaries
        """
        params = {
            'country': country,
            'category': category,
            'language': 'en',
            'size': min(max_articles, 10),  # Free tier max is 10
        }
        
        logger.info(f"Fetching economic news for {country}, category: {category}")
        response = await self._make_request(params)
        
        articles = response.get('results', [])
        if not isinstance(articles, list):
            articles = []
        
        logger.info(f"Fetched {len(articles)} economic news articles")
        return self._process_articles(articles, category='economic')
    
    async def fetch_industry_news(
        self,
        industry: str,
        location: str = "Malaysia",
        max_articles: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Fetch industry-specific news.
        
        Args:
            industry: Industry type (e.g., 'restaurant', 'retail', 'cafe')
            location: Location filter (default: 'Malaysia')
            max_articles: Maximum articles to return (default: 10)
        
        Returns:
            List of article dictionaries
        """
        industry_keywords = self._get_industry_keywords(industry)
        query = f"{industry_keywords} {location}"
        
        params = {
            'q': query,
            'language': 'en',
            'size': min(max_articles, 10),
        }
        
        logger.info(f"Fetching industry news: {industry} in {location}")
        response = await self._make_request(params)
        
        articles = response.get('results', [])
        if not isinstance(articles, list):
            articles = []
        
        logger.info(f"Fetched {len(articles)} industry news articles")
        return self._process_articles(articles, category='industry', industry=industry)
    
    async def fetch_local_news(
        self,
        location: str = "Penang",
        max_articles: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Fetch location-specific economic news.
        
        Args:
            location: Location (e.g., 'Penang', 'Kuala Lumpur')
            max_articles: Maximum articles to return (default: 10)
        
        Returns:
            List of article dictionaries
        """
        query = f"{location} economy business"
        
        params = {
            'q': query,
            'language': 'en',
            'size': min(max_articles, 10),
        }
        
        logger.info(f"Fetching local news for {location}")
        response = await self._make_request(params)
        
        articles = response.get('results', [])
        if not isinstance(articles, list):
            articles = []
        
        logger.info(f"Fetched {len(articles)} local news articles")
        return self._process_articles(articles, category='local', location=location)
    
    async def search_news(
        self,
        query: str,
        max_articles: int = 10,
        country: str = "my",
        language: str = "en"
    ) -> List[Dict[str, Any]]:
        """
        Search for news with custom query.
        
        Args:
            query: Search query
            max_articles: Maximum articles to return (default: 10)
            country: Country code (default: 'my' for Malaysia)
            language: Language code (default: 'en' for English)
        
        Returns:
            List of article dictionaries
        """
        params = {
            'q': query,
            'country': country,
            'language': language,
            'size': min(max_articles, 10),
        }
        
        logger.info(f"Searching news: {query}")
        
        try:
            response = await self._make_request(params)
            articles = response.get('results', [])
            if not isinstance(articles, list):
                articles = []
            
            logger.info(f"Found {len(articles)} articles")
            return self._process_articles(articles, category='custom')
        finally:
            await self.close()
    
    def _get_industry_keywords(self, industry: str) -> str:
        """Get search keywords for industry."""
        keywords_map = {
            'restaurant': 'restaurant food dining',
            'mamak': 'mamak restaurant food',
            'cafe': 'cafe coffee shop',
            'retail': 'retail shop store',
            'tourism': 'tourism hotel travel',
            'grocery': 'grocery supermarket',
            'bakery': 'bakery pastry',
            'salon': 'salon beauty hair',
        }
        return keywords_map.get(industry.lower(), industry)
    
    def _process_articles(
        self,
        articles: List[Dict[str, Any]],
        category: str,
        industry: Optional[str] = None,
        location: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Process and standardize article data from newsdata.io format.
        
        Args:
            articles: Raw articles from API
            category: Article category
            industry: Industry (optional)
            location: Location (optional)
        
        Returns:
            Processed articles
        """
        processed = []
        
        for article in articles:
            if not article.get('title'):
                continue
            
            processed_article = {
                'source': article.get('source_name', article.get('source_id', 'Unknown')),
                'title': article.get('title', ''),
                'description': article.get('description', ''),
                'content': article.get('content', ''),
                'url': article.get('link', ''),
                'published_at': article.get('pubDate', ''),
                'category': category,
                'industry': industry,
                'location': location,
                'image_url': article.get('image_url'),
                'author': ', '.join(article.get('creator', []) or []),
            }
            
            processed.append(processed_article)
        
        return processed
    
    async def health_check(self) -> bool:
        """
        Check if newsdata.io API is accessible.
        
        Returns:
            True if API is accessible, False otherwise
        """
        try:
            params = {
                'q': 'Malaysia',
                'size': 1,
                'language': 'en',
            }
            response = await self._make_request(params)
            return response.get('status') == 'success'
        except Exception as e:
            logger.error(f"newsdata.io health check failed: {e}")
            return False
