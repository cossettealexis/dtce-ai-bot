"""
Hybrid Retrieval Module

Combines vector search and keyword search for comprehensive retrieval.
"""

from typing import List, Dict, Any, Optional, Tuple
import logging
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential

from .config import RAGConfig, RetrievalConfig
from .embedder import EmbeddingGenerator

logger = logging.getLogger(__name__)


class SearchResult:
    """Represents a search result with relevance score"""
    
    def __init__(self, content: str, metadata: Dict[str, Any], score: float, source: str = "unknown"):
        self.content = content
        self.metadata = metadata
        self.score = score
        self.source = source  # "vector", "keyword", or "hybrid"
        
    def __repr__(self):
        return f"SearchResult(score={self.score:.3f}, source={self.source})"


class QueryExpander:
    """Expands queries for multi-query retrieval"""
    
    def __init__(self, config: RAGConfig):
        self.config = config
        
    def expand_query(self, original_query: str) -> List[str]:
        """
        Generate multiple query variations
        
        Args:
            original_query: Original search query
            
        Returns:
            List of query variations including original
        """
        queries = [original_query]
        
        if not self.config.retrieval.enable_multi_query:
            return queries
        
        # Simple query expansion strategies
        expanded = []
        
        # Add question variations
        if not original_query.endswith('?'):
            expanded.append(f"What is {original_query}?")
            expanded.append(f"How does {original_query} work?")
        
        # Add specific domain terms
        if "construction" not in original_query.lower():
            expanded.append(f"{original_query} construction")
        
        if "building" not in original_query.lower():
            expanded.append(f"{original_query} building")
            
        # Add technical variations
        if "standard" not in original_query.lower():
            expanded.append(f"{original_query} standards")
            
        # Limit to configured count
        max_expansions = self.config.retrieval.query_expansion_count - 1
        queries.extend(expanded[:max_expansions])
        
        return queries


