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
        
        # RAG patterns from RAG.TXT - EXPANDED to cover ALL question types
        self.rag_patterns = {
            'nzs_code_lookup': {
                'patterns': [
                    r'minimum clear cover requirements.*NZS',
                    r'particular clause.*talks about.*requirements',
                    r'strength reduction factors.*beam.*seismic',
                    r'particular NZS structural code.*composite slab.*floor diaphragm',
                    r'NZS.*code.*refer.*to',
                    r'clause.*designing.*beam',
                    r'strength reduction.*seismic actions'
                ],
                'handler': self._handle_nzs_code_lookup
            },
            'project_reference': {
                'patterns': [
                    r'designing.*precast panel.*past project.*keywords',
                    r'designing.*timber retaining wall.*example past projects',
                    r'2.storey concrete precast panel building.*timber.framed',
                    r'past projects.*scope.*keywords',
                    r'DTCE has done.*in the past.*for',
                    r'provide.*example past projects'
                ],
                'handler': self._handle_project_reference
            },
            'product_lookup': {
                'patterns': [
                    r'proprietary product.*waterproofing layer.*concrete block wall',
                    r'timber connection details.*beam to.*column.*proprietary products',
                    r'available sizes.*LVL timber.*market.*links.*sizes and price',
                    r'proprietary.*DTCE.*used.*past',
                    r'specifications.*proprietary products.*DTCE.*refers',
                    r'LVL timber.*market.*Wellington'
                ],
                'handler': self._handle_product_lookup
            },
            'online_references': {
                'patterns': [
                    r'composite beam.*haunched.tapered.*online threads.*tapered composite beam',
                    r'reinforced concrete column.*seismic and gravity.*legitimate link',
                    r'online threads.*references.*structural design',
                    r'design guidelines.*legitimate link',
                    r'online.*references.*forums.*NZ'
                ],
                'handler': self._handle_online_references
            },
            'template_request': {
                'patterns': [
                    r'template.*preparing.*PS1.*direct link.*SuiteFiles',
                    r'PS3 template.*SuiteFiles.*legitimate link.*council.*New Zealand',
                    r'cannot find.*PS3.*SuiteFiles.*alternative.*link',
                    r'PS3.*template.*alternative.*source',
                    r'timber beam design spreadsheet.*DTCE.*uses',
                    r'template.*PS[1-4]',
                    r'calculation.*spreadsheet.*DTCE',
                    r'design.*spreadsheet.*timber'
                ],
                'handler': self._handle_template_request
            },
            'contact_lookup': {
                'patterns': [
                    r'builders.*worked with.*past.*years.*steel structure retrofit.*brick building',
                    r'companies.*contact details.*constructed.*design',
                    r'builders.*worked with.*before',
                    r'contact.*details.*built.*constructed'
                ],
                'handler': self._handle_contact_lookup
            },
            'scenario_technical': {
                'patterns': [
                    r'mid.rise timber frame buildings.*high wind zones',
                    r'foundation systems.*houses.*steep slopes.*Wellington',
                    r'concrete shear walls.*seismic strengthening',
                    r'connection details.*balconies.*coastal apartment buildings',
                    r'examples.*designed.*wind zones',
                    r'foundation.*steep slopes',
                    r'shear walls.*strengthening',
                    r'connection.*balconies.*coastal'
                ],
                'handler': self._handle_scenario_technical
            },
            'lessons_learned': {
                'patterns': [
                    r'issues.*screw piles.*soft soils',
                    r'lessons learned.*retaining walls failed.*construction',
                    r'waterproofing methods.*basement walls.*high water table',
                    r'issues.*run into.*using',
                    r'lessons learned.*projects.*failed',
                    r'methods.*worked best.*basement'
                ],
                'handler': self._handle_lessons_learned
            },
            'regulatory_precedent': {
                'patterns': [
                    r'projects.*council questioned.*wind load calculations',
                    r'alternative solution applications.*non.standard stair designs',
                    r'non.standard bracing.*heritage building retrofits',
                    r'council.*questioned.*calculations',
                    r'alternative.*applications.*stair',
                    r'precedent.*bracing.*heritage'
                ],
                'handler': self._handle_regulatory_precedent
            },
            'cost_time_insights': {
                'patterns': [
                    r'how long.*concept to PS1.*small commercial alterations',
                    r'typical cost range.*structural design.*multi.unit residential',
                    r'structural scope expanded.*after concept design',
                    r'how long.*take.*PS1',
                    r'cost.*range.*structural.*design',
                    r'scope.*expanded.*concept'
                ],
                'handler': self._handle_cost_time_insights
            },
            'best_practices': {
                'patterns': [
                    r'standard approach.*steel portal frames.*industrial buildings',
                    r'best example drawings.*timber diaphragm design',
                    r'calculation templates.*multi.storey timber buildings',
                    r'standard.*approach.*portal frames',
                    r'best.*drawings.*diaphragm',
                    r'calculation.*templates.*timber'
                ],
                'handler': self._handle_best_practices
            },
            'materials_methods': {
                'patterns': [
                    r'precast concrete.*in.situ concrete.*floor slabs.*why',
                    r'timber treatment levels.*exterior beams.*coastal conditions',
                    r'seismic retrofit methods.*unreinforced masonry buildings',
                    r'chosen.*precast.*in.situ.*why',
                    r'treatment.*levels.*coastal',
                    r'retrofit.*methods.*masonry'
                ],
                'handler': self._handle_materials_methods
            },
            'internal_knowledge': {
                'patterns': [
                    r'engineers.*experience.*tilt.slab construction',
                    r'documented expertise.*pile design.*soft coastal soils',
                    r'project notes.*senior engineer.*seismic strengthening',
                    r'engineers.*experience.*tilt',
                    r'expertise.*pile.*design',
                    r'notes.*engineer.*seismic'
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
        """Handle NZ Standards code lookup queries - Use GPT for natural language answers"""
        logger.info("Processing NZS code lookup", question=question)
        
        # Search for NZ Standards documents
        search_query = self._extract_nzs_search_terms(question)
        documents = await self._search_documents(search_query, project_filter, doc_types=['pdf', 'standard'])
        
        if documents:
            # Use GPT to generate natural language answer from documents
            answer = await self._generate_natural_answer(question, documents, "NZ Standards")
            
            return {
                'answer': answer,
                'sources': self._format_sources_with_clauses(documents),
                'confidence': 'high' if len(documents) >= 2 else 'medium',
                'documents_searched': len(documents),
                'rag_type': 'nzs_code_lookup'
            }
        else:
            return {
                'answer': "I couldn't find the specific NZ Standard information in our database. This information may not be uploaded to our system, or you may need to refer to the physical NZ Standards documents.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'nzs_code_lookup'
            }
    
    async def _handle_project_reference(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle past project reference queries - Use GPT for natural language answers"""
        logger.info("Processing project reference", question=question)
        
        # Extract keywords from question
        keywords = self._extract_project_keywords(question)
        search_query = ' OR '.join(keywords)
        
        documents = await self._search_documents(search_query, project_filter)
        
        if documents:
            # Use GPT to generate natural language answer about projects
            prompt = f"""Based on the project documents found, please answer this question about past DTCE projects: {question}

Focus on:
- Providing job numbers if found
- Including SuiteFiles links when available
- Describing relevant project scope and details
- Matching the keywords from the question"""
            
            answer = await self._generate_natural_answer(prompt, documents, "past DTCE projects")
            
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'high' if len(documents) >= 3 else 'medium',
                'documents_searched': len(documents),
                'rag_type': 'project_reference'
            }
        else:
            return {
                'answer': f"I couldn't find past DTCE projects matching your specific keywords in our database.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'project_reference'
            }
    
    async def _handle_product_lookup(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle proprietary product lookup queries - Use GPT for natural language answers"""
        logger.info("Processing product lookup", question=question)
        
        # Extract product keywords
        product_terms = self._extract_product_terms(question)
        search_query = ' AND '.join(product_terms)
        
        documents = await self._search_documents(search_query, project_filter)
        
        if documents:
            # Use GPT to generate natural language answer about products
            prompt = f"""Based on the documents found, please answer this question about products: {question}

Focus on:
- Product specifications and details
- Prioritizing information from SuiteFiles documents
- Including supplier information when available
- Mentioning alternative products if found"""
            
            answer = await self._generate_natural_answer(prompt, documents, "product specifications")
            
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'high',
                'documents_searched': len(documents),
                'rag_type': 'product_lookup'
            }
        else:
            return {
                'answer': "I couldn't find specific proprietary product information in our SuiteFiles database for your query.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'product_lookup'
            }
    
    async def _handle_template_request(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle template and form requests - Use GPT for natural language answers"""
        logger.info("Processing template request", question=question)
        
        # Search for templates and forms
        template_terms = self._extract_template_terms(question)
        search_query = ' OR '.join(template_terms)
        
        documents = await self._search_documents(search_query, project_filter, doc_types=['xlsx', 'xls', 'pdf', 'doc', 'docx'])
        
        if documents:
            # Filter for actual templates/forms
            template_docs = [doc for doc in documents if self._is_template_document(doc)]
            
            if template_docs:
                # Use GPT to generate natural language answer about templates
                # Include guidance for alternative sources when SuiteFiles isn't accessible
                prompt = f"""Based on the templates and forms found, please answer: {question}

Context: The user is asking about templates/forms, and we found relevant documents in SuiteFiles.

Instructions for your response:
- Provide direct links to templates found in SuiteFiles
- Explain what each template is for and its location
- If the user mentions they cannot access SuiteFiles or need alternatives, also suggest:
  * Engineering New Zealand (ENZ) website for official PS templates
  * MBIE website for government-approved templates  
  * Local council websites for council-specific formats
- Focus primarily on the SuiteFiles documents found, but mention alternatives if accessibility is an issue

Documents found: {len(template_docs)} templates"""
                
                answer = await self._generate_natural_answer(prompt, template_docs, "templates and forms")
                
                return {
                    'answer': answer,
                    'sources': self._format_sources(template_docs),
                    'confidence': 'high',
                    'documents_searched': len(documents),
                    'rag_type': 'template_request'
                }
            else:
                # GPT generates response about found documents even if not templates
                prompt = f"""The user asked: {question}

We found {len(documents)} documents but they don't appear to be templates/forms. Please provide a helpful response suggesting:
1. What we found instead
2. Alternative sources for templates like Engineering New Zealand or MBIE
3. Suggestions for finding the specific templates they need"""
                
                answer = await self._generate_natural_answer(prompt, documents[:3], "related documents")
                
                return {
                    'answer': answer,
                    'sources': self._format_sources(documents[:3]),
                    'confidence': 'medium',
                    'documents_searched': len(documents),
                    'rag_type': 'template_request'
                }
        else:
            # GPT generates helpful response even when no documents found
            prompt = f"""The user asked: {question}

No relevant documents were found in our SuiteFiles database. Please provide a helpful response that:
1. Acknowledges we couldn't find the templates in SuiteFiles
2. Suggests official alternative sources:
   - Engineering New Zealand (ENZ) for official Producer Statement templates
   - MBIE website for government-approved building templates
   - Local council websites for council-specific formats
3. Explains what the template is typically used for (if it's a PS1, PS3, etc.)
4. Maintains a helpful, professional tone

Focus on providing genuine value even without internal documents."""
            
            # Use GPT even with no documents - it can still provide valuable guidance
            answer = await self._generate_natural_answer(prompt, [], "external sources")
            
            return {
                'answer': answer,
                'sources': [],
                'confidence': 'medium',
                'documents_searched': 0,
                'rag_type': 'template_request_external_guidance'
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
                'url': self._convert_to_suitefiles_url(doc.get('blob_url', '')) or doc.get('blob_url', ''),
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
                'url': self._convert_to_suitefiles_url(doc.get('blob_url', '')) or doc.get('blob_url', ''),
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
                    'suitefiles_url': self._convert_to_suitefiles_url(doc.get('blob_url', '')) or doc.get('blob_url', '')
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
    
    async def _generate_natural_answer(self, question: str, documents: List[Dict], context_type: str) -> str:
        """Generate natural language answer using GPT based on documents found"""
        try:
            # Prepare context from documents
            context_parts = []
            for doc in documents[:10]:  # Limit to top 10 documents
                content = doc.get('content', '')
                filename = doc.get('filename', 'Unknown')
                blob_url = doc.get('blob_url', '')
                
                if content:
                    context_part = f"**Document: {filename}**\n{content[:1000]}..."
                    if blob_url:
                        suitefiles_url = self._convert_to_suitefiles_url(blob_url) or blob_url
                        context_part += f"\nSuiteFiles URL: {suitefiles_url}"
                        context_part += f"\nTo include in response format as: [{filename}]({suitefiles_url})"
                    context_parts.append(context_part)
            
            if not context_parts:
                return f"I couldn't find specific information about '{question}' in our database."
            
            context = "\n\n".join(context_parts)
            
            # Create prompt for GPT
            prompt = f"""You are the DTCE AI Assistant. Based on the following documents from our engineering database, please provide a comprehensive answer to this question: {question}

Context from {context_type}:
{context}

CRITICAL INSTRUCTIONS:
- Provide a natural, conversational answer based on DTCE's engineering expertise
- ONLY use information that is explicitly provided in the context above
- NEVER create, invent, or make up project numbers, job numbers, or file names that aren't in the context
- When URLs are provided in the context, include them as clickable links in your response
- If documents show only "Document: filename" content, acknowledge this limitation
- Include specific details from the documents when available
- If the documents contain partial information, be honest about limitations
- Focus on practical engineering guidance for New Zealand conditions
- When relevant, mention SuiteFiles as the primary document repository
- For technical queries, emphasize DTCE's experience and methodology
- Keep the response professional but approachable

LINK HANDLING:
- When a URL is provided in the context, format it as: [Document Name](URL)
- If user asks for links but no URLs are available in context, explain that links aren't available
- Only include URLs that are explicitly provided in the document context above

For engineering queries about:
- **Past Projects**: Reference specific job folders and project details when available
- **Technical Methods**: Describe DTCE's standard approaches and lessons learned
- **Products/Materials**: Prioritize specifications used in past DTCE projects
- **Design Standards**: Reference NZ structural codes and local conditions
- **SuiteFiles Links**: When URLs are provided, format them as clickable links

Answer:"""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are an expert engineering assistant for DTCE. Provide clear, practical answers based on the document context provided."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error("Failed to generate natural answer", error=str(e))
            return f"I found relevant documents but encountered an error generating a response. Please try rephrasing your question."
    
    async def _generate_product_specifications_response(self, question: str, documents: List[Dict]) -> str:
        """Generate product specifications response prioritizing SuiteFiles as per RAG.TXT"""
        suitefiles_docs = [doc for doc in documents if 'suitefiles' in doc.get('blob_url', '').lower()]
        other_docs = [doc for doc in documents if 'suitefiles' not in doc.get('blob_url', '').lower()]
        
        response = "Product specifications found in SuiteFiles:\n\n"
        
        # Prioritize SuiteFiles documents
        for i, doc in enumerate(suitefiles_docs[:5], 1):
            response += f"{i}. **{doc.get('filename', 'Unknown')}**\n"
            suitefiles_url = self._convert_to_suitefiles_url(doc.get('blob_url', '')) or doc.get('blob_url', '')
            response += f"   📄 [View in SuiteFiles]({suitefiles_url})\n"
            content = doc.get('content', '')[:200]
            if content:
                response += f"   Summary: {content}...\n\n"
        
        if other_docs:
            response += "\nAlternative products found online:\n\n"
            for i, doc in enumerate(other_docs[:3], 1):
                response += f"{i}. **{doc.get('filename', 'Unknown')}**\n"
                if doc.get('blob_url'):
                    suitefiles_url = self._convert_to_suitefiles_url(doc.get('blob_url', '')) or doc.get('blob_url', '')
                    response += f"   🔗 [Product link]({suitefiles_url})\n\n"
        
        return response
    
    async def _generate_online_references_response(self, question: str, documents: List[Dict]) -> str:
        """Generate online references response as per RAG.TXT"""
        response = "Relevant references and discussions found:\n\n"
        
        for i, doc in enumerate(documents[:5], 1):
            filename = doc.get('filename', 'Unknown')
            url = self._convert_to_suitefiles_url(doc.get('blob_url', '')) or doc.get('blob_url', '')
            content = doc.get('content', '')[:150]
            
            response += f"{i}. **{filename}**\n"
            if url:
                response += f"   🔗 [Access reference]({url})\n"
            if content:
                response += f"   Summary: {content}...\n\n"
        
        return response
    
    def _extract_builder_contacts(self, documents: List[Dict]) -> List[Dict]:
        """Extract builder/contractor contact information"""
        contacts = []
        
        for doc in documents:
            content = doc.get('content', '')
            filename = doc.get('filename', '')
            
            # Look for company names and contact info
            import re
            company_patterns = [
                r'([A-Z][a-z]+ Construction)',
                r'([A-Z][a-z]+ Builders?)',
                r'([A-Z][a-z]+ Ltd)',
                r'([A-Z][a-z]+ Limited)'
            ]
            
            for pattern in company_patterns:
                matches = re.findall(pattern, content + ' ' + filename)
                for match in matches:
                    contacts.append({
                        'company': match,
                        'contact_info': self._extract_contact_info(content),
                        'project_references': filename
                    })
        
        return contacts[:10]  # Limit to 10 contacts
    
    def _extract_contact_info(self, content: str) -> str:
        """Extract contact information from content"""
        import re
        
        # Look for phone numbers and emails
        phone_pattern = r'(\d{2,3}[-\s]?\d{3}[-\s]?\d{4})'
        email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        
        phones = re.findall(phone_pattern, content)
        emails = re.findall(email_pattern, content)
        
        contact_info = []
        if phones:
            contact_info.append(f"Phone: {phones[0]}")
        if emails:
            contact_info.append(f"Email: {emails[0]}")
        
        return " | ".join(contact_info) if contact_info else "Contact details not found"
    
    def _is_template_document(self, doc: Dict) -> bool:
        """Check if document is actually a template/form"""
        filename = doc.get('filename', '').lower()
        template_keywords = ['template', 'form', 'ps1', 'ps2', 'ps3', 'ps4', 'calculation', 'spreadsheet']
        
        return any(keyword in filename for keyword in template_keywords)
    
    def _extract_online_reference_keywords(self, question: str) -> List[str]:
        """Extract keywords for online reference searches"""
        # Extract technical terms from the question
        technical_terms = []
        
        if 'composite beam' in question.lower():
            technical_terms.extend(['composite beam', 'steel concrete composite'])
        if 'haunched' in question.lower() or 'tapered' in question.lower():
            technical_terms.extend(['haunched beam', 'tapered beam'])
        if 'concrete column' in question.lower():
            technical_terms.extend(['concrete column', 'reinforced concrete'])
        if 'seismic' in question.lower():
            technical_terms.append('seismic design')
        
        return technical_terms if technical_terms else [question]
    
    # Additional helper methods for comprehensive RAG support
    def _extract_scenario_keywords(self, question: str) -> List[str]:
        """Extract scenario-specific keywords"""
        keywords = []
        
        if 'mid-rise' in question.lower() and 'timber' in question.lower():
            keywords.extend(['mid-rise', 'timber', 'wind'])
        if 'foundation' in question.lower() and 'steep' in question.lower():
            keywords.extend(['foundation', 'steep', 'slope'])
        if 'shear wall' in question.lower():
            keywords.extend(['shear wall', 'seismic'])
        if 'balcony' in question.lower() and 'coastal' in question.lower():
            keywords.extend(['balcony', 'coastal', 'connection'])
        
        return keywords if keywords else ['building', 'design']
    
    def _extract_issue_keywords(self, question: str) -> List[str]:
        """Extract issue/problem keywords"""
        keywords = []
        
        if 'screw pile' in question.lower():
            keywords.extend(['screw pile', 'soft soil'])
        if 'retaining wall' in question.lower() and 'fail' in question.lower():
            keywords.extend(['retaining wall', 'failure'])
        if 'waterproofing' in question.lower() and 'basement' in question.lower():
            keywords.extend(['waterproofing', 'basement'])
        
        return keywords if keywords else ['issue', 'problem']
    
    def _extract_regulatory_keywords(self, question: str) -> List[str]:
        """Extract regulatory-specific keywords"""
        keywords = []
        
        if 'council' in question.lower() and 'wind load' in question.lower():
            keywords.extend(['council', 'wind load'])
        if 'alternative solution' in question.lower():
            keywords.extend(['alternative solution', 'stair'])
        if 'heritage' in question.lower() and 'bracing' in question.lower():
            keywords.extend(['heritage', 'bracing'])
        
        return keywords if keywords else ['council', 'consent']
    
    def _extract_cost_time_keywords(self, question: str) -> List[str]:
        """Extract cost/time related keywords"""
        keywords = []
        
        if 'PS1' in question and 'long' in question.lower():
            keywords.extend(['PS1', 'timeline'])
        if 'cost' in question.lower() and 'residential' in question.lower():
            keywords.extend(['cost', 'residential'])
        if 'scope' in question.lower() and 'expand' in question.lower():
            keywords.extend(['scope', 'expansion'])
        
        return keywords if keywords else ['project', 'timeline']
    
    def _extract_practice_keywords(self, question: str) -> List[str]:
        """Extract best practice keywords"""
        keywords = []
        
        if 'portal frame' in question.lower():
            keywords.extend(['portal frame', 'steel'])
        if 'diaphragm' in question.lower():
            keywords.extend(['diaphragm', 'timber'])
        if 'multi-storey' in question.lower() and 'timber' in question.lower():
            keywords.extend(['multi-storey', 'timber'])
        
        return keywords if keywords else ['standard', 'approach']
    
    def _extract_material_keywords(self, question: str) -> List[str]:
        """Extract material comparison keywords"""
        keywords = []
        
        if 'precast' in question.lower() and 'in-situ' in question.lower():
            keywords.extend(['precast', 'in-situ'])
        if 'treatment' in question.lower() and 'coastal' in question.lower():
            keywords.extend(['treatment', 'coastal'])
        if 'retrofit' in question.lower() and 'masonry' in question.lower():
            keywords.extend(['retrofit', 'masonry'])
        
        return keywords if keywords else ['material', 'method']
    
    def _extract_expertise_keywords(self, question: str) -> List[str]:
        """Extract expertise area keywords"""
        keywords = []
        
        if 'tilt-slab' in question.lower():
            keywords.extend(['tilt-slab', 'construction'])
        if 'pile' in question.lower() and 'soil' in question.lower():
            keywords.extend(['pile', 'soil'])
        if 'seismic' in question.lower() and 'strengthen' in question.lower():
            keywords.extend(['seismic', 'strengthening'])
        
        return keywords if keywords else ['engineer', 'expertise']
    
    # Data extraction methods
    def _extract_projects_with_scenarios(self, documents: List[Dict], keywords: List[str]) -> List[Dict]:
        """Extract projects matching scenario criteria"""
        projects = []
        
        for doc in documents:
            content = doc.get('content', '')
            filename = doc.get('filename', '')
            
            # Look for job numbers and scenario matches
            import re
            job_numbers = re.findall(r'(\d{4,6})', content + ' ' + filename)
            
            if job_numbers:
                scenario_match = ', '.join([kw for kw in keywords if kw.lower() in content.lower()])
                
                projects.append({
                    'job_number': job_numbers[0],
                    'name': filename.replace('.pdf', '').replace('.docx', ''),
                    'scenario_match': scenario_match or 'Keywords found in document',
                    'details': content[:150] + '...' if content else 'Details in linked document',
                    'suitefiles_url': self._convert_to_suitefiles_url(doc.get('blob_url', '')) or doc.get('blob_url', '')
                })
        
        return projects[:10]
    
    def _extract_lessons_from_documents(self, documents: List[Dict]) -> List[Dict]:
        """Extract lessons learned from documents"""
        lessons = []
        
        for doc in documents:
            content = doc.get('content', '')
            filename = doc.get('filename', '')
            
            import re
            job_numbers = re.findall(r'(\d{4,6})', content + ' ' + filename)
            
            # Look for lesson-related content
            if any(word in content.lower() for word in ['issue', 'problem', 'lesson', 'failure']):
                lessons.append({
                    'issue': self._extract_issue_description(content),
                    'job_number': job_numbers[0] if job_numbers else 'Unknown',
                    'lesson_learned': self._extract_lesson_content(content),
                    'solution': self._extract_solution_content(content)
                })
        
        return lessons[:10]
    
    def _extract_regulatory_precedents(self, documents: List[Dict]) -> List[Dict]:
        """Extract regulatory precedents from documents"""
        precedents = []
        
        for doc in documents:
            content = doc.get('content', '')
            filename = doc.get('filename', '')
            
            import re
            job_numbers = re.findall(r'(\d{4,6})', content + ' ' + filename)
            
            if any(word in content.lower() for word in ['council', 'consent', 'alternative']):
                precedents.append({
                    'council_issue': self._extract_council_issue(content),
                    'job_number': job_numbers[0] if job_numbers else 'Unknown',
                    'council': self._extract_council_name(content),
                    'resolution': self._extract_resolution(content)
                })
        
        return precedents[:10]
    
    def _extract_cost_time_insights(self, documents: List[Dict]) -> List[Dict]:
        """Extract cost and time insights"""
        insights = []
        
        for doc in documents:
            content = doc.get('content', '')
            
            if any(word in content.lower() for word in ['cost', 'time', 'duration', 'PS1']):
                insights.append({
                    'project_type': self._extract_project_type(content),
                    'timeline': self._extract_timeline_info(content),
                    'cost_range': self._extract_cost_info(content),
                    'examples': content[:100] + '...'
                })
        
        return insights[:8]
    
    def _extract_best_practices(self, documents: List[Dict]) -> List[Dict]:
        """Extract best practices from documents"""
        practices = []
        
        for doc in documents:
            content = doc.get('content', '')
            
            if any(word in content.lower() for word in ['standard', 'approach', 'practice', 'method']):
                practices.append({
                    'practice_area': self._extract_practice_area(content),
                    'approach': self._extract_approach_description(content),
                    'considerations': self._extract_considerations(content),
                    'examples': content[:100] + '...'
                })
        
        return practices[:8]
    
    def _extract_material_comparisons(self, documents: List[Dict]) -> List[Dict]:
        """Extract material and method comparisons"""
        comparisons = []
        
        for doc in documents:
            content = doc.get('content', '')
            
            if any(word in content.lower() for word in ['compare', 'vs', 'versus', 'choose']):
                comparisons.append({
                    'comparison_type': self._extract_comparison_type(content),
                    'factors': self._extract_decision_factors(content),
                    'option_a_criteria': 'See document for detailed criteria',
                    'option_b_criteria': 'See document for detailed criteria',
                    'examples': content[:100] + '...'
                })
        
        return comparisons[:8]
    
    def _extract_internal_expertise(self, documents: List[Dict]) -> List[Dict]:
        """Extract internal expertise information"""
        expertise = []
        
        for doc in documents:
            content = doc.get('content', '')
            filename = doc.get('filename', '')
            
            # Look for engineer names and expertise areas
            if any(word in content.lower() for word in ['engineer', 'design', 'experience']):
                expertise.append({
                    'expertise_area': self._extract_expertise_area(content),
                    'engineers': self._extract_engineer_names(content),
                    'experience': 'Detailed in project documents',
                    'projects': filename.replace('.pdf', '').replace('.docx', '')
                })
        
        return expertise[:10]
    
    # Simple text extraction helpers
    def _extract_issue_description(self, content: str) -> str:
        sentences = content.split('.')
        for sentence in sentences:
            if any(word in sentence.lower() for word in ['issue', 'problem']):
                return sentence.strip()[:100] + '...'
        return 'Issue described in document'
    
    def _extract_lesson_content(self, content: str) -> str:
        return 'Lesson learned details in project documentation'
    
    def _extract_solution_content(self, content: str) -> str:
        return 'Solution approach documented in project files'
    
    def _extract_council_issue(self, content: str) -> str:
        return 'Council interaction details in project documentation'
    
    def _extract_council_name(self, content: str) -> str:
        councils = ['Wellington', 'Auckland', 'Christchurch', 'Hamilton']
        for council in councils:
            if council.lower() in content.lower():
                return f"{council} City Council"
        return 'Council details in documentation'
    
    def _extract_resolution(self, content: str) -> str:
        return 'Resolution details in project files'
    
    def _extract_project_type(self, content: str) -> str:
        if 'commercial' in content.lower():
            return 'Commercial project'
        elif 'residential' in content.lower():
            return 'Residential project'
        return 'Project type in documentation'
    
    def _extract_timeline_info(self, content: str) -> str:
        import re
        timeline_match = re.search(r'(\d+)\s*(week|month|day)', content.lower())
        if timeline_match:
            return f"{timeline_match.group(1)} {timeline_match.group(2)}s"
        return 'Timeline details in documentation'
    
    def _extract_cost_info(self, content: str) -> str:
        import re
        cost_match = re.search(r'\$(\d+,?\d*)', content)
        if cost_match:
            return f"${cost_match.group(1)} range"
        return 'Cost details in documentation'
    
    def _extract_practice_area(self, content: str) -> str:
        if 'portal frame' in content.lower():
            return 'Steel portal frame design'
        elif 'diaphragm' in content.lower():
            return 'Timber diaphragm design'
        return 'Practice area in documentation'
    
    def _extract_approach_description(self, content: str) -> str:
        return 'Detailed approach described in documentation'
    
    def _extract_considerations(self, content: str) -> str:
        return 'Key considerations outlined in project files'
    
    def _extract_comparison_type(self, content: str) -> str:
        if 'precast' in content.lower() and 'in-situ' in content.lower():
            return 'Precast vs in-situ concrete'
        elif 'treatment' in content.lower():
            return 'Timber treatment comparison'
        return 'Material/method comparison in documentation'
    
    def _extract_decision_factors(self, content: str) -> str:
        return 'Decision factors detailed in project documentation'
    
    def _extract_expertise_area(self, content: str) -> str:
        if 'tilt-slab' in content.lower():
            return 'Tilt-slab construction'
        elif 'pile' in content.lower():
            return 'Pile design'
        return 'Expertise area from project work'
    
    def _extract_engineer_names(self, content: str) -> str:
        # For privacy, don't extract actual names
        return 'Engineer details in project documentation'
    
    def _extract_projects_with_job_numbers(self, documents: List[Dict]) -> List[Dict]:
        """Extract projects with job numbers from documents - Enhanced for RAG compliance"""
        projects = []
        
        for doc in documents:
            content = doc.get('content', '')
            filename = doc.get('filename', '')
            blob_url = doc.get('blob_url', '')
            
            # Enhanced job number extraction
            import re
            job_patterns = [
                r'job\s*#?\s*(\d{4,6})',
                r'project\s*#?\s*(\d{4,6})',
                r'(\d{6})',  # 6-digit numbers often job numbers
                r'DTT?E[-\s]?(\d{4,6})'  # DTCE project numbers
            ]
            
            job_numbers = []
            for pattern in job_patterns:
                matches = re.findall(pattern, content + ' ' + filename, re.IGNORECASE)
                job_numbers.extend(matches)
            
            if job_numbers:
                # Extract keywords that were found
                keywords_found = self._find_matching_keywords(content + ' ' + filename)
                
                projects.append({
                    'job_number': job_numbers[0],  # Take first job number found
                    'name': filename.replace('.pdf', '').replace('.docx', ''),
                    'description': content[:200] + '...' if len(content) > 200 else content,
                    'scope': self._extract_scope_from_content(content),
                    'suitefiles_url': self._convert_to_suitefiles_url(blob_url) or blob_url,
                    'keywords_found': ', '.join(keywords_found)
                })
        
        return projects
    
    def _find_matching_keywords(self, text: str) -> List[str]:
        """Find matching keywords in text"""
        common_keywords = [
            'precast', 'panel', 'timber', 'retaining wall', 'connection', 
            'unispans', 'concrete', 'steel', 'seismic', 'foundation'
        ]
        
        found_keywords = []
        text_lower = text.lower()
        
        for keyword in common_keywords:
            if keyword in text_lower:
                found_keywords.append(keyword)
        
        return found_keywords[:5]  # Limit to 5 keywords
    
    async def _handle_general_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle general queries that don't match specific RAG patterns."""
        # If no specific RAG pattern is found, return general_query type
        # The DocumentQAService will handle this as a "no pattern match"
        
        return {
            'answer': "No specific RAG pattern matched",
            'sources': [],
            'confidence': 'low',
            'documents_searched': 0,
            'rag_type': 'general_query'
        }
    
    # Update placeholder methods to use natural language generation
    async def _handle_online_references(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle online reference queries - Use GPT for natural language answers"""
        logger.info("Processing online references", question=question)
        
        keywords = self._extract_online_reference_keywords(question)
        documents = await self._search_documents(' OR '.join(keywords), project_filter)
        
        if documents:
            prompt = f"""Based on the documents found, please answer: {question}

Focus on:
- Providing relevant references and design guidance
- Including links when available
- Explaining design procedures and best practices"""
            
            answer = await self._generate_natural_answer(prompt, documents, "design references")
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'medium',
                'documents_searched': len(documents),
                'rag_type': 'online_references'
            }
        else:
            return {
                'answer': "I couldn't find relevant design references in our database. You may need to search engineering forums or technical communities directly.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'online_references'
            }
    
    async def _handle_contact_lookup(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle contact lookup queries - Use GPT for natural language answers"""
        logger.info("Processing contact lookup", question=question)
        
        search_terms = ['builder', 'contractor', 'construction', 'contact', 'company']
        search_query = ' OR '.join(search_terms)
        documents = await self._search_documents(search_query, project_filter)
        
        if documents:
            prompt = f"""Based on the project documents found, please answer: {question}

Focus on:
- Builder and contractor information
- Contact details when available
- Project performance and quality
- Relevant project references"""
            
            answer = await self._generate_natural_answer(prompt, documents, "project contacts")
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'medium',
                'documents_searched': len(documents),
                'rag_type': 'contact_lookup'
            }
        else:
            return {
                'answer': "I couldn't find builder/contractor contact information in our database.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'contact_lookup'
            }
    
    async def _handle_scenario_technical(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle scenario-based technical queries with enhanced DTCE methodology"""
        logger.info("Processing scenario technical", question=question)
        
        # Extract technical scenario keywords with enhanced terms
        scenario_keywords = self._extract_scenario_keywords(question)
        
        # Add common engineering terms for better search
        enhanced_keywords = scenario_keywords + [
            'structural', 'design', 'engineering', 'analysis', 'drawings', 
            'calculations', 'report', 'specifications', 'details'
        ]
        
        documents = await self._search_documents(' OR '.join(enhanced_keywords), project_filter, limit=15)
        
        if documents:
            prompt = f"""Based on the DTCE project documents found, please answer: {question}

**DTCE Engineering Approach Guidelines:**

For scenario-based technical queries, structure your response as follows:

1. **Project Examples**: List specific DTCE projects that match the scenario (if found in documents)
   - Include job numbers or project names mentioned in the documents
   - Describe the project scope and technical solutions used
   - Reference the document sources

2. **Technical Solutions**: Describe DTCE's engineering approaches
   - Design methodologies and standards followed
   - Material specifications and connection details
   - Analysis methods and software used

3. **Design Considerations**: Highlight key factors
   - New Zealand building code requirements (NZS standards)
   - Local environmental conditions (wind, seismic, soil)
   - Construction practicalities and detailing

4. **SuiteFiles References**: Direct users to relevant documentation
   - Project folders containing similar designs
   - Standard detail drawings and templates
   - Calculation spreadsheets and methodologies

**Important**: If documents only show "Document: filename" content, explain that full content extraction is being improved and suggest checking SuiteFiles directly for complete project information.

Focus on practical engineering guidance for New Zealand conditions and DTCE's proven methodologies."""
            
            answer = await self._generate_natural_answer(prompt, documents, "DTCE technical projects")
            return {
                'answer': answer,
                'sources': self._format_sources_with_suitefiles(documents),
                'confidence': 'high' if len(documents) >= 5 else 'medium',
                'documents_searched': len(documents),
                'rag_type': 'scenario_technical',
                'query_type': 'Technical Scenario Analysis'
            }
        else:
            return {
                'answer': self._generate_fallback_technical_response(question),
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'scenario_technical',
                'query_type': 'Technical Scenario Analysis - No Specific Documents Found'
            }
    
    async def _handle_lessons_learned(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle lessons learned queries - Use GPT for natural language answers"""
        logger.info("Processing lessons learned", question=question)
        
        lessons_keywords = self._extract_lessons_keywords(question)
        documents = await self._search_documents(' OR '.join(lessons_keywords), project_filter)
        
        if documents:
            prompt = f"""Based on the DTCE project documents found, please answer: {question}

Focus on:
- Issues and problems encountered
- Lessons learned and solutions
- Best practices developed
- Recommendations for future projects"""
            
            answer = await self._generate_natural_answer(prompt, documents, "lessons learned")
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'high',
                'documents_searched': len(documents),
                'rag_type': 'lessons_learned'
            }
        else:
            return {
                'answer': "I couldn't find specific lessons learned matching your query in our database.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'lessons_learned'
            }
    
    async def _handle_regulatory_precedent(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle regulatory precedent queries - Use GPT for natural language answers"""
        logger.info("Processing regulatory precedent", question=question)
        
        regulatory_keywords = self._extract_regulatory_keywords(question)
        documents = await self._search_documents(' OR '.join(regulatory_keywords), project_filter)
        
        if documents:
            prompt = f"""Based on the DTCE project documents found, please answer: {question}

Focus on:
- Council approvals and precedents
- Regulatory challenges and solutions
- Alternative solution applications
- Consent processes and outcomes"""
            
            answer = await self._generate_natural_answer(prompt, documents, "regulatory precedents")
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'medium',
                'documents_searched': len(documents),
                'rag_type': 'regulatory_precedent'
            }
        else:
            return {
                'answer': "I couldn't find specific regulatory precedents matching your query in our database.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'regulatory_precedent'
            }
    
    async def _handle_cost_time_insights(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle cost and time insight queries - Use GPT for natural language answers"""
        logger.info("Processing cost time insights", question=question)
        
        cost_time_keywords = self._extract_cost_time_keywords(question)
        documents = await self._search_documents(' OR '.join(cost_time_keywords), project_filter)
        
        if documents:
            prompt = f"""Based on the DTCE project documents found, please answer: {question}

Focus on:
- Project timelines and durations
- Cost information and estimates
- Scope changes and expansion
- Efficiency insights and recommendations"""
            
            answer = await self._generate_natural_answer(prompt, documents, "cost and time insights")
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'medium',
                'documents_searched': len(documents),
                'rag_type': 'cost_time_insights'
            }
        else:
            return {
                'answer': "I couldn't find specific cost and time insights matching your query in our database.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'cost_time_insights'
            }
    
    async def _handle_best_practices(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle best practices queries - Use GPT for natural language answers"""
        logger.info("Processing best practices", question=question)
        
        best_practices_keywords = self._extract_best_practices_keywords(question)
        documents = await self._search_documents(' OR '.join(best_practices_keywords), project_filter)
        
        if documents:
            prompt = f"""Based on the DTCE project documents found, please answer: {question}

Focus on:
- Standard approaches and methodologies
- Best practice examples and templates
- Design guidelines and procedures
- Proven solutions and techniques"""
            
            answer = await self._generate_natural_answer(prompt, documents, "best practices")
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'high',
                'documents_searched': len(documents),
                'rag_type': 'best_practices'
            }
        else:
            return {
                'answer': "I couldn't find specific best practices matching your query in our database.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'best_practices'
            }
    
    async def _handle_materials_methods(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle materials and methods queries - Use GPT for natural language answers"""
        logger.info("Processing materials methods", question=question)
        
        materials_keywords = self._extract_materials_keywords(question)
        documents = await self._search_documents(' OR '.join(materials_keywords), project_filter)
        
        if documents:
            prompt = f"""Based on the DTCE project documents found, please answer: {question}

Focus on:
- Material comparisons and selection
- Construction methods and techniques
- Performance considerations
- Decision-making factors and rationale"""
            
            answer = await self._generate_natural_answer(prompt, documents, "materials and methods")
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'high',
                'documents_searched': len(documents),
                'rag_type': 'materials_methods'
            }
        else:
            return {
                'answer': "I couldn't find specific materials and methods information matching your query in our database.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'materials_methods'
            }
    
    async def _handle_internal_knowledge(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle internal knowledge queries - Use GPT for natural language answers"""
        logger.info("Processing internal knowledge", question=question)
        
        knowledge_keywords = self._extract_knowledge_keywords(question)
        documents = await self._search_documents(' OR '.join(knowledge_keywords), project_filter)
        
        if documents:
            prompt = f"""Based on the DTCE project documents found, please answer: {question}

Focus on:
- Engineer expertise and experience
- Internal knowledge and capabilities
- Project authorship and contributions
- Team skills and specializations"""
            
            answer = await self._generate_natural_answer(prompt, documents, "internal knowledge")
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'medium',
                'documents_searched': len(documents),
                'rag_type': 'internal_knowledge'
            }
        else:
            return {
                'answer': "I couldn't find specific internal knowledge information matching your query in our database.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'internal_knowledge'
            }
    
    # Add missing helper methods
    def _extract_lessons_keywords(self, question: str) -> List[str]:
        """Extract lessons learned keywords"""
        return self._extract_issue_keywords(question)
    
    def _extract_best_practices_keywords(self, question: str) -> List[str]:
        """Extract best practice keywords"""
        return self._extract_practice_keywords(question)
    
    def _extract_materials_keywords(self, question: str) -> List[str]:
        """Extract material comparison keywords"""
        return self._extract_material_keywords(question)
    
    def _extract_knowledge_keywords(self, question: str) -> List[str]:
        """Extract expertise area keywords"""
        return self._extract_expertise_keywords(question)
    
    def _format_sources_with_job_numbers(self, documents: List[Dict]) -> List[Dict]:
        """Format sources with job number information."""
        return self._format_sources(documents)
    
    def _format_sources_with_products(self, documents: List[Dict]) -> List[Dict]:
        """Format sources with product information."""
        return self._format_sources(documents)
    
    async def _handle_general_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle general queries that don't match specific RAG patterns."""
        # If no specific RAG pattern is found, return general_query type
        # The DocumentQAService will handle this as a "no pattern match"
        
        return {
            'answer': "No specific RAG pattern matched",
            'sources': [],
            'confidence': 'low',
            'documents_searched': 0,
            'rag_type': 'general_query'
        }
    
    async def _handle_scenario_technical(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle scenario-based technical queries - EXACT OUTPUT as per RAG.TXT"""
        logger.info("Processing scenario technical", question=question)
        
        # Extract scenario keywords
        scenario_keywords = self._extract_scenario_keywords(question)
        search_query = ' AND '.join(scenario_keywords)
        
        documents = await self._search_documents(search_query, project_filter)
        
        if documents:
            # Use GPT to generate natural answer based on scenario documents
            prompt = f"Looking for DTCE project examples that match this scenario: {question}\n\nScenario keywords: {', '.join(scenario_keywords)}"
            answer = await self._generate_natural_answer(prompt, documents, "scenario examples")
            
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'high',
                'documents_searched': len(documents),
                'rag_type': 'scenario_technical'
            }
        else:
            return {
                'answer': "I couldn't find projects matching your specific scenario criteria in our database.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'scenario_technical'
            }
    
    async def _handle_lessons_learned(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle lessons learned queries - EXACT OUTPUT as per RAG.TXT"""
        logger.info("Processing lessons learned", question=question)
        
        # Extract issue/problem keywords
        issue_keywords = self._extract_issue_keywords(question)
        search_query = ' AND '.join(issue_keywords)
        
        documents = await self._search_documents(search_query, project_filter)
        
        if documents:
            # Use GPT to generate natural answer based on lessons learned documents
            prompt = f"Looking for lessons learned from DTCE projects related to: {question}\n\nIssue keywords: {', '.join(issue_keywords)}"
            answer = await self._generate_natural_answer(prompt, documents, "lessons learned")
            
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'high',
                'documents_searched': len(documents),
                'rag_type': 'lessons_learned'
            }
        else:
            return {
                'answer': "I couldn't find specific lessons learned about this issue in our database.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'lessons_learned'
            }
    
    async def _handle_regulatory_precedent(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle regulatory precedent queries - EXACT OUTPUT as per RAG.TXT"""
        logger.info("Processing regulatory precedent", question=question)
        
        regulatory_keywords = self._extract_regulatory_keywords(question)
        search_query = ' AND '.join(regulatory_keywords)
        
        documents = await self._search_documents(search_query, project_filter)
        
        if documents:
            # Use GPT to generate natural answer based on regulatory documents
            prompt = f"Looking for regulatory precedents from DTCE projects related to: {question}\n\nRegulatory keywords: {', '.join(regulatory_keywords)}"
            answer = await self._generate_natural_answer(prompt, documents, "regulatory precedents")
            
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'high',
                'documents_searched': len(documents),
                'rag_type': 'regulatory_precedent'
            }
        else:
            return {
                'answer': "I couldn't find regulatory precedents for this type of issue in our database.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'regulatory_precedent'
            }
    
    async def _handle_cost_time_insights(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle cost and time insight queries - EXACT OUTPUT as per RAG.TXT"""
        logger.info("Processing cost time insights", question=question)
        
        cost_time_keywords = self._extract_cost_time_keywords(question)
        search_query = ' AND '.join(cost_time_keywords)
        
        documents = await self._search_documents(search_query, project_filter)
        
        if documents:
            # Use GPT to generate natural answer based on cost/time documents
            prompt = f"Looking for cost and time insights from DTCE projects related to: {question}\n\nCost/time keywords: {', '.join(cost_time_keywords)}"
            answer = await self._generate_natural_answer(prompt, documents, "cost and time insights")
            
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'high',
                'documents_searched': len(documents),
                'rag_type': 'cost_time_insights'
            }
        else:
            return {
                'answer': "I couldn't find cost and time information for this type of project in our database.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'cost_time_insights'
            }
    
    async def _handle_best_practices(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle best practices queries - EXACT OUTPUT as per RAG.TXT"""
        logger.info("Processing best practices", question=question)
        
        practice_keywords = self._extract_practice_keywords(question)
        search_query = ' AND '.join(practice_keywords)
        
        documents = await self._search_documents(search_query, project_filter)
        
        if documents:
            # Use GPT to generate natural answer based on best practices documents
            prompt = f"Looking for DTCE's best practices related to: {question}\n\nPractice keywords: {', '.join(practice_keywords)}"
            answer = await self._generate_natural_answer(prompt, documents, "best practices")
            
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'high',
                'documents_searched': len(documents),
                'rag_type': 'best_practices'
            }
        else:
            return {
                'answer': "I couldn't find best practices for this area in our database.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'best_practices'
            }
    
    async def _handle_materials_methods(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle materials and methods queries - EXACT OUTPUT as per RAG.TXT"""
        logger.info("Processing materials methods", question=question)
        
        material_keywords = self._extract_material_keywords(question)
        search_query = ' AND '.join(material_keywords)
        
        documents = await self._search_documents(search_query, project_filter)
        
        if documents:
            # Use GPT to generate natural answer based on materials/methods documents
            prompt = f"Looking for materials and methods comparisons from DTCE projects related to: {question}\n\nMaterial keywords: {', '.join(material_keywords)}"
            answer = await self._generate_natural_answer(prompt, documents, "materials and methods")
            
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'high',
                'documents_searched': len(documents),
                'rag_type': 'materials_methods'
            }
        else:
            return {
                'answer': "I couldn't find material/method comparisons for this area in our database.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'materials_methods'
            }
    
    async def _handle_internal_knowledge(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle internal knowledge queries - EXACT OUTPUT as per RAG.TXT"""
        logger.info("Processing internal knowledge", question=question)
        
        expertise_keywords = self._extract_expertise_keywords(question)
        search_query = ' AND '.join(expertise_keywords)
        
        documents = await self._search_documents(search_query, project_filter)
        
        if documents:
            # Use GPT to generate natural answer based on internal expertise documents
            prompt = f"Looking for DTCE's internal expertise and knowledge related to: {question}\n\nExpertise keywords: {', '.join(expertise_keywords)}"
            answer = await self._generate_natural_answer(prompt, documents, "internal knowledge")
            
            return {
                'answer': answer,
                'sources': self._format_sources(documents),
                'confidence': 'high',
                'documents_searched': len(documents),
                'rag_type': 'internal_knowledge'
            }
        else:
            return {
                'answer': "I couldn't find internal expertise information for this area in our database.",
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'internal_knowledge'
            }
    
    def _format_sources_with_job_numbers(self, documents: List[Dict]) -> List[Dict]:
        """Format sources with job number information."""
        return self._format_sources(documents)
    
    def _format_sources_with_products(self, documents: List[Dict]) -> List[Dict]:
        """Format sources with product information."""
        return self._format_sources(documents)

    def _convert_to_suitefiles_url(self, blob_url: str) -> Optional[str]:
        """Convert Azure blob URL to SuiteFiles URL for folder navigation."""
        if not blob_url:
            return None
        
        try:
            from ..config.settings import get_settings
            settings = get_settings()
            sharepoint_base_url = settings.SHAREPOINT_SITE_URL
            
            # Extract the file path from blob URL
            # Example blob URL: https://dtceaistorage.blob.core.windows.net/dtce-documents/Engineering/04_Design(Structural)/05_Timber/11%20Proprietary%20Products/Lumberworx/Lumberworx-Laminated-Veneer-Lumber-Glulam-Beams2013.pdf
            # Should become: https://donthomson.sharepoint.com/sites/suitefiles/AppPages/documents.aspx#/folder/Engineering/04_Design%28Structural%29/05_Timber/11%20Proprietary%20Products/Lumberworx
            
            # Extract everything after "/dtce-documents/"
            if "/dtce-documents/" in blob_url:
                path_part = blob_url.split("/dtce-documents/")[-1]
                
                # URL decode first (in case it's already encoded)
                import urllib.parse
                decoded_path = urllib.parse.unquote(path_part)
                
                # Check if this is a file (has extension) or folder
                if '.' in decoded_path.split('/')[-1]:
                    # This is a file - extract folder path and use /folder/ instead of /file/
                    folder_path = '/'.join(decoded_path.split('/')[:-1])
                    # Encode for SharePoint URLs with proper encoding
                    encoded_path = urllib.parse.quote(folder_path, safe="/")
                    # Build SuiteFiles URL - use /folder/ for folder navigation
                    suite_files_url = f"{sharepoint_base_url}/AppPages/documents.aspx#/folder/{encoded_path}"
                else:
                    # This is already a folder path
                    encoded_path = urllib.parse.quote(decoded_path, safe="/")
                    suite_files_url = f"{sharepoint_base_url}/AppPages/documents.aspx#/folder/{encoded_path}"
                
                return suite_files_url
                
            # Fallback for old logic (Projects specific)
            elif "/Projects/" in blob_url:
                path_part = blob_url.split("/Projects/")[-1]
                import urllib.parse
                decoded_path = urllib.parse.unquote(path_part)
                
                # Extract folder path for Projects
                if '.' in decoded_path.split('/')[-1]:
                    folder_path = '/'.join(decoded_path.split('/')[:-1])
                    encoded_path = urllib.parse.quote(folder_path, safe="/")
                    suite_files_url = f"{sharepoint_base_url}/AppPages/documents.aspx#/folder/Projects/{encoded_path}"
                else:
                    encoded_path = urllib.parse.quote(decoded_path, safe="/")
                    suite_files_url = f"{sharepoint_base_url}/AppPages/documents.aspx#/folder/Projects/{encoded_path}"
                
                return suite_files_url
        except Exception as e:
            logger.warning("Failed to convert to SuiteFiles URL", blob_url=blob_url, error=str(e))
        
        return None

    def _format_sources_with_suitefiles(self, documents: List[Dict]) -> List[Dict]:
        """Format sources with enhanced SuiteFiles integration for better navigation."""
        formatted_sources = []
        for doc in documents:
            source = {
                'title': doc.get('title', 'Unknown Document'),
                'content_preview': doc.get('content', '')[:200] + '...' if doc.get('content') else '',
                'file_path': doc.get('file_path', ''),
                'score': doc.get('@search.score', 0),
                'highlights': doc.get('@search.highlights', {}),
            }
            
            # Add SuiteFiles URL for folder navigation
            if doc.get('file_path'):
                suitefiles_url = self._convert_to_suitefiles_url(doc['file_path'])
                if suitefiles_url:
                    source['suitefiles_folder_url'] = suitefiles_url
            
            formatted_sources.append(source)
        
        return formatted_sources

    def _generate_fallback_technical_response(self, query: str, documents: List[Dict]) -> Dict:
        """Generate fallback response for technical scenario queries when specific content is limited."""
        
        # Extract key technical terms from query
        technical_terms = []
        engineering_keywords = ['foundation', 'structural', 'timber', 'concrete', 'steel', 'building', 
                               'design', 'load', 'beam', 'column', 'slab', 'wall', 'roof', 'seismic',
                               'wind', 'pile', 'footing', 'connection', 'joint', 'material', 'code',
                               'standard', 'specification', 'detail', 'drawing', 'analysis', 'calculation']
        
        query_lower = query.lower()
        for keyword in engineering_keywords:
            if keyword in query_lower:
                technical_terms.append(keyword)
        
        # Format available sources
        sources = self._format_sources_with_suitefiles(documents)
        
        fallback_response = f"""
I found {len(documents)} relevant documents related to your technical query about {', '.join(technical_terms[:3]) if technical_terms else 'engineering topics'}.

**Available Resources:**
"""
        
        # Group sources by folder/topic
        folder_groups = {}
        for doc in sources:
            file_path = doc.get('file_path', '')
            if file_path:
                # Extract main folder category
                path_parts = file_path.split('/')
                if len(path_parts) > 1:
                    main_folder = path_parts[1] if len(path_parts) > 2 else path_parts[0]
                    if main_folder not in folder_groups:
                        folder_groups[main_folder] = []
                    folder_groups[main_folder].append(doc)
        
        # Present organized results
        for folder, docs in folder_groups.items():
            fallback_response += f"\n**{folder}:**\n"
            for doc in docs[:3]:  # Limit to top 3 per folder
                title = doc.get('title', 'Unknown Document')
                if doc.get('suitefiles_folder_url'):
                    fallback_response += f"- {title} [View in SuiteFiles]({doc['suitefiles_folder_url']})\n"
                else:
                    fallback_response += f"- {title}\n"
        
        fallback_response += f"""
**For More Specific Information:**
- Review the documents listed above for detailed technical content
- Use SuiteFiles links to browse related documents in each folder
- Consider refining your query with more specific technical terms
- Contact the engineering team for project-specific guidance

**Query Processing Note:** This response is based on document metadata and titles. For detailed technical content, please review the full documents through the SuiteFiles links provided.
"""
        
        return {
            'response': fallback_response.strip(),
            'sources': sources,
            'rag_type': 'scenario_technical_fallback'
        }

    def _generate_fallback_lessons_response(self, query: str, documents: List[Dict]) -> Dict:
        """Generate fallback response for lessons learned queries when specific content is limited."""
        
        # Extract problem/challenge terms from query
        problem_keywords = ['issue', 'problem', 'challenge', 'failure', 'error', 'mistake', 'lesson',
                           'difficulty', 'complication', 'setback', 'obstacle', 'trouble', 'concern']
        
        query_lower = query.lower()
        identified_problems = [kw for kw in problem_keywords if kw in query_lower]
        
        sources = self._format_sources_with_suitefiles(documents)
        
        fallback_response = f"""
I found {len(documents)} documents that may contain relevant lessons learned and problem-solving insights.

**Document Categories Found:**
"""
        
        # Categorize documents by type/folder
        doc_categories = {}
        for doc in sources:
            file_path = doc.get('file_path', '')
            title = doc.get('title', '')
            
            # Identify document category
            category = 'General Engineering'
            if any(word in file_path.lower() for word in ['project', 'job']):
                category = 'Project Documentation'
            elif any(word in file_path.lower() for word in ['report', 'analysis', 'study']):
                category = 'Technical Reports'
            elif any(word in file_path.lower() for word in ['specification', 'standard', 'code']):
                category = 'Standards & Specifications'
            elif any(word in file_path.lower() for word in ['drawing', 'detail', 'plan']):
                category = 'Technical Drawings'
            
            if category not in doc_categories:
                doc_categories[category] = []
            doc_categories[category].append(doc)
        
        for category, docs in doc_categories.items():
            fallback_response += f"\n**{category}:** {len(docs)} documents\n"
            for doc in docs[:2]:  # Show top 2 per category
                title = doc.get('title', 'Unknown Document')
                if doc.get('suitefiles_folder_url'):
                    fallback_response += f"  - {title} [Browse Folder]({doc['suitefiles_folder_url']})\n"
                else:
                    fallback_response += f"  - {title}\n"
        
        fallback_response += f"""
**Recommended Approach for Finding Lessons Learned:**

1. **Review Project Files:** Look for post-project reports, meeting minutes, or project closeout documents
2. **Check Technical Reports:** Examine analysis reports and studies for identified challenges and solutions
3. **Browse Related Folders:** Use the SuiteFiles links above to explore folders for additional context
4. **Consult Team Knowledge:** Reach out to project team members who worked on similar challenges

**Search Refinement Suggestions:**
- Include specific project names or numbers if known
- Use technical terms related to the specific problem area
- Search for "post-project," "lessons," "issues," or "challenges"

**Note:** This response is based on document discovery. For detailed lessons learned content, please review the full documents and folders linked above.
"""
        
        return {
            'response': fallback_response.strip(),
            'sources': sources,
            'rag_type': 'lessons_learned_fallback'
        }
