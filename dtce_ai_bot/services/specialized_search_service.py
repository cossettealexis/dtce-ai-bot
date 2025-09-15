"""
Specialized Search Service

Single Responsibility: Handle specialized search operations for different intent types
"""

import re
from typing import List, Dict, Any, Optional, Tuple
import structlog
from azure.search.documents import SearchClient
from openai import AsyncAzureOpenAI

logger = structlog.get_logger(__name__)


class SpecializedSearchService:
    """
    Responsible for executing specialized searches based on classified user intent.
    Each search type has its own optimized approach for maximum relevance.
    """
    
    def __init__(self, search_client: SearchClient, openai_client: AsyncAzureOpenAI, model_name: str):
        self.search_client = search_client
        self.openai_client = openai_client
        self.model_name = model_name
    
    async def execute_project_search(self, question: str, project_number: str = None) -> Tuple[List[Dict], str]:
        """
        Execute a direct project search for a specific project number.
        
        Args:
            question: The user's original question
            project_number: Extracted project number if available
            
        Returns:
            Tuple of (documents, search_strategy_used)
        """
        try:
            # Extract project number from question if not provided
            if not project_number:
                project_number = self._extract_project_number(question)
            
            if project_number:
                logger.info(f"Searching for specific project: {project_number}")
                
                # Search with exact project number
                search_query = f"project {project_number}"
                filter_expr = f"blob_name eq '*{project_number}*'"
                
                results = self.search_client.search(
                    search_text=search_query,
                    filter=filter_expr,
                    top=10,
                    search_mode="all"
                )
                
                documents = list(results)
                return documents, f"project_specific_search_{project_number}"
            
            # Fallback to general project search
            return await self._general_project_search(question)
            
        except Exception as e:
            logger.error("Project search failed", error=str(e))
            return [], "project_search_failed"
    
    async def execute_keyword_project_search(self, question: str) -> Tuple[List[Dict], str]:
        """
        Execute a keyword-based search for projects with similar scope.
        
        Args:
            question: The user's question containing keywords
            
        Returns:
            Tuple of (documents, search_strategy_used)
        """
        try:
            # Extract engineering keywords
            keywords = await self._extract_engineering_keywords(question)
            logger.info(f"Searching projects with keywords: {keywords}")
            
            # Build search query emphasizing scope and technical terms
            search_query = " OR ".join(keywords) if keywords else question
            
            results = self.search_client.search(
                search_text=search_query,
                top=15,
                search_mode="any",
                query_type="semantic"
            )
            
            documents = list(results)
            return documents, f"keyword_project_search_{len(keywords)}_terms"
            
        except Exception as e:
            logger.error("Keyword project search failed", error=str(e))
            return [], "keyword_search_failed"
    
    async def execute_template_search(self, question: str) -> Tuple[List[Dict], str]:
        """
        Execute a search for templates and similar documents.
        
        Args:
            question: The user's question about templates
            
        Returns:
            Tuple of (documents, search_strategy_used)
        """
        try:
            # Extract document type from question
            doc_type = self._extract_document_type(question)
            logger.info(f"Searching for templates: {doc_type}")
            
            # Search for templates and similar documents
            template_terms = ["template", "format", "example", "standard", doc_type] if doc_type else ["template", "format"]
            search_query = " OR ".join(template_terms)
            
            results = self.search_client.search(
                search_text=search_query,
                top=12,
                search_mode="any"
            )
            
            documents = list(results)
            return documents, f"template_search_{doc_type or 'general'}"
            
        except Exception as e:
            logger.error("Template search failed", error=str(e))
            return [], "template_search_failed"
    
    async def execute_email_search(self, question: str) -> Tuple[List[Dict], str]:
        """
        Execute a search for email correspondence.
        
        Args:
            question: The user's question about emails
            
        Returns:
            Tuple of (documents, search_strategy_used)
        """
        try:
            # Extract project/client context for email search
            context = await self._extract_email_search_context(question)
            logger.info(f"Searching emails with context: {context}")
            
            # Build email-focused search
            email_terms = ["email", "correspondence", "message", "communication"]
            if context.get('project'):
                email_terms.append(context['project'])
            if context.get('client'):
                email_terms.append(context['client'])
                
            search_query = " AND ".join(email_terms[:3])  # Limit to avoid over-complexity
            
            results = self.search_client.search(
                search_text=search_query,
                top=10,
                search_mode="all"
            )
            
            documents = list(results)
            return documents, f"email_search_{context.get('type', 'general')}"
            
        except Exception as e:
            logger.error("Email search failed", error=str(e))
            return [], "email_search_failed"
    
    async def execute_client_info_search(self, question: str) -> Tuple[List[Dict], str]:
        """
        Execute a search for client information and contacts.
        
        Args:
            question: The user's question about client info
            
        Returns:
            Tuple of (documents, search_strategy_used)
        """
        try:
            # Extract client name/project context
            client_context = await self._extract_client_context(question)
            logger.info(f"Searching client info: {client_context}")
            
            search_terms = ["contact", "client"]
            if client_context.get('client_name'):
                search_terms.append(client_context['client_name'])
            if client_context.get('project'):
                search_terms.append(client_context['project'])
                
            search_query = " AND ".join(search_terms)
            
            results = self.search_client.search(
                search_text=search_query,
                top=8,
                search_mode="all"
            )
            
            documents = list(results)
            return documents, f"client_info_search_{client_context.get('client_name', 'unknown')}"
            
        except Exception as e:
            logger.error("Client info search failed", error=str(e))
            return [], "client_info_search_failed"
    
    async def execute_scope_based_search(self, question: str) -> Tuple[List[Dict], str]:
        """
        Execute a search for projects with specific engineering scope.
        
        Args:
            question: The user's question about specific scope
            
        Returns:
            Tuple of (documents, search_strategy_used)
        """
        try:
            # Extract engineering scope keywords
            scope_terms = await self._extract_scope_terms(question)
            logger.info(f"Searching by engineering scope: {scope_terms}")
            
            # Build scope-focused search
            search_query = " OR ".join(scope_terms) if scope_terms else question
            
            results = self.search_client.search(
                search_text=search_query,
                top=15,
                search_mode="any",
                query_type="semantic"
            )
            
            documents = list(results)
            return documents, f"scope_search_{len(scope_terms)}_terms"
            
        except Exception as e:
            logger.error("Scope-based search failed", error=str(e))
            return [], "scope_search_failed"
    
    # Helper methods
    
    def _extract_project_number(self, question: str) -> Optional[str]:
        """Extract project number from question using regex patterns."""
        # Common DTCE project patterns: 225001, 224-050, project 225, etc.
        # Prioritize full project numbers first
        patterns = [
            r'\b(22[4-9]\d{3})\b',      # 224xxx, 225xxx format (e.g., 224001)
            r'\b(22[4-9]-\d{3})\b',      # 224-xxx format
            r'project\s+(2\d{5})',      # "project 225001"
            r'job\s+(2\d{5})',          # "job 225001"
            r'project\s+(\d{3})',       # "project 224" (year code)
            r'job\s+(\d{3})',           # "job 224" (year code)
        ]
        
        for pattern in patterns:
            match = re.search(pattern, question, re.IGNORECASE)
            if match:
                # Return the matched number, could be full project number or year code
                return match.group(1).replace('-', '')
        
        return None
    
    def _extract_document_type(self, question: str) -> Optional[str]:
        """Extract document type from template search question."""
        doc_types = [
            "PS1", "PS2", "PS3", "PS4",
            "geotech", "geotechnical",
            "structural", "seismic",
            "report", "letter", "memo",
            "calculation", "drawing",
            "specification", "tender"
        ]
        
        question_lower = question.lower()
        for doc_type in doc_types:
            if doc_type.lower() in question_lower:
                return doc_type
        
        return None
    
    async def _extract_engineering_keywords(self, question: str) -> List[str]:
        """Extract engineering-specific keywords using AI assistance."""
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "Extract engineering keywords from the question. Return only the technical terms as a comma-separated list."
                    },
                    {
                        "role": "user", 
                        "content": f"Question: {question}"
                    }
                ],
                max_tokens=100,
                temperature=0.1
            )
            
            keywords_text = response.choices[0].message.content.strip()
            keywords = [k.strip() for k in keywords_text.split(',') if k.strip()]
            return keywords[:5]  # Limit to 5 most relevant terms
            
        except Exception as e:
            logger.error("Keyword extraction failed", error=str(e))
            # Fallback to simple keyword extraction
            return self._simple_keyword_extraction(question)
    
    def _simple_keyword_extraction(self, question: str) -> List[str]:
        """Simple keyword extraction as fallback."""
        engineering_terms = [
            "steel", "concrete", "timber", "foundation", "retaining",
            "seismic", "structural", "geotechnical", "bridge", "building",
            "portal frame", "beam", "column", "slab", "wall"
        ]
        
        question_lower = question.lower()
        found_terms = [term for term in engineering_terms if term in question_lower]
        return found_terms[:5]
    
    async def _extract_email_search_context(self, question: str) -> Dict[str, str]:
        """Extract context for email searches."""
        context = {}
        
        # Extract project number
        project_num = self._extract_project_number(question)
        if project_num:
            context['project'] = project_num
            context['type'] = 'project_emails'
        
        # Look for client mentions
        if 'client' in question.lower():
            context['type'] = 'client_emails'
        
        return context
    
    async def _extract_client_context(self, question: str) -> Dict[str, str]:
        """Extract client context from questions."""
        context = {}
        
        # Extract project number for client lookup
        project_num = self._extract_project_number(question)
        if project_num:
            context['project'] = project_num
        
        # Look for explicit client names (this could be enhanced with a client database)
        client_indicators = ['NZTA', 'Council', 'Construction', 'Engineering', 'Ltd', 'Limited']
        question_words = question.split()
        
        for i, word in enumerate(question_words):
            if any(indicator in word for indicator in client_indicators):
                # Try to capture client name (current word + previous word if available)
                if i > 0:
                    context['client_name'] = f"{question_words[i-1]} {word}"
                else:
                    context['client_name'] = word
                break
        
        return context
    
    async def _extract_scope_terms(self, question: str) -> List[str]:
        """Extract engineering scope terms from question."""
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "Extract engineering scope and technical terms that would be useful for searching similar projects. Return as comma-separated list."
                    },
                    {
                        "role": "user", 
                        "content": f"Question: {question}"
                    }
                ],
                max_tokens=150,
                temperature=0.1
            )
            
            scope_text = response.choices[0].message.content.strip()
            scope_terms = [s.strip() for s in scope_text.split(',') if s.strip()]
            return scope_terms[:6]
            
        except Exception as e:
            logger.error("Scope extraction failed", error=str(e))
            return self._simple_keyword_extraction(question)
    
    async def _general_project_search(self, question: str) -> Tuple[List[Dict], str]:
        """General project search when specific project number not found."""
        try:
            results = self.search_client.search(
                search_text=question,
                top=10,
                query_type="semantic"
            )
            
            documents = list(results)
            return documents, "general_project_search"
            
        except Exception as e:
            logger.error("General project search failed", error=str(e))
            return [], "general_search_failed"
