"""
Google Docs Integration Service for DTCE Knowledge Base
Fetches and processes content from Google Docs for RAG integration
"""

import requests
import re
from typing import Optional, Dict, Any
import structlog
from urllib.parse import urlparse, parse_qs

logger = structlog.get_logger(__name__)

class GoogleDocsService:
    """Service to fetch and process Google Docs content for RAG integration."""
    
    def __init__(self):
        self.session = requests.Session()
        # Set user agent to avoid some blocking
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def extract_doc_id(self, url: str) -> Optional[str]:
        """Extract Google Doc ID from various URL formats."""
        # Handle different Google Docs URL formats
        patterns = [
            r'/document/d/([a-zA-Z0-9-_]+)',
            r'id=([a-zA-Z0-9-_]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def get_public_content(self, doc_url: str) -> Optional[str]:
        """Fetch content from a public Google Doc using multiple methods."""
        doc_id = self.extract_doc_id(doc_url)
        if not doc_id:
            logger.error("Could not extract document ID from URL", url=doc_url)
            return None
        
        # Try multiple approaches to access the document
        methods = [
            f"https://docs.google.com/document/d/{doc_id}/export?format=txt",
            f"https://docs.google.com/document/d/{doc_id}/pub",
            f"https://docs.google.com/document/d/{doc_id}/export?format=html",
            f"https://docs.google.com/document/u/0/d/{doc_id}/export?format=txt",
        ]
        
        for method_url in methods:
            try:
                logger.info("Attempting to fetch Google Doc", method=method_url)
                response = self.session.get(method_url, timeout=30)
                
                if response.status_code == 200:
                    content = response.text.strip()
                    
                    # Check if we got actual content (not a sign-in page)
                    if self._is_valid_content(content):
                        logger.info("Successfully fetched Google Doc content", 
                                  method=method_url, 
                                  content_length=len(content))
                        return self._clean_content(content)
                    else:
                        logger.warning("Got sign-in page or invalid content", method=method_url)
                        
                elif response.status_code == 403:
                    logger.warning("Access forbidden - document may not be public", method=method_url)
                else:
                    logger.warning("Failed to fetch document", 
                                 method=method_url, 
                                 status=response.status_code)
                    
            except Exception as e:
                logger.error("Exception fetching Google Doc", method=method_url, error=str(e))
                continue
        
        return None
    
    def _is_valid_content(self, content: str) -> bool:
        """Check if the fetched content is valid (not a sign-in page)."""
        # Check for common sign-in page indicators
        signin_indicators = [
            "Sign in to continue",
            "Sign in to Google",
            "accounts.google.com",
            "ServiceLogin",
            "Enter your email",
            "<!DOCTYPE html>"  # If we get HTML when expecting text
        ]
        
        content_lower = content.lower()
        for indicator in signin_indicators:
            if indicator.lower() in content_lower:
                return False
        
        # Check if content is too short (likely an error page)
        if len(content.strip()) < 50:
            return False
            
        return True
    
    def _clean_content(self, content: str) -> str:
        """Clean and format the content for RAG processing."""
        # Remove excessive whitespace
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        content = re.sub(r' +', ' ', content)
        
        # Remove common Google Docs artifacts
        content = re.sub(r'Page \d+ of \d+', '', content)
        content = re.sub(r'https://docs\.google\.com[^\s]*', '', content)
        
        return content.strip()
    
    def get_knowledge_base_content(self, doc_url: str) -> Dict[str, Any]:
        """Get formatted knowledge base content for RAG integration."""
        content = self.get_public_content(doc_url)
        
        if not content:
            return {
                "success": False,
                "error": "Could not access Google Doc content",
                "content": None
            }
        
        # Structure the content for RAG
        return {
            "success": True,
            "content": content,
            "source": "DTCE Knowledge Base (Google Doc)",
            "doc_url": doc_url,
            "content_length": len(content),
            "processed_at": "2025-09-15"
        }
