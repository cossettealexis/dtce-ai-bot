"""
Smart Semantic Search Service for DTCE AI Bot
Uses intelligent routing to search in the right folders with the right keywords
"""

import re
from typing import List, Dict, Any, Optional
import structlog
from azure.search.documents import SearchClient
from openai import AsyncAzureOpenAI
from .intelligent_query_router import IntelligentQueryRouter, SearchCategory

logger = structlog.get_logger(__name__)


class SemanticSearchService:
    """
    Intelligent semantic search service that routes queries to appropriate folders.
    
    Uses AI-powered intent classification to search only relevant document categories.
    """
    
    def __init__(self, search_client: SearchClient, openai_client: Optional[AsyncAzureOpenAI] = None, model_name: str = "gpt-4"):
        self.search_client = search_client
        self.query_router = None
        
        # Initialize query router if OpenAI client is provided
        if openai_client:
            self.query_router = IntelligentQueryRouter(openai_client, model_name)
        
    async def search_documents(self, query: str, project_filter: Optional[str] = None) -> List[Dict[str, any]]:
        """
        Perform intelligent semantic search with folder routing.
        
        Args:
            query: User's natural language query
            project_filter: Optional project filter
            
        Returns:
            List of relevant documents ranked by semantic similarity
        """
        try:
            logger.info("Intelligent semantic search", query=query)
            
            # Route query to appropriate folder category
            if self.query_router:
                category, confidence = await self.query_router.classify_query(query)
                logger.info("Query routed", category=category.value, confidence=confidence)
                
                # Get folder-specific search with routing
                documents = await self._execute_routed_search(query, category, project_filter)
            else:
                # Fallback to general search if no router available
                logger.warning("No query router available, using general search")
                documents = await self._execute_pure_semantic_search(query, project_filter)
            
            # Filter out superseded documents
            documents = self._filter_quality_documents(documents)
            
            logger.info("Intelligent semantic search completed", total_found=len(documents))
            
            return documents
            
        except Exception as e:
            logger.error("Semantic search failed", error=str(e), query=query)
            # Fallback to basic search
            return await self._fallback_search(query, project_filter)
    
    async def _execute_routed_search(self, query: str, category: SearchCategory, project_filter: Optional[str] = None) -> List[Dict[str, any]]:
        """Execute semantic search routed to specific folder category."""
        
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
        
        # Build smart filters combining exclusions with folder routing
        filters = self._build_routed_filters(category, project_filter)
        
        if filters:
            search_params['filter'] = ' and '.join(filters)
            logger.info("Routed semantic search", 
                       category=category.value, 
                       filter_count=len(filters))
        
        # Execute search
        try:
            results = self.search_client.search(**search_params)
            documents = [dict(result) for result in results]
            
            logger.info("Routed semantic search executed", 
                       category=category.value,
                       documents_found=len(documents))
            
            return documents
            
        except Exception as e:
            logger.warning("Routed semantic search failed, trying fallback", 
                          category=category.value,
                          error=str(e))
            # Remove semantic parameters and try keyword search
            search_params.pop('query_type', None)
            search_params.pop('semantic_configuration_name', None)
            search_params.pop('query_caption', None)
            search_params.pop('query_answer', None)
            
            results = self.search_client.search(**search_params)
            return [dict(result) for result in results]
    
    def _build_routed_filters(self, category: SearchCategory, project_filter: Optional[str] = None) -> List[str]:
        """Build search filters for routed queries."""
        filters = []
        
        # Always exclude superseded/archive folders
        base_exclusions = [
            "not search.ismatch('*superseded*', 'filename')",
            "not search.ismatch('*superceded*', 'filename')", 
            "not search.ismatch('*archive*', 'filename')",
            "not search.ismatch('*trash*', 'filename')"
        ]
        filters.extend(base_exclusions)
        
        # NOTE: Folder field is empty in current index, so skip folder filtering for now
        # The AI classification will handle intelligent search through better query understanding
        # and specialized prompts rather than folder restrictions
        logger.info("Using AI-based routing without folder filters", 
                   category=category.value,
                   reason="folder_field_empty_in_index")
        
        # Add project filter if specified
        if project_filter and not ('search.ismatch' in project_filter or 'and' in project_filter):
            filters.append(f"search.ismatch('{project_filter}*', 'project_name')")
        
        return filters
    
    async def _execute_pure_semantic_search(self, query: str, project_filter: Optional[str] = None) -> List[Dict[str, any]]:
        """Execute pure semantic search without intent classification bullshit."""
        
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
        
        # Simple, reliable filters - just exclude superseded files and apply project filter
        filters = [
            "not search.ismatch('*superseded*', 'filename')",
            "not search.ismatch('*superceded*', 'filename')",
            "not search.ismatch('*archive*', 'filename')",
            "not search.ismatch('*trash*', 'filename')"
        ]
        
        # Add project filter if specified (simple project name)
        if project_filter and not ('search.ismatch' in project_filter or 'and' in project_filter):
            filters.append(f"search.ismatch('{project_filter}*', 'project_name')")
        
        if filters:
            search_params['filter'] = ' and '.join(filters)
            logger.info("Simple semantic search filter applied", filter_count=len(filters))
        
        # Execute search
        try:
            results = self.search_client.search(**search_params)
            documents = [dict(result) for result in results]
            
            logger.info("Semantic search executed", documents_found=len(documents))
            
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
            logger.info("Processing project_filter", project_filter=project_filter[:200])
            # Check if project_filter is already a complete filter expression or just a project name
            if ('search.ismatch' in project_filter or 
                'and' in project_filter or 
                'or' in project_filter or 
                'not ' in project_filter.lower() or
                project_filter.startswith('(')):
                # It's already a complete filter expression (from folder structure service)
                logger.info("Using complete filter expression")
                filters.append(project_filter)
            else:
                # It's a simple project name, wrap it in search.ismatch
                logger.info("Wrapping simple project name")
                filters.append(f"search.ismatch('{project_filter}*', 'project_name')")
        
        # Don't filter by document types - semantic search works across all formats
        # Let the content and folder-based filtering do the work
        
        # Add folder filters based on intent (light filtering only)
        if strategy.get("folder_filters") and strategy.get("use_strict_filtering"):
            folder_names = strategy["folder_filters"]
            folder_filter = ' or '.join([f"search.ismatch('*{folder}*', 'folder')" for folder in folder_names])
            filters.append(f"({folder_filter})")
        
        return filters
    
    def _rerank_by_intent(self, documents: List[Dict[str, any]], query: str, 
                         intent_result: Dict[str, any]) -> List[Dict[str, any]]:
        """Rerank documents based on search category relevance."""
        
        def calculate_category_score(doc: Dict[str, any], category: SearchCategory) -> float:
            """Calculate category-specific relevance score."""
            base_score = doc.get('@search.score', 0.0)
            
            # Boost based on category-specific factors
            boost = 1.0
            
            filename = doc.get('filename', '').lower()
            content = doc.get('content', '').lower()
            folder = doc.get('folder', '').lower()
            
            # Category-specific boosting
            if category == SearchCategory.POLICY:
                # Boost policy documents - employees must follow these
                if any(term in folder for term in ['policy', 'h&s', 'health', 'safety', 'employment', 'hr']):
                    boost += 0.4
                if any(term in filename for term in ['policy', 'procedure', 'guideline', 'handbook']):
                    boost += 0.3
                if 'policy' in content[:500] or 'must' in content[:500]:
                    boost += 0.2
                    
            elif category == SearchCategory.PROCEDURES:
                # Boost H2H and procedure documents - best practices
                if any(term in folder for term in ['h2h', 'procedure', 'handbook', 'workflow']):
                    boost += 0.5
                if any(term in filename for term in ['h2h', 'handbook', 'procedure', 'guide', 'how to']):
                    boost += 0.4
                if 'how to' in content[:500] or 'procedure' in content[:500]:
                    boost += 0.2
                    
            elif category == SearchCategory.STANDARDS:
                # Boost NZ standards and engineering codes
                if any(term in folder for term in ['standard', 'engineering', 'code', 'specification']):
                    boost += 0.4
                if any(term in filename for term in ['nzs', 'standard', 'code', 'specification']):
                    boost += 0.5
                # Look for NZS numbers in content
                if re.search(r'nzs?\s*\d+', content[:1000], re.IGNORECASE):
                    boost += 0.3
                    
            elif category == SearchCategory.PROJECTS:
                # Boost project documents and reports
                if any(year in folder for year in ['225', '224', '223', '222', '221', '220']):
                    boost += 0.4
                if 'project' in folder or any(term in folder for term in ['report', 'brief', 'scope']):
                    boost += 0.3
                if any(term in filename for term in ['report', 'brief', 'scope', 'analysis', 'assessment']):
                    boost += 0.3
                    
            elif category == SearchCategory.CLIENTS:
                # Boost client-related documents
                if any(term in folder for term in ['admin', 'client', 'contact', 'nzta', 'council']):
                    boost += 0.4
                if any(term in filename for term in ['client', 'contact', 'admin', 'brief']):
                    boost += 0.3
                # Look for contact information patterns
                if any(pattern in content[:1000] for pattern in ['@', 'phone', 'email', 'contact']):
                    boost += 0.2
            
            return base_score * boost
        
        # Sort by category-adjusted score - need category parameter
        # For now, just return documents as-is since we don't have category context here
        logger.info("Documents processed (no reranking without category context)")
        
        return documents
    
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
        logger.info("Using simple fallback keyword search", query=query)
        
        # Simple exclusion filters
        filters = [
            "not search.ismatch('*superseded*', 'filename')",
            "not search.ismatch('*superceded*', 'filename')", 
            "not search.ismatch('*archive*', 'filename')"
        ]
        
        # Add simple project filter if provided
        if project_filter and not ('search.ismatch' in project_filter or 'and' in project_filter):
            filters.append(f"search.ismatch('{project_filter}*', 'project_name')")
        
        search_params = {
            'search_text': query,
            'top': 10,
            'search_mode': 'any'
        }
        
        if filters:
            search_params['filter'] = ' and '.join(filters)
        
        try:
            results = self.search_client.search(**search_params)
            documents = [dict(result) for result in results]
            logger.info("Fallback search completed", documents_found=len(documents))
            return self._filter_quality_documents(documents)
        except Exception as e:
            logger.error("Fallback search failed", error=str(e))
            return []
