"""
Specialized Search Service - Advanced search strategies for different content types
"""

from typing import List, Dict, Any, Optional
import structlog
from azure.search.documents import SearchClient
from openai import AsyncAzureOpenAI

logger = structlog.get_logger(__name__)


class SpecializedSearchService:
    """
    Service providing specialized search strategies for different content types.
    Implements advanced retrieval techniques as described in RAG requirements.
    """
    
    def __init__(self, search_client: SearchClient, openai_client: AsyncAzureOpenAI, model_name: str):
        self.search_client = search_client
        self.openai_client = openai_client
        self.model_name = model_name
    
    async def execute_specialized_search(
        self, 
        query: str, 
        search_strategy: Dict[str, Any]
    ) -> List[Dict]:
        """
        Execute specialized search based on strategy.
        
        Args:
            query: User's search query
            search_strategy: Strategy dictionary from intent classifier
            
        Returns:
            List of relevant documents
        """
        try:
            category = search_strategy.get('category', 'general')
            logger.info("Executing specialized search", category=category)
            
            if category == 'project_reference':
                return await self._search_projects(query, search_strategy)
            elif category == 'nz_standards':
                return await self._search_standards(query, search_strategy)
            elif category == 'policy':
                return await self._search_policies(query, search_strategy)
            elif category == 'procedures':
                return await self._search_procedures(query, search_strategy)
            elif category == 'client_reference':
                return await self._search_clients(query, search_strategy)
            else:
                return await self._search_general(query, search_strategy)
                
        except Exception as e:
            logger.error("Specialized search failed", error=str(e))
            return await self._fallback_search(query)
    
    async def _search_projects(self, query: str, strategy: Dict[str, Any]) -> List[Dict]:
        """
        Specialized search for project documents.
        """
        search_params = {
            'search_text': query,
            'top': 15,
            'select': ["id", "filename", "content", "blob_url", "project_name", "folder"],
            'search_mode': 'any'
        }
        
        # Build project-specific filters
        filters = []
        
        # Project folder filter
        filters.append("search.ismatch('*Projects*', 'blob_url')")
        
        # Project number filter if specified
        if strategy.get('project_filter'):
            project_num = strategy['project_filter']
            filters.append(f"search.ismatch('*{project_num}*', 'blob_url')")
        
        # Exclude common non-project folders
        filters.append("(not search.ismatch('*CPD*', 'blob_url'))")
        filters.append("(not search.ismatch('*Training*', 'blob_url'))")
        
        # Document type filter for projects
        project_doc_types = ['pdf', 'docx', 'xlsx']
        doc_filter = ' or '.join([f"search.ismatch('*.{ext}', 'filename')" for ext in project_doc_types])
        filters.append(f"({doc_filter})")
        
        search_params['filter'] = ' and '.join(filters)
        
        # Execute search
        results = self.search_client.search(**search_params)
        documents = [dict(result) for result in results]
        
        # Post-process: prioritize recent projects and relevant documents
        return self._rank_project_documents(documents, query)
    
    async def _search_standards(self, query: str, strategy: Dict[str, Any]) -> List[Dict]:
        """
        Specialized search for NZ standards and codes.
        """
        # Enhance query with standards-specific terms
        enhanced_query = await self._enhance_standards_query(query)
        
        search_params = {
            'search_text': enhanced_query,
            'top': 12,
            'select': ["id", "filename", "content", "blob_url", "project_name", "folder"],
            'search_mode': 'any'
        }
        
        # Standards-specific filters
        filters = []
        
        # Folder filters for standards
        standards_folders = [
            "search.ismatch('*Standards*', 'blob_url')",
            "search.ismatch('*Engineering*', 'blob_url')",
            "search.ismatch('*Reference*', 'blob_url')"
        ]
        filters.append(f"({' or '.join(standards_folders)})")
        
        # File type filter (mainly PDFs for standards)
        filters.append("search.ismatch('*.pdf', 'filename')")
        
        # Standards naming patterns
        standards_patterns = [
            "search.ismatch('*NZS*', 'filename')",
            "search.ismatch('*AS/NZS*', 'filename')",
            "search.ismatch('*NZBC*', 'filename')"
        ]
        filters.append(f"({' or '.join(standards_patterns)})")
        
        search_params['filter'] = ' and '.join(filters)
        
        results = self.search_client.search(**search_params)
        documents = [dict(result) for result in results]
        
        return self._rank_standards_documents(documents, query)
    
    async def _search_policies(self, query: str, strategy: Dict[str, Any]) -> List[Dict]:
        """
        Specialized search for company policies.
        """
        search_params = {
            'search_text': query,
            'top': 10,
            'select': ["id", "filename", "content", "blob_url", "project_name", "folder"],
            'search_mode': 'any'
        }
        
        # Policy-specific filters
        filters = []
        
        # Policy folders
        policy_folders = [
            "search.ismatch('*Health*Safety*', 'blob_url')",
            "search.ismatch('*IT*', 'blob_url')",
            "search.ismatch('*Policies*', 'blob_url')",
            "search.ismatch('*Administration*', 'blob_url')",
            "search.ismatch('*HR*', 'blob_url')"
        ]
        filters.append(f"({' or '.join(policy_folders)})")
        
        # Document types for policies
        policy_doc_types = ['pdf', 'docx']
        doc_filter = ' or '.join([f"search.ismatch('*.{ext}', 'filename')" for ext in policy_doc_types])
        filters.append(f"({doc_filter})")
        
        search_params['filter'] = ' and '.join(filters)
        
        results = self.search_client.search(**search_params)
        return [dict(result) for result in results]
    
    async def _search_procedures(self, query: str, strategy: Dict[str, Any]) -> List[Dict]:
        """
        Specialized search for procedures and handbooks.
        """
        search_params = {
            'search_text': query,
            'top': 10,
            'select': ["id", "filename", "content", "blob_url", "project_name", "folder"],
            'search_mode': 'any'
        }
        
        # Procedure-specific filters
        filters = []
        
        # Procedure folders
        procedure_folders = [
            "search.ismatch('*H2H*', 'blob_url')",
            "search.ismatch('*Head*Head*', 'blob_url')",
            "search.ismatch('*Procedures*', 'blob_url')",
            "search.ismatch('*Engineering*', 'blob_url')",
            "search.ismatch('*Templates*', 'blob_url')"
        ]
        filters.append(f"({' or '.join(procedure_folders)})")
        
        # Document types
        filters.append("(search.ismatch('*.pdf', 'filename') or search.ismatch('*.docx', 'filename'))")
        
        search_params['filter'] = ' and '.join(filters)
        
        results = self.search_client.search(**search_params)
        return [dict(result) for result in results]
    
    async def _search_clients(self, query: str, strategy: Dict[str, Any]) -> List[Dict]:
        """
        Specialized search for client and contact information.
        """
        search_params = {
            'search_text': query,
            'top': 12,
            'select': ["id", "filename", "content", "blob_url", "project_name", "folder"],
            'search_mode': 'any'
        }
        
        # Client-specific filters
        filters = []
        
        # Search in relevant folders
        client_folders = [
            "search.ismatch('*Projects*', 'blob_url')",  # Project documents often contain client info
            "search.ismatch('*Administration*', 'blob_url')",
            "search.ismatch('*Business*', 'blob_url')",
            "search.ismatch('*Clients*', 'blob_url')"
        ]
        filters.append(f"({' or '.join(client_folders)})")
        
        # Document types likely to contain contact info
        contact_doc_types = ['pdf', 'docx', 'xlsx']
        doc_filter = ' or '.join([f"search.ismatch('*.{ext}', 'filename')" for ext in contact_doc_types])
        filters.append(f"({doc_filter})")
        
        search_params['filter'] = ' and '.join(filters)
        
        results = self.search_client.search(**search_params)
        return [dict(result) for result in results]
    
    async def _search_general(self, query: str, strategy: Dict[str, Any]) -> List[Dict]:
        """
        General search when no specific category applies.
        """
        search_params = {
            'search_text': query,
            'top': 15,
            'select': ["id", "filename", "content", "blob_url", "project_name", "folder"],
            'search_mode': 'any'
        }
        
        # Basic filters
        filters = []
        
        # Exclude superseded and archive documents
        filters.append("(not search.ismatch('*superseded*', 'filename'))")
        filters.append("(not search.ismatch('*archive*', 'filename'))")
        filters.append("(not search.ismatch('*trash*', 'filename'))")
        
        search_params['filter'] = ' and '.join(filters)
        
        results = self.search_client.search(**search_params)
        return [dict(result) for result in results]
    
    async def _enhance_standards_query(self, query: str) -> str:
        """
        Enhance query for better standards search.
        """
        # Add common standards terminology
        enhancements = []
        
        query_lower = query.lower()
        
        # Add standard numbers if not present
        if 'concrete' in query_lower and 'nzs' not in query_lower:
            enhancements.append('NZS 3101')
        
        if 'steel' in query_lower and 'nzs' not in query_lower:
            enhancements.append('NZS 3404')
        
        if any(term in query_lower for term in ['wind', 'earthquake', 'seismic', 'load']) and '1170' not in query_lower:
            enhancements.append('NZS 1170')
        
        if 'timber' in query_lower and 'nzs' not in query_lower:
            enhancements.append('NZS 3603')
        
        enhanced_query = query
        if enhancements:
            enhanced_query += ' ' + ' '.join(enhancements)
        
        return enhanced_query
    
    def _rank_project_documents(self, documents: List[Dict], query: str) -> List[Dict]:
        """
        Rank project documents by relevance and recency.
        """
        scored_docs = []
        
        for doc in documents:
            score = 0
            blob_url = doc.get('blob_url', '').lower()
            filename = doc.get('filename', '').lower()
            
            # Prioritize recent years
            if '/225/' in blob_url:  # 2025
                score += 3
            elif '/224/' in blob_url:  # 2024
                score += 2
            elif '/223/' in blob_url:  # 2023
                score += 1
            
            # Prioritize certain document types
            if any(doc_type in filename for doc_type in ['report', 'calc', 'drawing']):
                score += 2
            
            # Boost if query terms appear in filename
            query_terms = query.lower().split()
            for term in query_terms:
                if len(term) > 2 and term in filename:
                    score += 1
            
            scored_docs.append((doc, score))
        
        # Sort by score
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        
        return [doc for doc, score in scored_docs]
    
    def _rank_standards_documents(self, documents: List[Dict], query: str) -> List[Dict]:
        """
        Rank standards documents by relevance to query.
        """
        scored_docs = []
        
        for doc in documents:
            score = 0
            filename = doc.get('filename', '').lower()
            
            # Prioritize exact standard matches
            query_lower = query.lower()
            if 'nzs' in query_lower:
                # Extract standard number from query
                import re
                std_match = re.search(r'nzs\s*(\d+)', query_lower)
                if std_match:
                    std_num = std_match.group(1)
                    if std_num in filename:
                        score += 5
            
            # Prioritize current standards over superseded
            if 'superseded' not in filename and 'old' not in filename:
                score += 2
            
            scored_docs.append((doc, score))
        
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, score in scored_docs]
    
    async def _fallback_search(self, query: str) -> List[Dict]:
        """
        Fallback search when specialized search fails.
        """
        try:
            search_params = {
                'search_text': query,
                'top': 10,
                'select': ["id", "filename", "content", "blob_url", "project_name", "folder"]
            }
            
            results = self.search_client.search(**search_params)
            return [dict(result) for result in results]
            
        except Exception as e:
            logger.error("Fallback search failed", error=str(e))
            return []
