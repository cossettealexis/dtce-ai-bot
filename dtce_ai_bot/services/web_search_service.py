"""
Web search service for external engineering resources and forum discussions.
"""

import asyncio
import aiohttp
import re
from typing import List, Dict, Optional
import structlog
from bs4 import BeautifulSoup
from urllib.parse import urlencode

logger = structlog.get_logger(__name__)

class WebSearchService:
    """Service for searching external web resources for engineering discussions and references."""
    
    def __init__(self):
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def search_engineering_forums(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search engineering forums and discussion boards."""
        results = []
        
        # Define engineering-focused search targets
        forum_sites = [
            "site:reddit.com/r/StructuralEngineering",
            "site:reddit.com/r/engineering", 
            "site:eng.stackexchange.com",
            "site:structuremag.org",
            "site:civilax.com",
            "site:tekla.com/discussion",
            "site:linkedin.com/pulse"
        ]
        
        try:
            for site in forum_sites[:3]:  # Limit to avoid rate limiting
                site_results = await self._search_google_site(f"{query} {site}", max_results=3)
                results.extend(site_results)
                
                if len(results) >= max_results:
                    break
                    
        except Exception as e:
            logger.error("Forum search failed", error=str(e))
            
        return results[:max_results]
    
    async def search_nz_engineering_resources(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search New Zealand specific engineering resources."""
        results = []
        
        # NZ-specific engineering sites
        nz_sites = [
            "site:sesoc.org.nz",
            "site:ipenz.org.nz", 
            "site:engineering.org.nz",
            "site:standards.govt.nz",
            "site:building.govt.nz",
            "site:eq-assess.org.nz"
        ]
        
        try:
            for site in nz_sites:
                site_results = await self._search_google_site(f"{query} {site}", max_results=2)
                results.extend(site_results)
                
                if len(results) >= max_results:
                    break
                    
        except Exception as e:
            logger.error("NZ resource search failed", error=str(e))
            
        return results[:max_results]
    
    async def search_technical_publications(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search technical publications and guidelines."""
        results = []
        
        # Technical publication sites
        tech_sites = [
            "site:aisc.org",
            "site:concrete.org", 
            "site:asce.org",
            "site:istructe.org",
            "site:steelconstruction.org",
            "site:ccanz.org.nz",
            "site:nzcs.org.nz"
        ]
        
        try:
            for site in tech_sites[:4]:  # Limit to avoid rate limiting
                site_results = await self._search_google_site(f"{query} {site}", max_results=2)
                results.extend(site_results)
                
                if len(results) >= max_results:
                    break
                    
        except Exception as e:
            logger.error("Technical publication search failed", error=str(e))
            
        return results[:max_results]
    
    async def _search_google_site(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search Google for site-specific results."""
        # Note: In production, you would use Google Custom Search API
        # This is a simplified example that would need proper API integration
        
        results = []
        
        # For demo purposes, return mock results that show the structure
        # In production, replace with actual Google Custom Search API calls
        
        mock_results = [
            {
                "title": f"Forum Discussion: {query.replace('site:', '').split()[0]}",
                "url": f"https://example.com/forum/discussion-{hash(query) % 1000}",
                "snippet": f"Engineering discussion about {query.split()[0]} with practical insights from professionals.",
                "source": "Engineering Forum",
                "relevance_score": 0.9
            }
        ]
        
        return mock_results[:max_results]
    
    def _extract_keywords_for_web_search(self, query: str) -> List[str]:
        """Extract search-optimized keywords from the query."""
        # Remove common stopwords and focus on technical terms
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'please', 'provide', 'look', 'find'}
        
        words = re.findall(r'\b\w+\b', query.lower())
        keywords = [word for word in words if word not in stopwords and len(word) > 2]
        
        return keywords
    
    async def comprehensive_search(self, query: str, search_type: str = "all") -> Dict[str, List[Dict]]:
        """Perform comprehensive search across different resource types."""
        results = {
            "forums": [],
            "nz_resources": [], 
            "technical_publications": [],
            "general_web": []
        }
        
        try:
            if search_type in ["all", "forums"]:
                results["forums"] = await self.search_engineering_forums(query, max_results=5)
                
            if search_type in ["all", "nz"]:
                results["nz_resources"] = await self.search_nz_engineering_resources(query, max_results=5)
                
            if search_type in ["all", "technical"]:
                results["technical_publications"] = await self.search_technical_publications(query, max_results=5)
                
        except Exception as e:
            logger.error("Comprehensive search failed", error=str(e), query=query)
            
        return results
