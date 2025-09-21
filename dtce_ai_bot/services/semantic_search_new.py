"""
Semantic Search Service - Implements hybrid search with vector and keyword search
Follows the RAG pipeline described in the requirements
"""

import os
import re
from typing import List, Dict, Any, Optional
import structlog
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from openai import AsyncAzureOpenAI

logger = structlog.get_logger(__name__)


class SemanticSearchService:
    """
    Advanced semantic search service implementing:
    - Vector search for semantic similarity
    - Keyword search for exact matches
    - Hybrid search combining both approaches
    - Semantic ranking for improved relevance
    """
    
    def __init__(self, search_client: SearchClient, openai_client: AsyncAzureOpenAI, model_name: str):
        self.search_client = search_client
        self.openai_client = openai_client
        self.model_name = model_name
        self.embedding_model = os.getenv("AZURE_OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002")
    
    async def search_documents(
        self, 
        query: str, 
        project_filter: Optional[str] = None,
        doc_types: Optional[List[str]] = None,
        use_hybrid: bool = True,
        top_k: int = 20
    ) -> List[Dict]:
        """
        Main search method implementing hybrid search approach.
        
        Args:
            query: User's search query
            project_filter: Optional project number filter
            doc_types: Optional document type filters
            use_hybrid: Whether to use hybrid search (vector + keyword)
            top_k: Number of results to return
        """
        try:
            logger.info("Starting semantic search", query=query, use_hybrid=use_hybrid)
            
            if use_hybrid:
                # Use hybrid search for best results
                documents = await self._hybrid_search(query, project_filter, doc_types, top_k)
            else:
                # Use vector search only
                documents = await self._vector_search(query, project_filter, doc_types, top_k)
            
            # Apply semantic ranking if available
            if documents:
                documents = await self._apply_semantic_ranking(documents, query)
            
            logger.info("Search completed", documents_found=len(documents))
            return documents
            
        except Exception as e:
            logger.error("Semantic search failed", error=str(e))
            # Fallback to keyword search
            return await self._keyword_search(query, project_filter, doc_types, top_k)
    
    async def _hybrid_search(
        self, 
        query: str, 
        project_filter: Optional[str], 
        doc_types: Optional[List[str]], 
        top_k: int
    ) -> List[Dict]:
        """
        Implement hybrid search combining vector and keyword search.
        This is the recommended approach for maximum accuracy.
        """
        try:
            # Step 1: Generate query embedding for vector search
            query_vector = await self._generate_query_embedding(query)
            
            # Step 2: Build search parameters
            search_params = {
                'search_text': query,  # Keyword search
                'top': top_k,
                'select': ["id", "filename", "content", "blob_url", "project_name", "folder", "chunk_id"],
                'query_type': 'semantic'  # Enable semantic search if available
            }
            
            # Step 3: Add vector search
            if query_vector:
                try:
                    vector_query = VectorizedQuery(
                        vector=query_vector,
                        k_nearest_neighbors=top_k,
                        fields="content_vector"  # Assuming this is your vector field
                    )
                    search_params['vector_queries'] = [vector_query]
                except Exception as ve:
                    logger.warning("Vector search not available, using keyword only", error=str(ve))
            
            # Step 4: Add filters
            filters = self._build_filters(project_filter, doc_types)
            if filters:
                search_params['filter'] = ' and '.join(filters)
            
            # Step 5: Execute hybrid search
            results = self.search_client.search(**search_params)
            documents = [dict(result) for result in results]
            
            logger.info("Hybrid search completed", results_count=len(documents))
            return documents
            
        except Exception as e:
            logger.error("Hybrid search failed", error=str(e))
            # Fallback to keyword search
            return await self._keyword_search(query, project_filter, doc_types, top_k)
    
    async def _vector_search(
        self, 
        query: str, 
        project_filter: Optional[str], 
        doc_types: Optional[List[str]], 
        top_k: int
    ) -> List[Dict]:
        """
        Pure vector search for semantic similarity.
        """
        try:
            # Generate query embedding
            query_vector = await self._generate_query_embedding(query)
            if not query_vector:
                logger.warning("Failed to generate query embedding, falling back to keyword search")
                return await self._keyword_search(query, project_filter, doc_types, top_k)
            
            # Build vector search parameters
            vector_query = VectorizedQuery(
                vector=query_vector,
                k_nearest_neighbors=top_k,
                fields="content_vector"
            )
            
            search_params = {
                'vector_queries': [vector_query],
                'select': ["id", "filename", "content", "blob_url", "project_name", "folder", "chunk_id"],
                'top': top_k
            }
            
            # Add filters
            filters = self._build_filters(project_filter, doc_types)
            if filters:
                search_params['filter'] = ' and '.join(filters)
            
            # Execute vector search
            results = self.search_client.search(**search_params)
            documents = [dict(result) for result in results]
            
            logger.info("Vector search completed", results_count=len(documents))
            return documents
            
        except Exception as e:
            logger.error("Vector search failed", error=str(e))
            return await self._keyword_search(query, project_filter, doc_types, top_k)
    
    async def _keyword_search(
        self, 
        query: str, 
        project_filter: Optional[str], 
        doc_types: Optional[List[str]], 
        top_k: int
    ) -> List[Dict]:
        """
        Traditional keyword search as fallback.
        """
        try:
            search_params = {
                'search_text': query,
                'top': top_k,
                'select': ["id", "filename", "content", "blob_url", "project_name", "folder"],
                'search_mode': 'all'  # Require all terms to match
            }
            
            # Add filters
            filters = self._build_filters(project_filter, doc_types)
            if filters:
                search_params['filter'] = ' and '.join(filters)
            
            # Execute keyword search
            results = self.search_client.search(**search_params)
            documents = [dict(result) for result in results]
            
            logger.info("Keyword search completed", results_count=len(documents))
            return documents
            
        except Exception as e:
            logger.error("Keyword search failed", error=str(e))
            return []
    
    async def _generate_query_embedding(self, query: str) -> Optional[List[float]]:
        """
        Generate embedding vector for the user's query.
        This should use the same embedding model used for document indexing.
        """
        try:
            response = await self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=query
            )
            
            embedding = response.data[0].embedding
            logger.debug("Generated query embedding", embedding_length=len(embedding))
            return embedding
            
        except Exception as e:
            logger.error("Failed to generate query embedding", error=str(e))
            return None
    
    def _build_filters(self, project_filter: Optional[str], doc_types: Optional[List[str]]) -> List[str]:
        """
        Build Azure Search filters for refined search.
        """
        filters = []
        
        # Exclude superseded/archive documents
        excluded_filter = "(not search.ismatch('*superseded*', 'filename')) and (not search.ismatch('*archive*', 'filename')) and (not search.ismatch('*trash*', 'filename'))"
        filters.append(excluded_filter)
        
        # Add project filter
        if project_filter:
            # Extract project number
            project_match = re.search(r'\d+', project_filter)
            if project_match:
                project_num = project_match.group(0)
                project_filter_str = f"search.ismatch('*{project_num}*', 'blob_url')"
                filters.append(project_filter_str)
        
        # Add document type filter
        if doc_types:
            doc_filter = ' or '.join([f"search.ismatch('*.{ext}', 'filename')" for ext in doc_types])
            filters.append(f"({doc_filter})")
        
        return filters
    
    async def _apply_semantic_ranking(self, documents: List[Dict], query: str) -> List[Dict]:
        """
        Apply semantic ranking to re-rank results for better relevance.
        This could use Azure's semantic ranker or a custom re-ranking model.
        """
        try:
            # For now, return documents as-is
            # In the future, this could implement:
            # - Azure AI Search semantic ranker
            # - Custom re-ranking model
            # - LLM-based relevance scoring
            
            logger.debug("Semantic ranking applied", original_count=len(documents))
            return documents
            
        except Exception as e:
            logger.error("Semantic ranking failed", error=str(e))
            return documents
    
    async def multi_source_search(self, query: str, sources: List[str]) -> Dict[str, List[Dict]]:
        """
        Search across multiple data sources.
        This implements the multi-source retrieval strategy.
        """
        results = {}
        
        for source in sources:
            try:
                if source == 'azure_search':
                    results[source] = await self.search_documents(query)
                elif source == 'google_docs':
                    # Placeholder for Google Docs integration
                    results[source] = []
                elif source == 'external_apis':
                    # Placeholder for external API integration
                    results[source] = []
                else:
                    logger.warning("Unknown search source", source=source)
                    results[source] = []
                    
            except Exception as e:
                logger.error("Multi-source search failed for source", source=source, error=str(e))
                results[source] = []
        
        return results
    
    async def query_expansion(self, query: str) -> List[str]:
        """
        Expand user query into multiple sub-queries for better retrieval.
        This implements the query rewriting strategy.
        """
        try:
            expansion_prompt = f"""Given this user query: "{query}"

Generate 2-3 related search queries that would help find comprehensive information about this topic. 
The queries should:
1. Cover different aspects of the question
2. Use alternative terminology 
3. Be specific and focused

Return only the queries, one per line, without numbering or explanation."""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a search query expansion expert. Generate alternative search queries to improve information retrieval."},
                    {"role": "user", "content": expansion_prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            expanded_queries = response.choices[0].message.content.strip().split('\n')
            expanded_queries = [q.strip() for q in expanded_queries if q.strip()]
            
            # Include original query
            all_queries = [query] + expanded_queries
            
            logger.info("Query expansion completed", original=query, expanded=expanded_queries)
            return all_queries
            
        except Exception as e:
            logger.error("Query expansion failed", error=str(e))
            return [query]  # Return original query as fallback
