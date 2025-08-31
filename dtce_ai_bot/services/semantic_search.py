"""
Enhanced Semantic Search Service for DTCE AI Bot
Implements proper semantic search with intent-based routing and reranking
"""

import re
from typing import List, Dict, Any, Optional
import structlog
from azure.search.documents import SearchClient
from .intent_recognition import IntentRecognitionService, QueryIntent

logger = structlog.get_logger(__name__)


class SemanticSearchService:
    """
    Enhanced semantic search service that uses intent recognition for intelligent routing.
    
    This replaces the old keyword-based query enhancement with proper semantic understanding
    and intent-based search optimization.
    """
    
    def __init__(self, search_client: SearchClient):
        self.search_client = search_client
        self.intent_service = IntentRecognitionService()
        
    async def search_documents(self, query: str, project_filter: Optional[str] = None) -> List[Dict[str, any]]:
        """
        Perform intelligent semantic search using intent recognition.
        
        Args:
            query: User's natural language query
            project_filter: Optional project filter
            
        Returns:
            List of relevant documents ranked by semantic similarity
        """
        try:
            # Step 1: Classify the user's intent
            intent_result = self.intent_service.classify_intent(query)
            search_strategy = self.intent_service.get_search_strategy(intent_result)
            
            logger.info("Semantic search with intent recognition",
                       query=query,
                       intent=intent_result["intent"].value,
                       confidence=intent_result["confidence"],
                       strategy=search_strategy["search_type"])
            
            # Step 2: Execute search based on intent
            documents = await self._execute_semantic_search(query, search_strategy, project_filter)
            
            # Step 3: Apply intent-based reranking if needed
            if search_strategy["use_reranking"] and documents:
                documents = self._rerank_by_intent(documents, query, intent_result)
            
            # Step 4: Filter out phantom/superseded documents
            documents = self._filter_quality_documents(documents)
            
            logger.info("Semantic search completed",
                       total_found=len(documents),
                       intent=intent_result["intent"].value)
            
            return documents
            
        except Exception as e:
            logger.error("Semantic search failed", error=str(e), query=query)
            # Fallback to basic search
            return await self._fallback_search(query, project_filter)
    
    async def _execute_semantic_search(self, query: str, strategy: Dict[str, any], 
                                     project_filter: Optional[str] = None) -> List[Dict[str, any]]:
        """Execute the semantic search based on strategy."""
        
        # Build base search parameters for semantic search
        search_params = {
            'search_text': query,
            'top': 20,
            'select': ["id", "filename", "content", "blob_url", "project_name", "folder"],
            'query_type': 'semantic',
            'semantic_configuration_name': 'default',
            'query_caption': 'extractive',
            'query_answer': 'extractive'
        }
        
        # Build filters based on strategy
        filters = self._build_intent_filters(strategy, project_filter)
        if filters:
            search_params['filter'] = ' and '.join(filters)
        
        # Execute search
        try:
            results = self.search_client.search(**search_params)
            documents = [dict(result) for result in results]
            
            logger.info("Semantic search executed",
                       search_type=strategy["search_type"],
                       documents_found=len(documents),
                       filters_applied=len(filters))
            
            return documents
            
        except Exception as e:
            logger.warning("Semantic search failed, trying fallback", error=str(e))
            # Remove semantic parameters and try keyword search
            search_params.pop('query_type', None)
            search_params.pop('semantic_configuration_name', None)
            search_params.pop('query_caption', None)
            search_params.pop('query_answer', None)
            
            results = self.search_client.search(**search_params)
            return [dict(result) for result in results]
    
    def _build_intent_filters(self, strategy: Dict[str, any], project_filter: Optional[str] = None) -> List[str]:
        """Build search filters based on intent strategy."""
        filters = []
        
        # Always exclude superseded/archive folders
        base_exclusions = [
            "(not search.ismatch('*superseded*', 'filename'))",
            "(not search.ismatch('*superceded*', 'filename'))", 
            "(not search.ismatch('*archive*', 'filename'))",
            "(not search.ismatch('*trash*', 'filename'))",
            "(not search.ismatch('*photos*', 'filename'))"
        ]
        filters.extend(base_exclusions)
        
        # Add project filter if specified
        if project_filter:
            filters.append(f"search.ismatch('{project_filter}*', 'project_name')")
        
        # Don't filter by document types - semantic search works across all formats
        # Let the content and folder-based filtering do the work
        
        # Add folder filters based on intent (only for high-confidence targeted searches)
        if (strategy.get("folder_filters") and 
            strategy["search_type"] == "targeted_semantic" and 
            strategy.get("use_strict_filtering")):
            folder_names = strategy["folder_filters"]
            folder_filter = ' or '.join([f"search.ismatch('*{folder}*', 'folder')" for folder in folder_names])
            filters.append(f"({folder_filter})")
        
        return filters
    
    def _rerank_by_intent(self, documents: List[Dict[str, any]], query: str, 
                         intent_result: Dict[str, any]) -> List[Dict[str, any]]:
        """Rerank documents based on DTCE-specific intent relevance."""
        intent = intent_result["intent"]
        
        def calculate_intent_score(doc: Dict[str, any]) -> float:
            """Calculate DTCE intent-specific relevance score."""
            base_score = doc.get('@search.score', 0.0)
            
            # Boost based on intent-specific factors
            boost = 1.0
            
            filename = doc.get('filename', '').lower()
            content = doc.get('content', '').lower()
            folder = doc.get('folder', '').lower()
            
            # DTCE-specific intent boosting
            if intent == QueryIntent.POLICY:
                # Boost policy documents - employees must follow these
                if any(term in folder for term in ['policy', 'h&s', 'health', 'safety', 'employment', 'it policy']):
                    boost += 0.4
                if any(term in filename for term in ['policy', 'procedure', 'guideline']):
                    boost += 0.3
                if 'policy' in content[:500] or 'must' in content[:500]:
                    boost += 0.2
                    
            elif intent == QueryIntent.TECHNICAL_PROCEDURE:
                # Boost H2H and procedure documents - best practices
                if 'h2h' in folder or 'procedure' in folder or 'handbook' in folder:
                    boost += 0.5
                if any(term in filename for term in ['h2h', 'handbook', 'procedure', 'guide', 'how to']):
                    boost += 0.4
                if 'how to' in content[:500] or 'procedure' in content[:500]:
                    boost += 0.2
                    
            elif intent == QueryIntent.NZ_STANDARDS:
                # Boost NZ standards and engineering codes
                if any(term in folder for term in ['standard', 'engineering', 'code']):
                    boost += 0.4
                if any(term in filename for term in ['nzs', 'standard', 'code', 'specification']):
                    boost += 0.5
                # Look for NZS numbers in content
                if re.search(r'nzs?\s*\d+', content[:1000], re.IGNORECASE):
                    boost += 0.3
                    
            elif intent == QueryIntent.PROJECT_REFERENCE:
                # Boost project documents and reports
                if any(year in folder for year in ['225', '224', '223', '222', '221', '220']):
                    boost += 0.4
                if 'project' in folder or any(term in folder for term in ['report', 'brief', 'scope']):
                    boost += 0.3
                if any(term in filename for term in ['report', 'brief', 'scope', 'analysis', 'assessment']):
                    boost += 0.3
                    
            elif intent == QueryIntent.CLIENT_REFERENCE:
                # Boost client-related documents
                if any(term in folder for term in ['admin', 'client', 'contact']):
                    boost += 0.4
                if any(term in filename for term in ['client', 'contact', 'admin', 'brief']):
                    boost += 0.3
                # Look for contact information patterns
                if any(pattern in content[:1000] for pattern in ['@', 'phone', 'email', 'contact']):
                    boost += 0.2
            
            return base_score * boost
        
        # Sort by intent-adjusted score
        ranked_docs = sorted(documents, key=calculate_intent_score, reverse=True)
        
        logger.info("Documents reranked by DTCE intent",
                   intent=intent.value,
                   original_top=documents[0].get('filename') if documents else None,
                   reranked_top=ranked_docs[0].get('filename') if ranked_docs else None)
        
        return ranked_docs
    
    def _filter_quality_documents(self, documents: List[Dict[str, any]]) -> List[Dict[str, any]]:
        """Filter out phantom documents and low-quality results."""
        filtered_docs = []
        
        for doc in documents:
            content = doc.get('content', '')
            filename = doc.get('filename', '')
            
            # Filter out true phantom documents (very specific criteria)
            is_phantom = False
            if content and len(content) < 50:
                expected_stub = f"Document: {filename}"
                if content.strip() == expected_stub:
                    is_phantom = True
                    logger.info("Filtered phantom document", filename=filename)
            
            # Filter out superseded documents (additional check)
            is_superseded = False
            blob_name = doc.get('blob_name', '') or filename
            blob_url = doc.get('blob_url', '')
            
            superseded_indicators = ['superseded', 'superceded', 'archive', 'obsolete', 'old version']
            for indicator in superseded_indicators:
                if (indicator in blob_name.lower() or indicator in blob_url.lower()):
                    is_superseded = True
                    logger.info("Filtered superseded document", filename=filename, indicator=indicator)
                    break
            
            if not is_phantom and not is_superseded:
                filtered_docs.append(doc)
        
        logger.info("Document quality filtering completed",
                   original_count=len(documents),
                   filtered_count=len(filtered_docs))
        
        return filtered_docs
    
    async def _fallback_search(self, query: str, project_filter: Optional[str] = None) -> List[Dict[str, any]]:
        """Fallback to basic keyword search if semantic search fails."""
        logger.info("Using fallback keyword search", query=query)
        
        search_params = {
            'search_text': query,
            'top': 15,
            'select': ["id", "filename", "content", "blob_url", "project_name", "folder"]
        }
        
        # Basic exclusion filter
        filters = ["(not search.ismatch('*superseded*', 'filename'))"]
        if project_filter:
            filters.append(f"search.ismatch('{project_filter}*', 'project_name')")
        
        if filters:
            search_params['filter'] = ' and '.join(filters)
        
        try:
            results = self.search_client.search(**search_params)
            documents = [dict(result) for result in results]
            return self._filter_quality_documents(documents)
        except Exception as e:
            logger.error("Fallback search also failed", error=str(e))
            return []
