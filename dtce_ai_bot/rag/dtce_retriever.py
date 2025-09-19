"""
Adapted RAG Retriever for Existing DTCE Index

This retriever works with your existing Azure Search index schema.
"""

from typing import List, Dict, Any, Optional
import logging
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

from dtce_ai_bot.rag.config import RAGConfig

logger = logging.getLogger(__name__)


class SearchResult:
    """Represents a search result with relevance score"""
    
    def __init__(self, content: str, metadata: Dict[str, Any], score: float, source: str = "unknown"):
        self.content = content
        self.metadata = metadata
        self.score = score
        self.source = source  # "keyword" or "semantic"
        
    def __repr__(self):
        return f"SearchResult(score={self.score:.3f}, source={self.source})"


class DTCERetriever:
    """
    Retriever adapted for DTCE's existing Azure Search index
    
    Works with your existing schema:
    - id, filename, content, folder, project_name, etc.
    """
    
    def __init__(self, config: RAGConfig):
        self.config = config
        
        # Initialize Azure Search client
        credential = AzureKeyCredential(config.azure.search_admin_key)
        self.search_client = SearchClient(
            endpoint=config.azure.search_endpoint,
            index_name=config.azure.search_index_name,
            credential=credential
        )
        
    def retrieve(self, query: str, top_k: Optional[int] = None, 
                filters: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """
        Search your existing DTCE index
        
        Args:
            query: Search query
            top_k: Number of results to return
            filters: Optional filters (project_name, folder, content_type)
            
        Returns:
            List of search results from your index
        """
        top_k = top_k or self.config.retrieval.top_k
        
        try:
            # Build filter string for your schema
            filter_string = self._build_filters(filters)
            
            # Search your existing index
            results = self.search_client.search(
                search_text=query,
                filter=filter_string,
                select=["id", "filename", "content", "folder", "project_name", "year", "content_type"],
                top=top_k,
                search_mode="any"  # Match any terms
            )
            
            search_results = []
            for result in results:
                # Adapt your index data to SearchResult format
                content = result.get("content", "")
                
                # Skip non-text content (images, etc.)
                if not content or len(content.strip()) < 50:
                    continue
                
                # Clean content - remove binary data markers
                if content.startswith("ÿØÿà") or "JFIF" in content[:100]:
                    continue  # Skip image files
                
                metadata = {
                    "document_id": result.get("id", ""),
                    "filename": result.get("filename", ""),
                    "folder": result.get("folder", ""),
                    "project_name": result.get("project_name", ""),
                    "year": result.get("year"),
                    "content_type": result.get("content_type", "")
                }
                
                search_result = SearchResult(
                    content=content,
                    metadata=metadata,
                    score=result.get("@search.score", 0.0),
                    source="keyword"
                )
                search_results.append(search_result)
                
            return search_results
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    def _build_filters(self, filters: Optional[Dict[str, Any]]) -> Optional[str]:
        """Build filter string for your index schema"""
        if not filters:
            return None
            
        filter_conditions = []
        
        # Map to your actual field names
        field_mapping = {
            "project": "project_name",
            "folder": "folder", 
            "content_type": "content_type",
            "year": "year"
        }
        
        for key, value in filters.items():
            field_name = field_mapping.get(key, key)
            
            if isinstance(value, str):
                filter_conditions.append(f"{field_name} eq '{value}'")
            elif isinstance(value, (int, float)):
                filter_conditions.append(f"{field_name} eq {value}")
        
        return " and ".join(filter_conditions) if filter_conditions else None
    
    def search_by_project(self, project_name: str, query: str = "*", top_k: int = 10) -> List[SearchResult]:
        """Search within a specific project"""
        return self.retrieve(query, top_k, {"project": project_name})
    
    def search_documents_only(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """Search only document files (exclude images)"""
        filters = {
            "content_type": "application/pdf"  # Adjust based on your content types
        }
        return self.retrieve(query, top_k, filters)
    
    def get_recent_documents(self, days: int = 30, top_k: int = 10) -> List[SearchResult]:
        """Get recently modified documents"""
        try:
            # Note: This would need date filtering which is more complex
            # For now, just return general search
            results = self.search_client.search(
                search_text="*",
                select=["id", "filename", "content", "folder", "project_name", "last_modified"],
                top=top_k,
                order_by=["last_modified desc"]
            )
            
            search_results = []
            for result in results:
                content = result.get("content", "")
                if not content or len(content.strip()) < 50:
                    continue
                    
                metadata = {
                    "document_id": result.get("id", ""),
                    "filename": result.get("filename", ""),
                    "folder": result.get("folder", ""),
                    "project_name": result.get("project_name", ""),
                    "last_modified": result.get("last_modified")
                }
                
                search_result = SearchResult(
                    content=content,
                    metadata=metadata,
                    score=1.0,
                    source="recent"
                )
                search_results.append(search_result)
                
            return search_results
            
        except Exception as e:
            logger.error(f"Recent documents error: {e}")
            return []
