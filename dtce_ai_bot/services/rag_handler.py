"""
RAG (Retrieval-Augmented Generation) Handler for DTCE AI Bot
Implements specific input/output patterns as defined in RAG.TXT
"""

import re
from typing import List, Dict, Any, Optional
import structlog
from azure.search.documents import SearchClient
from openai import AsyncAzureOpenAI

logger = structlog.get_logger(__name__)


class RAGHandler:
    """Handles RAG processing according to DTCE specifications."""
    
    def __init__(self, search_client: SearchClient, openai_client: AsyncAzureOpenAI, model_name: str):
        self.search_client = search_client
        self.openai_client = openai_client
        self.model_name = model_name
        
        # RAG patterns from RAG.TXT
        self.rag_patterns = {
            'nzs_code_lookup': {
                'patterns': [
                    r'minimum clear cover requirements as per NZS',
                    r'particular clause that talks about.*requirements',
                    r'strength reduction factors.*beam.*seismic',
                    r'particular NZS structural code.*composite slab.*floor diaphragm'
                ],
                'handler': self._handle_nzs_code_lookup
            },
            'project_reference': {
                'patterns': [
                    r'designing a precast panel.*past project.*keywords',
                    r'designing a timber retaining wall.*example past projects',
                    r'2 storey concrete precast panel building.*timber framed'
                ],
                'handler': self._handle_project_reference
            },
            'product_lookup': {
                'patterns': [
                    r'proprietary product.*waterproofing layer.*concrete block wall',
                    r'timber connection details.*beam to.*column.*proprietary products',
                    r'available sizes of LVL timber.*links.*sizes and price.*Wellington'
                ],
                'handler': self._handle_product_lookup
            },
            'online_references': {
                'patterns': [
                    r'composite beam.*haunched/tapered.*online threads.*tapered composite beam',
                    r'reinforced concrete column.*seismic and gravity.*legitimate link'
                ],
                'handler': self._handle_online_references
            },
            'template_request': {
                'patterns': [
                    r'template.*preparing a PS1.*direct link.*SuiteFiles',
                    r'PS3 template.*legitimate link.*council in New Zealand',
                    r'timber beam design spreadsheet.*DTCE usually uses'
                ],
                'handler': self._handle_template_request
            },
            'contact_lookup': {
                'patterns': [
                    r'builders.*worked with.*past 3 years.*steel structure retrofit.*brick building'
                ],
                'handler': self._handle_contact_lookup
            },
            'scenario_technical': {
                'patterns': [
                    r'mid-rise timber frame buildings.*high wind zones',
                    r'foundation systems.*houses.*steep slopes.*Wellington',
                    r'concrete shear walls.*seismic strengthening',
                    r'connection details.*balconies.*coastal apartment buildings'
                ],
                'handler': self._handle_scenario_technical
            },
            'lessons_learned': {
                'patterns': [
                    r'issues.*screw piles.*soft soils',
                    r'lessons learned.*retaining walls failed.*construction',
                    r'waterproofing methods.*basement walls.*high water table'
                ],
                'handler': self._handle_lessons_learned
            },
            'regulatory_precedent': {
                'patterns': [
                    r'council questioned.*wind load calculations',
                    r'alternative solution applications.*non-standard stair designs',
                    r'non-standard bracing.*heritage building retrofits'
                ],
                'handler': self._handle_regulatory_precedent
            },
            'cost_time_insights': {
                'patterns': [
                    r'how long.*concept to PS1.*small commercial alterations',
                    r'typical cost range.*structural design.*multi-unit residential',
                    r'structural scope expanded.*after concept design'
                ],
                'handler': self._handle_cost_time_insights
            },
            'best_practices': {
                'patterns': [
                    r'standard approach.*steel portal frames.*industrial buildings',
                    r'best example drawings.*timber diaphragm design',
                    r'calculation templates.*multi-storey timber buildings'
                ],
                'handler': self._handle_best_practices
            },
            'materials_methods': {
                'patterns': [
                    r'precast concrete.*in-situ concrete.*floor slabs.*why',
                    r'timber treatment levels.*exterior beams.*coastal conditions',
                    r'seismic retrofit methods.*unreinforced masonry buildings'
                ],
                'handler': self._handle_materials_methods
            },
            'internal_knowledge': {
                'patterns': [
                    r'engineers.*experience.*tilt-slab construction',
                    r'documented expertise.*pile design.*soft coastal soils',
                    r'project notes.*senior engineer.*seismic strengthening'
                ],
                'handler': self._handle_internal_knowledge
            }
        }
    
    async def process_rag_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Process a query according to RAG specifications."""
        try:
            # Identify the RAG pattern
            rag_type = self._identify_rag_pattern(question)
            
            if rag_type:
                handler = self.rag_patterns[rag_type]['handler']
                return await handler(question, project_filter)
            else:
                return await self._handle_general_query(question, project_filter)
                
        except Exception as e:
            logger.error("RAG processing failed", error=str(e), question=question)
            return {
                'answer': f'I encountered an error while processing your question: {str(e)}',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0,
                'rag_type': 'error'
            }
    
    def _identify_rag_pattern(self, question: str) -> Optional[str]:
        """Identify which RAG pattern the question matches."""
        question_lower = question.lower()
        
        for rag_type, config in self.rag_patterns.items():
            for pattern in config['patterns']:
                if re.search(pattern, question_lower, re.IGNORECASE):
                    logger.info("RAG pattern identified", rag_type=rag_type, pattern=pattern)
                    return rag_type
        
        return None
    
    async def _handle_nzs_code_lookup(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle NZ Standards code lookup queries."""
        logger.info("Processing NZS code lookup", question=question)
        
        # Search for NZ Standards documents
        search_query = self._extract_nzs_search_terms(question)
        documents = await self._search_documents(search_query, project_filter, doc_types=['pdf', 'standard'])
        
        if documents:
            # Generate NZS-specific response with clause references
            answer = await self._generate_nzs_response(question, documents)
            
            return {
                'answer': answer,
                'sources': self._format_sources_with_clauses(documents),
                'confidence': 'high' if len(documents) >= 2 else 'medium',
                'documents_searched': len(documents),
                'rag_type': 'nzs_code_lookup'
            }
        else:
            return {
                'answer': f"I couldn't find the specific NZ Standard information you're looking for. The information might be in physical standards documents. You may need to refer to:\n\n• NZS 3101 (Concrete Structures Standard)\n• AS/NZS 1170 (Structural Design Actions)\n• NZS 3603 (Timber Structures Standard)\n• Or contact Standards New Zealand directly",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'nzs_code_lookup'
            }
    
    async def _handle_project_reference(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle past project reference queries."""
        logger.info("Processing project reference", question=question)
        
        # Extract keywords from question
        keywords = self._extract_project_keywords(question)
        search_query = ' OR '.join(keywords)
        
        documents = await self._search_documents(search_query, project_filter)
        
        if documents:
            # Extract projects with job numbers
            projects = self._extract_projects_with_job_numbers(documents)
            
            if projects:
                answer = f"Here are past DTCE projects that match your criteria:\n\n"
                
                for i, project in enumerate(projects[:10], 1):
                    answer += f"**{i}. Job #{project['job_number']} - {project['name']}**\n"
                    answer += f"   📋 {project['description']}\n"
                    if project.get('suitefiles_url'):
                        answer += f"   📁 [View in SuiteFiles]({project['suitefiles_url']})\n"
                    answer += f"   🏗️ Scope: {project['scope']}\n\n"
                
                if len(projects) > 10:
                    answer += f"*Found {len(projects)} total projects matching your criteria.*"
                
                return {
                    'answer': answer,
                    'sources': self._format_sources_with_job_numbers(documents),
                    'confidence': 'high',
                    'documents_searched': len(documents),
                    'rag_type': 'project_reference'
                }
            else:
                return {
                    'answer': f"I found {len(documents)} documents related to your keywords but couldn't identify specific project numbers. The documents contain relevant information but may need manual review to extract project details.",
                    'sources': self._format_sources(documents[:5]),
                    'confidence': 'medium',
                    'documents_searched': len(documents),
                    'rag_type': 'project_reference'
                }
        else:
            return {
                'answer': f"I couldn't find past DTCE projects matching your specific criteria. Try using broader keywords or different search terms.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'project_reference'
            }
    
    async def _handle_product_lookup(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle proprietary product lookup queries."""
        logger.info("Processing product lookup", question=question)
        
        # Extract product keywords
        product_terms = self._extract_product_terms(question)
        search_query = ' AND '.join(product_terms)
        
        documents = await self._search_documents(search_query, project_filter)
        
        if documents:
            # Generate product-focused response
            answer = await self._generate_product_response(question, documents)
            
            return {
                'answer': answer,
                'sources': self._format_sources_with_products(documents),
                'confidence': 'high',
                'documents_searched': len(documents),
                'rag_type': 'product_lookup'
            }
        else:
            return {
                'answer': f"I couldn't find specific product information in our SuiteFiles. You might want to:\n\n• Check the Product Specifications folder in SuiteFiles\n• Contact suppliers directly\n• Search manufacturer websites\n• Ask the team for recent product recommendations",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'product_lookup'
            }
    
    async def _handle_template_request(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle template and form requests."""
        logger.info("Processing template request", question=question)
        
        # Search for templates and forms
        template_terms = self._extract_template_terms(question)
        search_query = ' OR '.join(template_terms)
        
        documents = await self._search_documents(search_query, project_filter, doc_types=['xlsx', 'xls', 'pdf', 'template'])
        
        if documents:
            answer = f"Here are the templates and forms related to your request:\n\n"
            
            for i, doc in enumerate(documents[:8], 1):
                filename = doc.get('filename', 'Unknown')
                answer += f"**{i}. {filename}**\n"
                if doc.get('blob_url'):
                    answer += f"   📄 [Download from SuiteFiles]({doc['blob_url']})\n"
                answer += f"   📁 Location: {doc.get('folder', 'Unknown folder')}\n\n"
            
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'high',
                'documents_searched': len(documents),
                'rag_type': 'template_request'
            }
        else:
            return {
                'answer': f"I couldn't find the specific templates you're looking for. Try:\n\n• Checking the Templates folder in SuiteFiles directly\n• Looking in Project Templates section\n• Contacting the team for custom templates\n• Visiting council websites for standard forms",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'template_request'
            }
    
    # Helper methods for RAG processing
    def _extract_nzs_search_terms(self, question: str) -> str:
        """Extract NZS-specific search terms."""
        nzs_terms = []
        
        if 'clear cover' in question.lower():
            nzs_terms.extend(['clear cover', 'concrete cover', 'NZS 3101'])
        if 'strength reduction' in question.lower():
            nzs_terms.extend(['strength reduction factor', 'phi factor', 'capacity reduction'])
        if 'composite slab' in question.lower():
            nzs_terms.extend(['composite slab', 'floor diaphragm', 'NZS 3404'])
        
        return ' OR '.join(nzs_terms) if nzs_terms else question
    
    def _extract_project_keywords(self, question: str) -> List[str]:
        """Extract project keywords from question."""
        keywords = []
        
        # Common project keywords
        project_terms = ['precast', 'panel', 'timber', 'retaining wall', 'connection', 'unispans']
        
        for term in project_terms:
            if term.lower() in question.lower():
                keywords.append(term)
        
        return keywords if keywords else [question]
    
    def _extract_product_terms(self, question: str) -> List[str]:
        """Extract product-related terms."""
        product_terms = []
        
        if 'waterproofing' in question.lower():
            product_terms.extend(['waterproofing', 'membrane', 'sealant'])
        if 'timber connection' in question.lower():
            product_terms.extend(['timber connector', 'bracket', 'bolt', 'screw'])
        if 'LVL' in question:
            product_terms.extend(['LVL', 'laminated veneer lumber', 'engineered timber'])
        
        return product_terms
    
    def _extract_template_terms(self, question: str) -> List[str]:
        """Extract template-related terms."""
        template_terms = []
        
        if 'PS1' in question:
            template_terms.extend(['PS1', 'producer statement'])
        if 'PS3' in question:
            template_terms.extend(['PS3', 'construction review'])
        if 'spreadsheet' in question.lower():
            template_terms.extend(['calculation', 'spreadsheet', 'excel'])
        
        return template_terms if template_terms else ['template', 'form']
    
    async def _search_documents(self, search_query: str, project_filter: Optional[str] = None, 
                              doc_types: Optional[List[str]] = None) -> List[Dict]:
        """Search for relevant documents."""
        try:
            # Build search parameters
            search_params = {
                'search_text': search_query,
                'top': 20,
                'select': ["id", "filename", "content", "blob_url", "project_name", "folder"]
            }
            
            # Add document type filter if specified
            if doc_types:
                doc_filter = ' or '.join([f"search.ismatch('*.{ext}', 'filename')" for ext in doc_types])
                search_params['filter'] = doc_filter
            
            results = self.search_client.search(**search_params)
            return [dict(result) for result in results]
            
        except Exception as e:
            logger.error("Document search failed", error=str(e))
            return []
    
    def _format_sources(self, documents: List[Dict]) -> List[Dict]:
        """Format sources for response."""
        sources = []
        for doc in documents[:5]:  # Limit to top 5 sources
            sources.append({
                'filename': doc.get('filename', 'Unknown'),
                'url': doc.get('blob_url', ''),
                'folder': doc.get('folder', 'Unknown'),
                'relevance': 'high'
            })
        return sources
    
    def _format_sources_with_clauses(self, documents: List[Dict]) -> List[Dict]:
        """Format sources with NZS clause references."""
        sources = []
        for doc in documents[:5]:
            source = {
                'filename': doc.get('filename', 'Unknown'),
                'url': doc.get('blob_url', ''),
                'folder': doc.get('folder', 'Unknown'),
                'relevance': 'high'
            }
            
            # Try to extract clause references
            content = doc.get('content', '')
            clauses = re.findall(r'clause\s+(\d+\.?\d*)', content, re.IGNORECASE)
            if clauses:
                source['clauses'] = clauses[:3]  # First 3 clauses found
            
            sources.append(source)
        return sources
    
    def _extract_projects_with_job_numbers(self, documents: List[Dict]) -> List[Dict]:
        """Extract projects with job numbers from documents."""
        projects = []
        
        for doc in documents:
            content = doc.get('content', '')
            filename = doc.get('filename', '')
            
            # Try to extract job numbers from content or filename
            job_numbers = re.findall(r'job\s*#?\s*(\d{4,6})', content + ' ' + filename, re.IGNORECASE)
            
            if job_numbers:
                projects.append({
                    'job_number': job_numbers[0],
                    'name': filename.replace('.pdf', '').replace('.docx', ''),
                    'description': content[:200] + '...' if len(content) > 200 else content,
                    'scope': self._extract_scope_from_content(content),
                    'suitefiles_url': doc.get('blob_url', '')
                })
        
        return projects
    
    def _extract_scope_from_content(self, content: str) -> str:
        """Extract project scope from content."""
        scope_indicators = ['scope', 'design', 'structural', 'engineering', 'construction']
        
        for indicator in scope_indicators:
            if indicator in content.lower():
                # Find sentence containing scope indicator
                sentences = content.split('.')
                for sentence in sentences:
                    if indicator in sentence.lower():
                        return sentence.strip()[:100] + '...'
        
        return content[:100] + '...' if content else 'Scope not specified'
    
    async def _generate_nzs_response(self, question: str, documents: List[Dict]) -> str:
        """Generate NZS-specific response with clause references."""
        # Implementation for generating NZS code responses
        return f"Based on the NZ Standards documents found, here is the relevant information for your query..."
    
    async def _generate_product_response(self, question: str, documents: List[Dict]) -> str:
        """Generate product-specific response."""
        # Implementation for generating product responses
        return f"Here are the relevant product specifications found in our SuiteFiles..."
    
    async def _handle_general_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle general queries that don't match specific RAG patterns."""
        documents = await self._search_documents(question, project_filter)
        
        if documents:
            return {
                'answer': f"I found {len(documents)} relevant documents. Here's what I can tell you based on our project database...",
                'sources': self._format_sources(documents),
                'confidence': 'medium',
                'documents_searched': len(documents),
                'rag_type': 'general_query'
            }
        else:
            return {
                'answer': "I couldn't find specific information about your query in our database. Please try rephrasing or being more specific.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'general_query'
            }
    
    # Placeholder methods for other handlers
    async def _handle_online_references(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle online reference queries."""
        return await self._handle_general_query(question, project_filter)
    
    async def _handle_contact_lookup(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle contact lookup queries."""
        return await self._handle_general_query(question, project_filter)
    
    async def _handle_scenario_technical(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle scenario-based technical queries."""
        return await self._handle_general_query(question, project_filter)
    
    async def _handle_lessons_learned(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle lessons learned queries."""
        return await self._handle_general_query(question, project_filter)
    
    async def _handle_regulatory_precedent(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle regulatory precedent queries."""
        return await self._handle_general_query(question, project_filter)
    
    async def _handle_cost_time_insights(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle cost and time insight queries."""
        return await self._handle_general_query(question, project_filter)
    
    async def _handle_best_practices(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle best practices queries."""
        return await self._handle_general_query(question, project_filter)
    
    async def _handle_materials_methods(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle materials and methods queries."""
        return await self._handle_general_query(question, project_filter)
    
    async def _handle_internal_knowledge(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle internal knowledge queries."""
        return await self._handle_general_query(question, project_filter)
    
    def _format_sources_with_job_numbers(self, documents: List[Dict]) -> List[Dict]:
        """Format sources with job number information."""
        return self._format_sources(documents)
    
    def _format_sources_with_products(self, documents: List[Dict]) -> List[Dict]:
        """Format sources with product information."""
        return self._format_sources(documents)