class HybridRetriever:
    """
    Hybrid retrieval combining vector and keyword search
    """
    
    def __init__(self, config: RAGConfig, embedder: EmbeddingGenerator):
        self.config = config
        self.retrieval_config = config.retrieval
        self.embedder = embedder
        self.query_expander = QueryExpander(config)
        
        # Initialize Azure Search client
        credential = AzureKeyCredential(config.azure.search_admin_key)
        self.search_client = SearchClient(
            endpoint=config.azure.search_endpoint,
            index_name=config.azure.search_index_name,
            credential=credential
        )
        
    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[SearchResult]:
        """
        Perform hybrid retrieval for a query
        
        Args:
            query: Search query
            top_k: Number of results to return (uses config default if None)
            
        Returns:
            List of search results ranked by relevance
        """
        top_k = top_k or self.retrieval_config.top_k
        
        # Expand query if enabled
        queries = self.query_expander.expand_query(query)
        
        all_results = []
        
        # Retrieve for each query variation
        for q in queries:
            # Vector search
            vector_results = self._vector_search(q, self.retrieval_config.semantic_top_k)
            
            # Keyword search  
            keyword_results = self._keyword_search(q, self.retrieval_config.keyword_top_k)
            
            all_results.extend(vector_results)
            all_results.extend(keyword_results)
        
        # Combine and re-rank results
        combined_results = self._combine_results(all_results)
        
        # Apply semantic ranking if enabled
        if self.retrieval_config.enable_semantic_ranking:
            combined_results = self._semantic_rerank(query, combined_results)
        
        # Filter by minimum relevance score
        filtered_results = [
            result for result in combined_results 
            if result.score >= self.config.min_relevance_score
        ]
        
        return filtered_results[:top_k]
    
    def _vector_search(self, query: str, top_k: int) -> List[SearchResult]:
        """Perform vector similarity search"""
        try:
            # Generate query embedding
            query_embedding = self.embedder.embed_query(query)
            
            # Create vectorized query
            vector_query = VectorizedQuery(
                vector=query_embedding,
                k_nearest_neighbors=top_k,
                fields="content_vector"
            )
            
            # Search
            results = self.search_client.search(
                search_text=None,
                vector_queries=[vector_query],
                select=["content", "metadata", "chunk_id"],
                top=top_k
            )
            
            search_results = []
            for result in results:
                search_result = SearchResult(
                    content=result.get("content", ""),
                    metadata=result.get("metadata", {}),
                    score=result.get("@search.score", 0.0),
                    source="vector"
                )
                search_results.append(search_result)
                
            return search_results
            
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return []
    
    def _keyword_search(self, query: str, top_k: int) -> List[SearchResult]:
        """Perform keyword search"""
        try:
            results = self.search_client.search(
                search_text=query,
                select=["content", "metadata", "chunk_id"],
                top=top_k,
                search_mode="all"  # Require all terms
            )
            
            search_results = []
            for result in results:
                search_result = SearchResult(
                    content=result.get("content", ""),
                    metadata=result.get("metadata", {}),
                    score=result.get("@search.score", 0.0),
                    source="keyword"
                )
                search_results.append(search_result)
                
            return search_results
            
        except Exception as e:
            logger.error(f"Keyword search error: {e}")
            return []
    
    def _combine_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """
        Combine and deduplicate results from different search methods
        """
        # Group by content to handle duplicates
        content_to_result = {}
        
        for result in results:
            content_key = result.content[:100]  # Use first 100 chars as key
            
            if content_key in content_to_result:
                # Combine scores using weighted average
                existing = content_to_result[content_key]
                if result.source == "vector":
                    vector_weight = self.retrieval_config.hybrid_weight
                    keyword_weight = 1 - vector_weight
                    
                    if existing.source == "keyword":
                        combined_score = (result.score * vector_weight + 
                                        existing.score * keyword_weight)
                        existing.score = combined_score
                        existing.source = "hybrid"
            else:
                content_to_result[content_key] = result
        
        # Sort by score
        combined = list(content_to_result.values())
        combined.sort(key=lambda x: x.score, reverse=True)
        
        return combined
    
    def _semantic_rerank(self, query: str, results: List[SearchResult]) -> List[SearchResult]:
        """
        Apply semantic re-ranking to results
        """
        if not results:
            return results
        
        try:
            # Generate query embedding for comparison
            query_embedding = self.embedder.embed_query(query)
            
            # Calculate semantic similarity for each result
            for result in results:
                content_embedding = self.embedder.generate_embedding(result.content)
                semantic_score = self.embedder.calculate_similarity(
                    query_embedding, 
                    content_embedding
                )
                
                # Combine with original search score
                result.score = (result.score * 0.7 + semantic_score * 0.3)
            
            # Re-sort by updated scores
            results.sort(key=lambda x: x.score, reverse=True)
            
        except Exception as e:
            logger.error(f"Semantic re-ranking error: {e}")
        
        return results
    
    def retrieve_by_metadata(self, filters: Dict[str, Any], top_k: int = 10) -> List[SearchResult]:
        """
        Retrieve documents by metadata filters
        
        Args:
            filters: Metadata filters (e.g., {"document_type": "standard"})
            top_k: Number of results to return
            
        Returns:
            List of filtered search results
        """
        try:
            # Build filter string
            filter_conditions = []
            for key, value in filters.items():
                if isinstance(value, str):
                    filter_conditions.append(f"metadata/{key} eq '{value}'")
                else:
                    filter_conditions.append(f"metadata/{key} eq {value}")
            
            filter_string = " and ".join(filter_conditions)
            
            results = self.search_client.search(
                search_text="*",
                filter=filter_string,
                select=["content", "metadata", "chunk_id"],
                top=top_k
            )
            
            search_results = []
            for result in results:
                search_result = SearchResult(
                    content=result.get("content", ""),
                    metadata=result.get("metadata", {}),
                    score=result.get("@search.score", 1.0),
                    source="metadata"
                )
                search_results.append(search_result)
                
            return search_results
            
        except Exception as e:
            logger.error(f"Metadata search error: {e}")
            return []
