"""
GPT integration service for answering questions about documents.
Connects to Azure OpenAI or OpenAI to provide intelligent responses.
"""

import asyncio
import re
from typing import List, Dict, Any, Optional, Tuple
import structlog
from azure.search.documents import SearchClient
from openai import AsyncAzureOpenAI
from ..config.settings import get_settings

logger = structlog.get_logger(__name__)


class DocumentQAService:
    """Service for answering questions about indexed documents using GPT."""
    
    def __init__(self, search_client: SearchClient):
        """Initialize the QA service."""
        self.search_client = search_client
        settings = get_settings()
        
        # Initialize Azure OpenAI client
        self.openai_client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version
        )
        
        self.model_name = settings.azure_openai_deployment_name
        self.max_context_length = 8000  # Conservative limit for context
        
        # Initialize smart query classification
        from .query_classification import QueryClassificationService, SmartQueryRouter
        self.classification_service = QueryClassificationService(self.openai_client, self.model_name)
        self.smart_router = SmartQueryRouter(self.classification_service)
        
    async def answer_question(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Answer a question using document context from the search index.
        
        Args:
            question: The question to answer
            project_filter: Optional project filter to limit search scope
            
        Returns:
            Dictionary with answer, sources, and metadata
        """
        try:
            logger.info("Processing question", question=question, project_filter=project_filter)
            
            # Use AI-powered smart routing instead of rigid keyword matching
            handler_type, classification = await self.smart_router.route_query(question)
            
            logger.info("Smart routing result", 
                       handler=handler_type,
                       intent=classification.get('primary_intent'),
                       confidence=classification.get('confidence'))
            
            # Route to appropriate handler based on AI classification
            if handler_type == "nz_standards":
                return await self._handle_nz_standards_query(question, project_filter)
            elif handler_type == "template_search":
                return await self._handle_template_search_query(question, project_filter)
            elif handler_type == "project_search":
                return await self._handle_keyword_project_query(question, project_filter)
            elif handler_type == "scenario_technical":
                return await self._handle_scenario_technical_query(question, project_filter)
            elif handler_type == "regulatory_precedent":
                return await self._handle_regulatory_precedent_query(question, project_filter)
            elif handler_type == "cost_time_insights":
                return await self._handle_cost_time_insights_query(question, project_filter)
            elif handler_type == "best_practices_templates":
                return await self._handle_best_practices_templates_query(question, project_filter)
            elif handler_type == "materials_methods":
                return await self._handle_materials_methods_query(question, project_filter)
            elif handler_type == "internal_knowledge":
                return await self._handle_internal_knowledge_query(question, project_filter)
            elif handler_type == "web_search":
                return await self._handle_web_search_query(question, project_filter)
            elif handler_type == "contractor_search":
                return await self._handle_contractor_search_query(question, project_filter)
            else:  # general_search
                # Fall back to normal document search
                pass
            
            # Convert dates in the question to match filename formats
            converted_question = self._convert_date_formats(question)
            
            # Step 1: Search for relevant documents
            relevant_docs = await self._search_relevant_documents(converted_question, project_filter)
            
            if not relevant_docs:
                return {
                    'answer': 'I could not find any relevant documents to answer your question.',
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': 0
                }
            
            # Step 2: Prepare context from relevant documents
            context = self._prepare_context(relevant_docs)
            
            # Step 3: Generate answer using GPT
            answer_response = await self._generate_answer(question, context)
            
            # Step 4: Format response with sources
            return {
                'answer': answer_response['answer'],
                'sources': [
                    {
                        'filename': self._extract_document_info(doc)['filename'],  # Use comprehensive extraction
                        'project_id': self._extract_document_info(doc)['project_id'] or 'Unknown',  # Use comprehensive extraction
                        'relevance_score': doc['@search.score'],
                        'blob_url': doc.get('blob_url', ''),
                        'excerpt': doc.get('@search.highlights', {}).get('content',  # Use existing field name 
                                  doc.get('@search.highlights', {}).get('content_preview', ['']))[0][:200] + '...'
                    }
                    for doc in relevant_docs[:3]  # Top 3 sources
                ],
                'confidence': answer_response['confidence'],
                'documents_searched': len(relevant_docs),
                'processing_time': answer_response.get('processing_time', 0)
            }
            
        except Exception as e:
            logger.error("Question answering failed", error=str(e), question=question)
            return {
                'answer': f'I encountered an error while processing your question: {str(e)}',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    async def _search_relevant_documents(self, question: str, project_filter: Optional[str] = None) -> List[Dict]:
        """Search for documents relevant to the question."""
        try:
            # Auto-detect project from question if not provided
            if not project_filter:
                project_filter = self._extract_project_from_question(question)
                
            # If no project found but it's a date-specific question, try searching without filter first
            # then suggest being more specific
            is_date_question = self._is_date_only_question(question)
            
            # For project-specific queries, broaden the search terms
            search_text = question
            if project_filter and ("project" in question.lower() or project_filter in question):
                # For project questions, search for common terms that might be in the files
                search_text = f"email OR communication OR document OR file OR DMT OR brief OR proceeding"
            
            # Convert date formats in the question to match filename patterns
            search_text = self._convert_date_formats(search_text)
            
            # Search without project filter initially since project_id field might be empty
            results = self.search_client.search(
                search_text=search_text,
                top=50,  # Get more results for filtering
                highlight_fields="filename,project_name,content",  # Use existing field names
                select=["id", "filename", "content", "blob_url", "project_name",  # Use existing field names
                       "folder", "last_modified", "created_date", "size"],  # Use existing field names
                query_type="semantic",  # Always use semantic search for better results
                semantic_configuration_name="default"  # Use the semantic configuration we defined
            )
            
            # Convert to list and filter by project if needed
            documents = []
            for result in results:
                doc_dict = dict(result)
                
                # If we have a project filter, check if the document belongs to that project
                if project_filter:
                    doc_project = self._extract_project_from_url(doc_dict.get('blob_url', ''))
                    if doc_project != project_filter:
                        continue  # Skip documents not in the target project
                elif is_date_question:
                    # For date-only questions, include all matching documents but prioritize recent projects
                    pass  # Don't filter by project for date-only questions
                
                documents.append(doc_dict)
                
                # Limit to top 10 after filtering
                if len(documents) >= 10:
                    break
            
            logger.info("Found relevant documents", count=len(documents), question=question, project_filter=project_filter)
            return documents
            
        except Exception as e:
            logger.error("Document search failed", error=str(e), question=question)
            return []
            
            logger.info("Found relevant documents", count=len(documents), question=question)
            return documents
            
        except Exception as e:
            logger.error("Document search failed", error=str(e), question=question)
            return []

    def _prepare_context(self, documents: List[Dict]) -> str:
        """Prepare context from relevant documents for GPT."""
        context_parts = []
        current_length = 0
        
        for doc in documents:
            # Extract relevant information using correct field names
            filename = doc.get('filename', 'Unknown')  # Use existing field name
            project = self._extract_project_from_url(doc.get('blob_url', '')) or doc.get('project_name', 'Unknown')  # Use existing field name
            # Use existing content field name
            content = doc.get('content', '')
            
            # Truncate content if too long
            if len(content) > 1000:
                content = content[:1000] + "..."
            
            doc_context = f"""
Document: {filename}
Project: {project}
Content: {content}
---
"""
            
            # Check if adding this document would exceed limit
            if current_length + len(doc_context) > self.max_context_length:
                break
                
            context_parts.append(doc_context)
            current_length += len(doc_context)
        
        return "\n".join(context_parts)

    def _extract_project_from_url(self, blob_url: str) -> Optional[str]:
        """Extract project ID from blob URL path like /Projects/219/219200/"""
        if not blob_url:
            return None
        
        try:
            # Look for Projects/xxx/xxxxxx pattern in URL
            import re
            match = re.search(r'/Projects/(\d+)/(\d+)/', blob_url)
            if match:
                # Return the more specific sub-project ID (219200)
                return match.group(2)
            
            # Fallback to simpler Projects/xxx pattern
            match = re.search(r'/Projects/(\d+)/', blob_url)
            if match:
                return match.group(1)
        except Exception:
            pass
        
        return None

    def _decode_document_id(self, document_id: str) -> Dict[str, str]:
        """Decode Base64 document ID to extract file path, filename, and project info."""
        result = {
            'full_path': '',
            'filename': '',
            'project_id': '',
            'folder_path': ''
        }
        
        if not document_id:
            return result
            
        try:
            import base64
            import urllib.parse
            import os
            
            # Try to decode as Base64
            decoded_bytes = base64.b64decode(document_id + '==')  # Add padding if needed
            decoded_url = decoded_bytes.decode('utf-8')
            
            # Extract the path part after the domain
            if 'dtce-documents/' in decoded_url:
                path_part = decoded_url.split('dtce-documents/')[-1]
                result['full_path'] = path_part
                
                # URL decode the path
                decoded_path = urllib.parse.unquote(path_part)
                result['full_path'] = decoded_path
                
                # Extract filename (last part of path, excluding .keep files)
                path_parts = decoded_path.split('/')
                if path_parts and path_parts[-1] and path_parts[-1] != '.keep':
                    result['filename'] = path_parts[-1]
                elif len(path_parts) > 1 and path_parts[-2]:
                    # If last part is .keep, use the folder name
                    result['filename'] = path_parts[-2]
                
                # Extract project ID from path (Projects/219/219359 pattern)
                if 'Projects/' in decoded_path:
                    project_part = decoded_path.split('Projects/')[-1]
                    project_parts = project_part.split('/')
                    if len(project_parts) >= 2:
                        result['project_id'] = project_parts[1]  # The specific project ID (e.g., 219359)
                    elif len(project_parts) >= 1:
                        result['project_id'] = project_parts[0]  # Fallback to first part
                
                # Extract folder path (everything except filename)
                if '/' in decoded_path:
                    result['folder_path'] = '/'.join(decoded_path.split('/')[:-1])
                    
        except Exception as e:
            # If Base64 decoding fails, try other extraction methods
            try:
                import re
                # Look for Projects_xxx_xxxxxx pattern in ID
                match = re.search(r'Projects_(\d+)_(\d+)_', document_id)
                if match:
                    result['project_id'] = match.group(2)  # Return the more specific project ID
                else:
                    # Fallback to Projects_xxx pattern
                    match = re.search(r'Projects_(\d+)_', document_id)
                    if match:
                        result['project_id'] = match.group(1)
            except:
                pass
        
        return result

    def _extract_document_info(self, document: Dict) -> Dict[str, str]:
        """Extract comprehensive document information including filename and project."""
        info = {
            'filename': 'Unknown',
            'project_id': '',
            'folder_path': '',
            'full_path': ''
        }
        
        # Start with existing fields
        if document.get('filename'):
            info['filename'] = document['filename']
        if document.get('project_name'):
            info['project_id'] = document['project_name']
        
        # Try to get better info from decoded ID
        document_id = document.get('id', '')
        if document_id:
            decoded_info = self._decode_document_id(document_id)
            
            # Use decoded filename if we don't have one or it's better
            if decoded_info['filename'] and (not info['filename'] or info['filename'] == 'Unknown'):
                info['filename'] = decoded_info['filename']
            
            # Use decoded project ID if we don't have one or it's better
            if decoded_info['project_id'] and not info['project_id']:
                info['project_id'] = decoded_info['project_id']
            
            # Always use the path info from decoded ID
            info['folder_path'] = decoded_info['folder_path']
            info['full_path'] = decoded_info['full_path']
        
        # Fallback methods for project extraction
        if not info['project_id']:
            # Try extracting from blob_url
            project_from_url = self._extract_project_from_url(document.get('blob_url', ''))
            if project_from_url:
                info['project_id'] = project_from_url
            
            # Try extracting from content (look for project numbers)
            content = document.get('content', '')
            if content and not info['project_id']:
                try:
                    import re
                    # Look for patterns like "219324", "2BC221295", "221285" in content
                    project_patterns = [
                        r'\b(2[A-Z]{2}\d{6})\b',  # 2BC221295 format
                        r'\b(\d{6})\b',           # 6-digit numbers
                        r'\b(Project\s+\d+)\b'    # "Project 123" format
                    ]
                    
                    for pattern in project_patterns:
                        matches = re.findall(pattern, content)
                        if matches:
                            info['project_id'] = matches[0]
                            break
                except:
                    pass
        
        return info

    def _extract_project_from_document(self, document: Dict) -> str:
        """Extract project ID from document using multiple methods."""
        # Use the comprehensive extraction method
        doc_info = self._extract_document_info(document)
        return doc_info['project_id'] or 'Unknown'

    def _generate_meaningful_filename(self, document: Dict) -> str:
        """Generate a meaningful filename from document content when filename is missing."""
        content = document.get('content', '')
        
        if not content:
            return 'Unknown Document'
        
        # Look for common document patterns
        content_lower = content.lower()
        
        # Check for specific document types
        if 'wind zones' in content_lower or 'wind load' in content_lower:
            return 'Wind Load Analysis'
        elif 'correspondence' in content_lower or 'from:' in content_lower:
            return 'Project Correspondence'
        elif 'building consent' in content_lower:
            return 'Building Consent Documentation'
        elif 'council' in content_lower and ('query' in content_lower or 'response' in content_lower):
            return 'Council Correspondence'
        elif 'engineering report' in content_lower or 'technical report' in content_lower:
            return 'Engineering Report'
        elif 'design guide' in content_lower:
            return 'Design Guide'
        elif 'timber building' in content_lower:
            return 'Timber Building Guide'
        elif 'consenting' in content_lower:
            return 'Consenting Documentation'
        elif 'ps1' in content_lower or 'ps3' in content_lower or 'producer statement' in content_lower:
            return 'Producer Statement'
        elif 'concept design' in content_lower:
            return 'Concept Design Report'
        
        # Look for subject lines in emails
        import re
        subject_match = re.search(r'subject:\s*([^\n\r]+)', content, re.IGNORECASE)
        if subject_match:
            subject = subject_match.group(1).strip()
            if len(subject) > 10 and len(subject) < 80:  # Reasonable subject length
                return f"Email: {subject}"
        
        # Look for document titles
        title_patterns = [
            r'^([A-Z][^\n\r]{10,60})\n',  # Title-like first lines
            r'FOR\s+([^\n\r]{10,60})\n',  # "FOR ..." patterns
            r'RE:\s*([^\n\r]{5,60})\n'    # "RE: ..." patterns
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, content[:200], re.MULTILINE)
            if match:
                title = match.group(1).strip()
                if title and not title.lower().startswith('page '):
                    return title[:50] + ('...' if len(title) > 50 else '')
        
        return 'Document Content'

    def _extract_project_from_question(self, question: str) -> Optional[str]:
        """Extract project number from question text."""
        if not question:
            return None
        
        try:
            import re
            # Look for 6-digit project numbers (like 219200)
            match = re.search(r'\b(\d{6})\b', question)
            if match:
                return match.group(1)
            
            # Look for project patterns like "project 219" 
            match = re.search(r'project\s+(\d{3,6})', question.lower())
            if match:
                return match.group(1)
            
            # Look for any 3+ digit numbers that could be projects
            match = re.search(r'\b(\d{3,6})\b', question)
            if match:
                return match.group(1)
        except Exception:
            pass
        
        return None

    def _convert_date_formats(self, text: str) -> str:
        """Convert natural language dates to the format used in filenames (YY MM DD)"""
        patterns = [
            (r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b', self._convert_full_date),
            (r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', self._convert_slash_date),
            (r'\b(\d{1,2})-(\d{1,2})-(\d{4})\b', self._convert_dash_date),
        ]
        
        converted_text = text
        for pattern, converter in patterns:
            converted_text = re.sub(pattern, converter, converted_text)
        
        return converted_text
    
    def _convert_full_date(self, match):
        """Convert 'January 7, 2019' to '19 01 07'"""
        month_name, day, year = match.groups()
        month_map = {
            'January': '01', 'February': '02', 'March': '03', 'April': '04',
            'May': '05', 'June': '06', 'July': '07', 'August': '08',
            'September': '09', 'October': '10', 'November': '11', 'December': '12'
        }
        month = month_map[month_name]
        year_short = year[-2:]  # Get last 2 digits
        day_padded = day.zfill(2)  # Pad with leading zero if needed
        return f"{year_short} {month} {day_padded}"
    
    def _convert_slash_date(self, match):
        """Convert '1/7/2019' to '19 01 07'"""
        month, day, year = match.groups()
        year_short = year[-2:]
        month_padded = month.zfill(2)
        day_padded = day.zfill(2)
        return f"{year_short} {month_padded} {day_padded}"
    
    def _convert_dash_date(self, match):
        """Convert '1-7-2019' to '19 01 07'"""
        month, day, year = match.groups()
        year_short = year[-2:]
        month_padded = month.zfill(2)
        day_padded = day.zfill(2)
        return f"{year_short} {month_padded} {day_padded}"

    def _is_date_only_question(self, question: str) -> bool:
        """Check if question is primarily about dates without project context."""
        if not question:
            return False
        
        try:
            import re
            question_lower = question.lower()
            
            # Check for date patterns without project numbers
            has_date = any([
                re.search(r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b', question_lower),
                re.search(r'\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b', question_lower),
                re.search(r'\b\d{1,2}\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}\b', question_lower)
            ])
            
            has_project = re.search(r'\b(project|219200|\d{6})\b', question_lower)
            
            return has_date and not has_project
            
        except Exception:
            return False

    async def _generate_answer(self, question: str, context: str) -> Dict[str, Any]:
        """Generate answer using GPT with document context."""
        try:
            import time
            start_time = time.time()
            
            # Prepare enhanced system prompt for comprehensive question answering
            system_prompt = """You are an advanced AI assistant for DTCE (engineering consultancy) that can answer ALL types of questions using available documentation and professional knowledge.

            YOUR CAPABILITIES:
            1. DOCUMENT-BASED ANSWERS: Answer questions using the provided document context
            2. BUSINESS PROCESS GUIDANCE: Provide advice on business processes, procedures, and workflows
            3. ENGINEERING EXPERTISE: Answer technical engineering questions
            4. ADMINISTRATIVE SUPPORT: Help with office procedures, software usage, and administrative tasks
            5. GENERAL PROFESSIONAL ADVICE: Provide reasonable professional guidance when documents don't contain the answer

            QUESTION TYPES YOU HANDLE:
            - Engineering: specifications, calculations, reports, drawings, project details
            - Business Processes: WorkflowMax, billing, time entry, invoicing, project management
            - Administrative: procedures, guidelines, company policies, software usage
            - Project Management: scheduling, communication, client relations
            - Financial: fee structures, billing procedures, cost estimation
            - General Professional: best practices, recommendations, troubleshooting

            RESPONSE STRATEGY:
            1. PRIMARY: Always use document context when available - cite specific documents and extract useful information
            2. NEVER say documents don't contain relevant information if documents are provided
            3. If documents contain partial information, extract what's useful and supplement with professional guidance
            4. Always be helpful and provide actionable advice
            5. For business process questions (like WorkflowMax), provide step-by-step guidance
            6. For technical questions, extract what you can from documents and provide additional context

            EXAMPLE APPROACHES:
            - "Based on the documents provided..." (when using document context)
            - "From the project files, I can see..." (extracting specific information)
            - "The documents show... and additionally, here's the recommended approach..." (combination approach)
            """
            
            # Prepare enhanced user prompt
            user_prompt = f"""
            Question: {question}

            Available Document Context:
            {context if context.strip() else "No specific documents found for this query."}

            INSTRUCTIONS:
            - If documents contain relevant information, use them as your primary source and cite specific details
            - If documents don't contain the answer, provide professional guidance and best practices
            - For business process questions (WorkflowMax, billing, etc.), provide step-by-step guidance
            - For technical questions, suggest where to find additional information if needed
            - Always be helpful and provide actionable advice
            - Be specific and detailed in your response

            Please provide a comprehensive answer addressing the question above.
            """
            
            # Call OpenAI/Azure OpenAI with enhanced parameters
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Slightly higher for more creative business guidance
                max_tokens=800   # Increased for more comprehensive answers
            )
            
            answer = response.choices[0].message.content
            processing_time = time.time() - start_time
            
            # Determine confidence based on response characteristics
            confidence = self._assess_confidence(answer, context)
            
            logger.info("Generated answer", 
                       question=question, 
                       answer_length=len(answer),
                       confidence=confidence,
                       processing_time=processing_time)
            
            return {
                'answer': answer,
                'confidence': confidence,
                'processing_time': processing_time
            }
            
        except Exception as e:
            logger.error("Answer generation failed", error=str(e), question=question)
            return {
                'answer': 'I encountered an error while generating the answer.',
                'confidence': 'error',
                'processing_time': 0
            }

    def _assess_confidence(self, answer: str, context: str) -> str:
        """Assess confidence level of the answer."""
        # Check for explicit disclaimers that indicate low confidence
        low_confidence_phrases = [
            "I cannot find", "not available", "not provided", "unclear from the documents",
            "insufficient information", "cannot determine"
        ]
        
        # Check if answer contains any low confidence indicators
        answer_lower = answer.lower()
        if any(phrase in answer_lower for phrase in low_confidence_phrases):
            return 'low'
        
        # Assess based on context and answer quality
        if len(context) > 2000 and len(answer) > 200:
            return 'high'
        elif len(context) > 500 and len(answer) > 100:
            return 'medium'
        elif len(context) > 0 and len(answer) > 50:
            return 'medium'  # Even with some context, give medium confidence
        else:
            return 'low'

    async def get_document_summary(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Get a summary of available documents for a project or all projects."""
        try:
            # Search for all documents or project-specific documents
            search_filter = f"project_name eq '{project_id}'" if project_id else None
            
            results = self.search_client.search(
                search_text="*",
                top=100,
                filter=search_filter,
                select=["filename", "project_name", "folder", "content_type", "last_modified"]
            )
            
            # Analyze documents
            documents = list(results)
            doc_types = {}
            projects = set()
            
            for doc in documents:
                # Count document types
                content_type = doc.get('content_type', 'unknown')
                doc_types[content_type] = doc_types.get(content_type, 0) + 1
                
                # Collect projects
                project = doc.get('project_name')
                if project:
                    projects.add(project)
            
            return {
                'total_documents': len(documents),
                'document_types': doc_types,
                'projects': sorted(list(projects)),
                'latest_documents': [
                    {
                        'filename': doc['filename'],
                        'project': doc.get('project_name', 'Unknown'),
                        'last_modified': doc.get('last_modified', '')
                    }
                    for doc in sorted(documents, key=lambda x: x.get('last_modified', ''), reverse=True)[:5]
                ]
            }
            
        except Exception as e:
            logger.error("Document summary failed", error=str(e))
            return {'error': str(e)}

    def _is_project_keyword_query(self, question: str) -> bool:
        """Check if the question is asking for past projects using specific engineering keywords."""
        if not question:
            return False
        
        question_lower = question.lower()
        
        # Engineering/structural keywords
        engineering_keywords = [
            # Precast & Concrete
            "precast", "pre-cast", "precast panel", "precast connection", 
            "unispans", "unispan", "precast element", "precast unit",
            "precast concrete", "prefab", "prefabricated", "concrete",
            "reinforced concrete", "cast in place", "cast-in-place",
            
            # Timber & Wood
            "timber", "wood", "wooden", "timber frame", "timber framed",
            "timber retaining", "timber structure", "glulam", "lvl",
            "plywood", "timber beam", "timber column", "timber wall",
            
            # Steel & Metal
            "steel", "steel frame", "steel structure", "metal", "aluminum",
            "steel beam", "steel column", "structural steel", "cold-formed",
            
            # Structural Elements
            "retaining wall", "foundation", "footing", "pile", "beam",
            "column", "slab", "wall", "roof", "truss", "portal frame",
            "cantilever", "span", "connection", "joint", "bracket",
            
            # Building Types
            "residential", "commercial", "industrial", "warehouse",
            "office", "retail", "apartment", "house", "building",
            "structure", "facility", "development"
        ]
        
        # Project/work-related terms
        project_patterns = [
            "project", "job", "work", "contract", "site", "construction",
            "past", "previous", "historical", "archive", "record",
            "scope", "experience", "portfolio", "case", "example",
            "reference", "similar", "done before", "worked on"
        ]
        
        # Intent/action terms (what user wants to do)
        intent_patterns = [
            "tell me", "show me", "find", "search", "list", "all",
            "what", "which", "where", "give me", "provide", "display",
            "help", "assist", "looking for", "need", "want", "advise"
        ]
        
        # Check for engineering keywords
        has_engineering_keywords = any(keyword in question_lower for keyword in engineering_keywords)
        
        # Check for project/work context
        has_project_context = any(pattern in question_lower for pattern in project_patterns)
        
        # Check for request/intent
        has_intent = any(pattern in question_lower for pattern in intent_patterns)
        
        # Also check for plural forms and question words
        has_multiple_indicator = any(word in question_lower for word in ["all", "any", "every", "what", "which"])
        
        # Return true if we have engineering keywords AND (project context OR clear intent to find multiple items)
        return has_engineering_keywords and (has_project_context or (has_intent and has_multiple_indicator))

    def _is_precast_project_query(self, question: str) -> bool:
        """Check if the question is specifically asking for precast panel projects (legacy method)."""
        if not question:
            return False
        
        question_lower = question.lower()
        
        # Precast-specific terms
        precast_patterns = [
            "precast", "pre-cast", "precast panel", "precast connection", 
            "unispans", "unispan", "precast element", "precast unit",
            "precast concrete", "prefab", "prefabricated"
        ]
        
        # Check if it has precast terms and is a project search
        has_precast = any(pattern in question_lower for pattern in precast_patterns)
        
        if has_precast:
            return self._is_project_keyword_query(question)
        
        return False
        
    async def _handle_keyword_project_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle keyword-based project queries with specialized search and SuiteFiles URLs."""
        try:
            logger.info("Processing keyword project query", question=question)
            
            # Check if this is a scenario-based project query (building type + conditions + location)
            if self._is_scenario_based_project_query(question):
                return await self._handle_scenario_project_query(question, project_filter)
            
            # Extract keywords from the question
            keywords = self._extract_keywords_from_question(question)
            
            # Search for keyword-related documents
            keyword_docs = await self._search_keyword_documents(keywords)
            
            if not keyword_docs:
                return {
                    'answer': f'I could not find any projects related to {", ".join(keywords)} in our document index.',
                    'sources': [],
                    'confidence': 'medium',
                    'documents_searched': 0
                }
            
            # Extract unique projects from the documents
            projects_found = self._extract_keyword_projects(keyword_docs, keywords)
            
            if not projects_found:
                return {
                    'answer': f'I found documents related to {", ".join(keywords)} but could not identify specific project numbers.',
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': len(keyword_docs)
                }
            
            # Format the answer and sources
            answer = self._format_keyword_project_answer(projects_found, keywords)
            sources = self._format_keyword_sources(projects_found, keyword_docs)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'high',
                'documents_searched': len(keyword_docs)
            }
            
        except Exception as e:
            logger.error("Keyword project query failed", error=str(e))
            return {
                'answer': 'I encountered an error while searching for keyword-related projects.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    def _is_scenario_based_project_query(self, question: str) -> bool:
        """Detect if this is a scenario-based project query (building type + conditions + location)."""
        question_lower = question.lower()
        
        # Look for combinations of building types, conditions, and technical systems
        building_indicators = ['buildings', 'building', 'houses', 'house', 'apartment', 'mid-rise', 'structures']
        condition_indicators = ['high wind', 'steep slope', 'coastal', 'seismic', 'wind zone', 'earthquake']
        location_indicators = ['wellington', 'auckland', 'christchurch', 'coastal', 'zone']
        system_indicators = ['foundation', 'shear wall', 'timber frame', 'connection', 'balcony', 'steel', 'concrete']
        
        has_building = any(term in question_lower for term in building_indicators)
        has_condition = any(term in question_lower for term in condition_indicators)
        has_location = any(term in question_lower for term in location_indicators)
        has_system = any(term in question_lower for term in system_indicators)
        
        # Scenario-based if it has at least 2 of these components
        components_count = sum([has_building, has_condition, has_location, has_system])
        
        return components_count >= 2
    
    async def _handle_scenario_project_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle complex scenario-based project queries."""
        try:
            logger.info("Processing scenario-based project query", question=question)
            
            # Extract scenario components
            scenario_components = self._extract_scenario_components(question)
            
            # Use scenario search logic
            search_terms = self._build_scenario_search_terms(question, scenario_components)
            relevant_docs = await self._search_scenario_documents(search_terms, scenario_components)
            
            if not relevant_docs:
                return {
                    'answer': f"I couldn't find specific examples matching your criteria: {scenario_components.get('summary', question)}. Try searching for broader terms or check if there are similar projects with different conditions.",
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': 0,
                    'search_type': 'scenario_project'
                }
            
            # Generate project-focused answer with SuiteFiles links
            answer = await self._generate_scenario_project_answer(question, relevant_docs, scenario_components)
            sources = self._format_scenario_sources(relevant_docs, scenario_components)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'high' if len(relevant_docs) >= 3 else 'medium',
                'documents_searched': len(relevant_docs),
                'search_type': 'scenario_project',
                'scenario_components': scenario_components
            }
            
        except Exception as e:
            logger.error("Scenario project query failed", error=str(e))
            return {
                'answer': 'I encountered an error while searching for scenario-based project examples.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    async def _generate_scenario_project_answer(self, question: str, documents: List[Dict], components: Dict[str, Any]) -> str:
        """Generate a project-focused answer for scenario-based queries with SuiteFiles links."""
        if not documents:
            return "No matching project examples found for your scenario criteria."
        
        # Extract unique projects
        projects_found = {}
        for doc in documents:
            project_id = self._extract_project_from_document(doc)
            if project_id not in projects_found:
                projects_found[project_id] = {
                    'documents': [],
                    'scenario_score': 0
                }
            
            projects_found[project_id]['documents'].append(doc)
            # Use the highest scenario score for the project
            projects_found[project_id]['scenario_score'] = max(
                projects_found[project_id]['scenario_score'],
                doc.get('scenario_score', 0)
            )
        
        # Sort projects by scenario relevance
        sorted_projects = sorted(projects_found.items(), 
                               key=lambda x: x[1]['scenario_score'], 
                               reverse=True)
        
        # Build answer with project links
        answer_parts = []
        answer_parts.append(f"I found **{len(sorted_projects)} projects** matching your scenario criteria: {components['summary']}")
        answer_parts.append("")
        
        for project_id, project_data in sorted_projects[:5]:  # Top 5 projects
            doc_count = len(project_data['documents'])
            scenario_score = project_data['scenario_score']
            
            # Build SuiteFiles project link
            project_url = f"https://donthomson.sharepoint.com/sites/suitefiles/AppPages/documents.aspx#/folder/Projects/{project_id}"
            
            answer_parts.append(f"• **Project {project_id}** - {doc_count} documents (Match Score: {scenario_score:.1f})")
            answer_parts.append(f"  📁 [View Project Files]({project_url})")
            
            # Add brief description of what was found
            sample_doc = project_data['documents'][0]
            if sample_doc.get('content'):
                preview = sample_doc['content'][:100].replace('\n', ' ')
                answer_parts.append(f"  📝 Preview: {preview}...")
            
            answer_parts.append("")
        
        answer_parts.append("💡 **Tip:** Click the project links to access all related documents in SuiteFiles.")
        
        return "\n".join(answer_parts)

    def _extract_keywords_from_question(self, question: str) -> List[str]:
        """Extract relevant engineering keywords from the question."""
        if not question:
            return []
        
        question_lower = question.lower()
        found_keywords = []
        
        # Define keyword categories with their variations
        keyword_categories = {
            "precast": ["precast", "pre-cast", "precast panel", "precast connection", "unispans", "unispan", "prefab", "prefabricated"],
            "timber": ["timber", "wood", "wooden", "timber frame", "timber framed", "timber retaining", "glulam", "lvl"],
            "concrete": ["concrete", "reinforced concrete", "cast in place", "cast-in-place", "concrete building"],
            "steel": ["steel", "steel frame", "steel structure", "structural steel", "cold-formed"],
            "retaining wall": ["retaining wall", "retaining", "wall"],
            "building": ["building", "structure", "storey", "story", "residential", "commercial", "warehouse"]
        }
        
        # Find which categories match
        for category, terms in keyword_categories.items():
            if any(term in question_lower for term in terms):
                found_keywords.append(category)
        
        # Also extract explicit keywords mentioned in the question
        explicit_keywords = []
        for word in question.split():
            word_clean = word.strip('.,!?:;()[]"').lower()
            if word_clean in ["precast", "timber", "concrete", "steel", "retaining", "wall", "building", "unispans"]:
                explicit_keywords.append(word_clean)
        
        # Combine and deduplicate
        all_keywords = list(set(found_keywords + explicit_keywords))
        return all_keywords if all_keywords else ["structural", "engineering"]  # fallback

    async def _search_keyword_documents(self, keywords: List[str]) -> List[Dict]:
        """Search for documents related to the specified keywords using semantic search."""
        try:
            # Create a comprehensive search query from keywords
            search_text = " ".join(keywords) + " engineering structural design construction"
            
            results = self.search_client.search(
                search_text=search_text,
                top=100,  # Get many results to find all projects
                select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                query_type="semantic",  # Semantic search will find similar concepts
                semantic_configuration_name="default"  # Use the semantic configuration we defined
            )
            
            documents = []
            for result in results:
                doc_dict = dict(result)
                
                # More flexible content matching with semantic search
                content = (doc_dict.get('content') or '').lower()
                filename = (doc_dict.get('filename') or '').lower()
                
                # Check for keyword-related terms in content or filename
                keyword_terms = keywords + [
                    'engineering', 'structural', 'design', 'construction', 'building',
                    'concrete', 'steel', 'timber', 'precast', 'retaining', 'wall'
                ]
                
                # Include if semantic search found it OR if it contains obvious keyword terms
                if (result.get('@search.score', 0) > 0.1 or  # Lower threshold for semantic match
                    any(term in content or term in filename for term in keyword_terms)):
                    documents.append(doc_dict)
            
            logger.info("Found keyword documents via semantic search", keywords=keywords, count=len(documents))
            return documents
            
        except Exception as e:
            logger.error("Keyword semantic search failed", error=str(e), keywords=keywords)
            return []

    def _extract_keyword_projects(self, keyword_docs: List[Dict], keywords: List[str]) -> Dict[str, Dict]:
        """Extract unique project numbers from keyword-related documents."""
        projects = {}
        
        for doc in keyword_docs:
            blob_url = doc.get('blob_url', '')
            project_id = self._extract_project_from_url(blob_url)
            
            if project_id and len(project_id) >= 6:  # Valid project numbers
                if project_id not in projects:
                    projects[project_id] = {
                        'project_id': project_id,
                        'suitefiles_url': f"https://donthomson.sharepoint.com/sites/suitefiles/AppPages/documents.aspx#/folder/Projects/{project_id}",
                        'document_count': 0,
                        'sample_documents': [],
                        'keywords_found': []
                    }
                
                projects[project_id]['document_count'] += 1
                if len(projects[project_id]['sample_documents']) < 3:
                    projects[project_id]['sample_documents'].append(doc.get('filename', 'Unknown'))
                
                # Track which keywords were found in this project
                content = (doc.get('content') or '').lower()
                filename = (doc.get('filename') or '').lower()
                for keyword in keywords:
                    if keyword in content or keyword in filename:
                        if keyword not in projects[project_id]['keywords_found']:
                            projects[project_id]['keywords_found'].append(keyword)
        
        return projects

    def _format_keyword_project_answer(self, projects_found: Dict[str, Dict], keywords: List[str]) -> str:
        """Format the answer for keyword-based project queries."""
        if not projects_found:
            return f"I couldn't find any projects related to {', '.join(keywords)} in our documents."
        
        project_count = len(projects_found)
        keywords_text = ', '.join(keywords).title()
        
        if project_count == 1:
            # Single project - more conversational
            project_id, project_info = list(projects_found.items())[0]
            doc_count = project_info['document_count']
            suitefiles_url = project_info['suitefiles_url']
            keywords_found = project_info['keywords_found']
            
            answer = f"I found **Project {project_id}** which has {doc_count} documents related to {keywords_text}.\n\n"
            if keywords_found:
                answer += f"**Keywords Found:** {', '.join(keywords_found).title()}\n\n"
            answer += f"📁 **View Project Files:** [Open in SuiteFiles]({suitefiles_url})\n\n"
            answer += "This will take you directly to the project folder where you can access all the related documents."
        else:
            # Multiple projects
            answer = f"I found **{project_count} projects** related to {keywords_text}:\n\n"
            
            project_list = []
            for project_id, project_info in sorted(projects_found.items()):
                doc_count = project_info['document_count']
                suitefiles_url = project_info['suitefiles_url']
                keywords_found = project_info['keywords_found']
                
                keywords_display = f" ({', '.join(keywords_found)})" if keywords_found else ""
                project_list.append(f"• **Project {project_id}** - {doc_count} documents{keywords_display}\n  📁 [View Files]({suitefiles_url})")
            
            answer += "\n\n".join(project_list)
            answer += "\n\nClick any link above to access the project folders in SuiteFiles."
        
        return answer

    def _format_keyword_sources(self, projects_found: Dict[str, Dict], keyword_docs: List[Dict]) -> List[Dict]:
        """Format sources for keyword project queries with SuiteFiles URLs."""
        sources = []
        
        for project_id, project_info in sorted(projects_found.items()):
            sample_files = project_info['sample_documents'][:3]
            keywords_found = project_info['keywords_found']
            
            if sample_files:
                sample_text = f"Including files: {', '.join(sample_files)}"
            else:
                sample_text = "Multiple related documents found"
            
            if keywords_found:
                sample_text += f" | Keywords: {', '.join(keywords_found)}"
                
            sources.append({
                'filename': f"Project {project_id}",
                'project_id': project_id,
                'relevance_score': 1.0,
                'blob_url': project_info['suitefiles_url'],
                'excerpt': sample_text
            })
        
        return sources

    async def _handle_precast_project_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle precast panel project queries with specialized search and SuiteFiles URLs."""
        try:
            logger.info("Processing precast project query", question=question)
            
            # Search for precast-related documents
            precast_docs = await self._search_precast_documents()
            
            if not precast_docs:
                return {
                    'answer': 'I could not find any precast panel projects in our document index.',
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': 0
                }
            
            # Extract unique projects and generate SuiteFiles URLs
            projects_found = self._extract_precast_projects(precast_docs)
            
            # Format response with project list and SuiteFiles URLs
            answer = self._format_precast_project_answer(projects_found)
            
            # Format sources with SuiteFiles URLs
            sources = self._format_precast_sources(projects_found, precast_docs)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'high',
                'documents_searched': len(precast_docs),
                'processing_time': 0
            }
            
        except Exception as e:
            logger.error("Precast project query failed", error=str(e), question=question)
            return {
                'answer': f'I encountered an error while searching for precast projects: {str(e)}',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    async def _search_precast_documents(self) -> List[Dict]:
        """Search for documents related to precast panels using semantic search."""
        try:
            # Use natural language query for semantic search
            search_text = "precast panels precast concrete connections unispans prefabricated elements construction"
            
            results = self.search_client.search(
                search_text=search_text,
                top=100,  # Get many results to find all projects
                select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                query_type="semantic",  # Semantic search will find similar concepts
                semantic_configuration_name="default"  # Use the semantic configuration we defined
            )
            
            documents = []
            for result in results:
                doc_dict = dict(result)
                
                # More flexible content matching with semantic search
                content = (doc_dict.get('content') or '').lower()
                filename = (doc_dict.get('filename') or '').lower()
                
                # With semantic search, we can be more lenient in filtering
                # Check for precast-related terms in content or filename
                precast_terms = [
                    'precast', 'pre-cast', 'unispan', 'prefab', 'prefabricated',
                    'tilt-up', 'lift-up', 'panel', 'connection'
                ]
                
                # Include if semantic search found it OR if it contains obvious precast terms
                # Lower the threshold for semantic search since Azure might score differently
                if (result.get('@search.score', 0) > 0.1 or  # Lower threshold for semantic match
                    any(term in content or term in filename for term in precast_terms)):
                    documents.append(doc_dict)
            
            logger.info("Found precast documents via semantic search", count=len(documents))
            return documents
            
        except Exception as e:
            logger.error("Precast semantic search failed", error=str(e))
            return []

    def _extract_precast_projects(self, precast_docs: List[Dict]) -> Dict[str, Dict]:
        """Extract unique project numbers from precast documents."""
        projects = {}
        
        for doc in precast_docs:
            blob_url = doc.get('blob_url', '')
            project_id = self._extract_project_from_url(blob_url)
            
            if project_id and len(project_id) >= 6:  # Valid project numbers
                if project_id not in projects:
                    projects[project_id] = {
                        'project_id': project_id,
                        'suitefiles_url': f"https://donthomson.sharepoint.com/sites/suitefiles/AppPages/documents.aspx#/folder/Projects/{project_id}",
                        'document_count': 0,
                        'sample_documents': []
                    }
                
                projects[project_id]['document_count'] += 1
                if len(projects[project_id]['sample_documents']) < 3:
                    projects[project_id]['sample_documents'].append(doc.get('filename', 'Unknown'))
        
        return projects

    def _format_precast_project_answer(self, projects_found: Dict[str, Dict]) -> str:
        """Format the answer for precast project queries."""
        if not projects_found:
            return "I couldn't find any projects with precast panel work in our documents."
        
        project_count = len(projects_found)
        
        if project_count == 1:
            # Single project - more conversational
            project_id, project_info = list(projects_found.items())[0]
            doc_count = project_info['document_count']
            suitefiles_url = project_info['suitefiles_url']
            
            answer = f"I found **Project {project_id}** which has {doc_count} documents related to precast work.\n\n"
            answer += f"📁 **View Project Files:** [Open in SuiteFiles]({suitefiles_url})\n\n"
            answer += "This will take you directly to the project folder where you can access all the precast-related documents."
        else:
            # Multiple projects
            answer = f"I found **{project_count} projects** with precast panel work:\n\n"
            
            project_list = []
            for project_id, project_info in sorted(projects_found.items()):
                doc_count = project_info['document_count']
                suitefiles_url = project_info['suitefiles_url']
                project_list.append(f"• **Project {project_id}** ({doc_count} documents) - [View Files]({suitefiles_url})")
            
            answer += "\n".join(project_list)
            answer += "\n\nClick any link above to access the project folders in SuiteFiles."
        
        return answer

    def _format_precast_sources(self, projects_found: Dict[str, Dict], precast_docs: List[Dict]) -> List[Dict]:
        """Format sources for precast project queries with SuiteFiles URLs."""
        sources = []
        
        for project_id, project_info in sorted(projects_found.items()):
            sample_files = project_info['sample_documents'][:3]
            if sample_files:
                sample_text = f"Including files: {', '.join(sample_files)}"
            else:
                sample_text = "Multiple precast-related documents found"
                
            sources.append({
                'filename': f"Project {project_id}",
                'project_id': project_id,
                'relevance_score': 1.0,
                'blob_url': project_info['suitefiles_url'],
                'excerpt': sample_text
            })
        
        return sources[:10]  # Limit to top 10 projects

    def _is_nz_standards_query(self, question: str) -> bool:
        """Check if the question is asking about NZ Standards, codes, or clauses."""
        if not question:
            return False
        
        question_lower = question.lower()
        
        # NZ Standards and code terms
        standards_terms = [
            "nzs", "nz standard", "new zealand standard", "code", "clause",
            "nzs 3101", "nzs 3404", "nzs 1170", "nzs 3603", "structural code",
            "standard", "requirement", "specification"
        ]
        
        # Technical engineering terms often found in standards queries
        technical_terms = [
            "cover", "clear cover", "minimum cover", "concrete cover",
            "strength reduction", "reduction factor", "phi factor",
            "detailing", "detailing requirement", "reinforcement",
            "beam", "column", "slab", "foundation", "seismic",
            "composite", "diaphragm", "design", "structural design"
        ]
        
        # Question patterns that indicate standards queries
        standards_patterns = [
            "as per", "according to", "per code", "per standard",
            "what clause", "which clause", "tell me", "requirements",
            "minimum", "maximum", "shall", "must", "should"
        ]
        
        # Check for standards/code terms
        has_standards_terms = any(term in question_lower for term in standards_terms)
        
        # Check for technical terms
        has_technical_terms = any(term in question_lower for term in technical_terms)
        
        # Check for standards query patterns
        has_standards_patterns = any(pattern in question_lower for pattern in standards_patterns)
        
        # Return true if we have standards terms OR (technical terms AND standards patterns)
        return has_standards_terms or (has_technical_terms and has_standards_patterns)

    async def _handle_nz_standards_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle NZ Standards and code queries with specialized search for technical requirements."""
        try:
            logger.info("Processing NZ Standards query", question=question)
            
            # Search for standards-related documents
            standards_docs = await self._search_nz_standards_documents(question)
            
            if not standards_docs:
                return {
                    'answer': 'I could not find relevant NZ Standards or code documents to answer your technical query. Please ensure the standards documents are available in the system.',
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': 0
                }
            
            # Prepare enhanced context for standards queries
            context = self._prepare_standards_context(standards_docs, question)
            
            # Generate answer with focus on technical accuracy
            answer_response = await self._generate_standards_answer(question, context)
            
            # Format response with technical sources
            return {
                'answer': answer_response['answer'],
                'sources': [
                    {
                        'filename': doc.get('filename', 'NZ Standards Document'),
                        'project_id': 'NZ Standards',
                        'relevance_score': doc['@search.score'],
                        'blob_url': doc.get('blob_url', ''),
                        'excerpt': self._extract_relevant_clause(doc, question)
                    }
                    for doc in standards_docs[:5]  # Top 5 most relevant standards documents
                ],
                'confidence': answer_response['confidence'],
                'documents_searched': len(standards_docs),
                'processing_time': answer_response.get('processing_time', 0)
            }
            
        except Exception as e:
            logger.error("NZ Standards query failed", error=str(e))
            return {
                'answer': 'I encountered an error while searching NZ Standards documents.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    async def _search_nz_standards_documents(self, question: str) -> List[Dict]:
        """Search for NZ Standards and code documents using semantic search."""
        try:
            # Create a focused search query for standards documents
            search_text = f"{question} NZS standard code clause requirement specification"
            
            results = self.search_client.search(
                search_text=search_text,
                top=50,  # Get more results for comprehensive standards coverage
                select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                query_type="semantic",  # Use semantic search for better technical matching
                semantic_configuration_name="default"
            )
            
            documents = []
            for result in results:
                doc_dict = dict(result)
                
                # Check if document contains standards-related content
                content = (doc_dict.get('content') or '').lower()
                filename = (doc_dict.get('filename') or '').lower()
                
                # Look for NZ Standards indicators
                standards_indicators = [
                    'nzs', 'standard', 'code', 'clause', 'shall', 'must',
                    'requirement', 'specification', 'concrete cover', 'strength reduction',
                    'detailing', 'reinforcement', 'structural design'
                ]
                
                # Include if it's likely a standards document
                if (result.get('@search.score', 0) > 0.1 or  # Good semantic match
                    any(indicator in content or indicator in filename for indicator in standards_indicators)):
                    documents.append(doc_dict)
            
            logger.info("Found NZ Standards documents", count=len(documents))
            return documents
            
        except Exception as e:
            logger.error("NZ Standards search failed", error=str(e))
            return []

    def _prepare_standards_context(self, standards_docs: List[Dict], question: str) -> str:
        """Prepare context specifically for NZ Standards queries with relevant clauses."""
        context_parts = []
        current_length = 0
        
        for doc in standards_docs:
            content = doc.get('content', '')
            filename = doc.get('filename', 'Standards Document')
            
            # Extract relevant sections that might contain clauses or requirements
            relevant_content = self._extract_relevant_standards_content(content, question)
            
            if relevant_content:
                doc_context = f"""
=== {filename} ===
{relevant_content}
---
"""
                
                # Check if adding this document would exceed limit
                if current_length + len(doc_context) > self.max_context_length:
                    break
                    
                context_parts.append(doc_context)
                current_length += len(doc_context)
        
        return "\n".join(context_parts)

    def _extract_relevant_standards_content(self, content: str, question: str) -> str:
        """Extract the most relevant parts of standards documents for the question."""
        if not content:
            return ""
        
        question_lower = question.lower()
        content_lower = content.lower()
        
        # Keywords to look for in the question
        key_terms = []
        if 'cover' in question_lower:
            key_terms.extend(['cover', 'covering', 'concrete cover', 'clear cover'])
        if 'strength reduction' in question_lower or 'reduction factor' in question_lower:
            key_terms.extend(['strength reduction', 'reduction factor', 'phi', 'φ'])
        if 'detailing' in question_lower:
            key_terms.extend(['detailing', 'detail', 'reinforcement detailing'])
        if 'beam' in question_lower:
            key_terms.extend(['beam', 'flexural', 'bending'])
        if 'seismic' in question_lower:
            key_terms.extend(['seismic', 'earthquake', 'ductility'])
        if 'composite' in question_lower:
            key_terms.extend(['composite', 'slab', 'diaphragm'])
        
        # If no specific terms, look for general clause patterns
        if not key_terms:
            key_terms = ['clause', 'shall', 'must', 'requirement', 'minimum', 'maximum']
        
        # Find sentences containing key terms
        sentences = content.split('.')
        relevant_sentences = []
        
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(term in sentence_lower for term in key_terms):
                # Include some context around the relevant sentence
                relevant_sentences.append(sentence.strip())
        
        # Limit to most relevant content
        if relevant_sentences:
            return '. '.join(relevant_sentences[:10]) + '.'  # Max 10 sentences
        else:
            # Fallback to first part of content
            return content[:1500] + "..." if len(content) > 1500 else content

    def _extract_relevant_clause(self, doc: Dict, question: str) -> str:
        """Extract a relevant clause or excerpt from the document for display."""
        content = doc.get('content', '')
        if not content:
            return "NZ Standards document content"
        
        # Look for clause numbers or specific requirements
        relevant_content = self._extract_relevant_standards_content(content, question)
        
        if relevant_content:
            # Limit excerpt length for display
            excerpt = relevant_content[:200] + "..." if len(relevant_content) > 200 else relevant_content
            return excerpt
        else:
            return "NZ Standards technical requirements"

    async def _generate_standards_answer(self, question: str, context: str) -> Dict[str, Any]:
        """Generate answer specifically for NZ Standards queries with technical focus."""
        try:
            import time
            start_time = time.time()
            
            # Enhanced system prompt for NZ Standards queries
            system_prompt = """You are a technical AI assistant specializing in New Zealand Structural Engineering Standards and Codes. You have expert knowledge of NZS codes including NZS 3101 (Concrete), NZS 3404 (Steel), NZS 1170 (Loading), and other structural standards.

            TECHNICAL EXPERTISE AREAS:
            - NZS 3101: Concrete Structures Standard (cover requirements, strength reduction factors, detailing)
            - NZS 3404: Steel Structures Standard (connections, member design, seismic provisions)  
            - NZS 1170: Structural Design Actions (loading, seismic, wind)
            - NZS 3603: Timber Structures Standard
            - Building Code compliance and structural requirements

            RESPONSE REQUIREMENTS:
            1. ACCURACY: Provide precise, technically accurate information from NZ Standards
            2. CITE CLAUSES: Always reference specific clause numbers when available (e.g., "Clause 5.3.2 of NZS 3101")
            3. TECHNICAL DETAIL: Include specific values, formulas, and requirements
            4. CODE COMPLIANCE: Focus on compliance requirements and mandatory provisions
            5. PRACTICAL APPLICATION: Explain how the requirements apply in practice

            ANSWER FORMAT:
            - Lead with the specific requirement or answer
            - Cite the relevant NZS code and clause number
            - Provide technical details (values, formulas, conditions)
            - Explain any important exceptions or special cases
            - Be precise and avoid generalizations

            EXAMPLE RESPONSES:
            - "According to Clause 9.3.1 of NZS 3101:2006, the minimum cover to reinforcement shall be..."
            - "NZS 3101 specifies strength reduction factors (φ) in Table 7.1: φ = 0.85 for flexure, φ = 0.75 for shear..."
            - "For composite slabs acting as diaphragms, refer to NZS 3404 Part 1, specifically Clause 12.8.2..."
            """
            
            # Technical user prompt for standards queries
            user_prompt = f"""
            TECHNICAL STANDARDS QUERY: {question}

            AVAILABLE NZ STANDARDS DOCUMENTATION:
            {context if context.strip() else "Limited standards documentation available."}

            INSTRUCTIONS:
            - Extract specific requirements, clause numbers, and technical values from the provided standards documentation
            - If specific clause numbers are found, cite them precisely
            - Include exact values, formulas, and technical requirements
            - If the information is not in the provided documentation, clearly state this limitation
            - Focus on compliance requirements and mandatory provisions
            - Be technically precise and avoid approximations

            Provide a comprehensive, technically accurate answer based on the NZ Standards documentation provided.
            """
            
            # Call OpenAI with technical parameters
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # Very low temperature for technical accuracy
                max_tokens=1000   # Longer responses for detailed technical information
            )
            
            answer = response.choices[0].message.content
            processing_time = time.time() - start_time
            
            # Assess confidence for technical content
            confidence = self._assess_standards_confidence(answer, context)
            
            logger.info("Generated NZ Standards answer", 
                       question=question, 
                       answer_length=len(answer),
                       confidence=confidence,
                       processing_time=processing_time)
            
            return {
                'answer': answer,
                'confidence': confidence,
                'processing_time': processing_time
            }
            
        except Exception as e:
            logger.error("Standards answer generation failed", error=str(e), question=question)
            return {
                'answer': 'I encountered an error while processing the NZ Standards query.',
                'confidence': 'error',
                'processing_time': 0
            }

    def _assess_standards_confidence(self, answer: str, context: str) -> str:
        """Assess confidence level specifically for NZ Standards answers."""
        # Check for technical indicators of good standards content
        technical_indicators = [
            'clause', 'nzs', 'standard', 'shall', 'minimum', 'maximum',
            'requirement', 'specification', 'table', 'figure'
        ]
        
        answer_lower = answer.lower()
        has_technical_content = sum(1 for indicator in technical_indicators if indicator in answer_lower)
        
        # High confidence if answer contains multiple technical indicators and good context
        if has_technical_content >= 3 and len(context) > 1000:
            return 'high'
        elif has_technical_content >= 2 and len(context) > 500:
            return 'medium'
        elif len(context) > 0:
            return 'medium'
        else:
            return 'low'

    def _is_web_search_query(self, question: str) -> bool:
        """Check if the question is asking for online/external resources."""
        if not question:
            return False
        
        question_lower = question.lower()
        
        # Online/external resource indicators
        online_indicators = [
            "online", "web", "internet", "public", "forum", "thread", "discussion",
            "external", "outside", "accessible", "available online", "website",
            "blog", "article", "reference", "link", "url", "anonymous", 
            "community", "social", "reddit", "stackexchange", "linkedin"
        ]
        
        # Request types for external content
        external_requests = [
            "look for", "search for", "find online", "provide links", 
            "external references", "public discussions", "online threads",
            "web resources", "internet sources", "forum posts"
        ]
        
        # Check for online indicators
        has_online_indicators = any(indicator in question_lower for indicator in online_indicators)
        
        # Check for external request patterns
        has_external_request = any(request in question_lower for request in external_requests)
        
        # Return true if it's clearly asking for online/external resources
        return has_online_indicators or has_external_request

    async def _handle_web_search_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle queries requiring web search for external resources."""
        try:
            logger.info("Processing web search query", question=question)
            
            # Import web search service
            from .web_search_service import WebSearchService
            
            # Determine search type based on question content
            search_type = "all"
            if "nz" in question.lower() or "new zealand" in question.lower():
                search_type = "nz"
            elif "forum" in question.lower() or "thread" in question.lower():
                search_type = "forums"
            elif "guideline" in question.lower() or "standard" in question.lower():
                search_type = "technical"
            
            # Perform web search
            async with WebSearchService() as web_search:
                search_results = await web_search.comprehensive_search(question, search_type)
            
            # Format the response
            answer = self._format_web_search_answer(question, search_results)
            sources = self._format_web_search_sources(search_results)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'medium',  # Web search results have medium confidence
                'documents_searched': sum(len(results) for results in search_results.values()),
                'search_type': 'web_search'
            }
            
        except Exception as e:
            logger.error("Web search query failed", error=str(e))
            return {
                'answer': 'I encountered an error while searching for online resources. You might want to try searching engineering forums like Reddit r/StructuralEngineering, Engineering StackExchange, or SESOC resources directly.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    def _format_web_search_answer(self, question: str, search_results: Dict[str, List[Dict]]) -> str:
        """Format web search results into a comprehensive answer."""
        answer_parts = []
        
        # Introduction
        answer_parts.append("Based on your request for online resources and discussions, here are relevant external references:")
        
        # Forums and discussions
        if search_results.get("forums"):
            answer_parts.append("\n🗣️ **Engineering Forums & Discussions:**")
            for result in search_results["forums"][:3]:
                answer_parts.append(f"• [{result['title']}]({result['url']})")
                answer_parts.append(f"  {result['snippet']}")
        
        # NZ specific resources
        if search_results.get("nz_resources"):
            answer_parts.append("\n🇳🇿 **New Zealand Engineering Resources:**")
            for result in search_results["nz_resources"][:3]:
                answer_parts.append(f"• [{result['title']}]({result['url']})")
                answer_parts.append(f"  {result['snippet']}")
        
        # Technical publications
        if search_results.get("technical_publications"):
            answer_parts.append("\n📚 **Technical Publications & Guidelines:**")
            for result in search_results["technical_publications"][:3]:
                answer_parts.append(f"• [{result['title']}]({result['url']})")
                answer_parts.append(f"  {result['snippet']}")
        
        # Additional recommendations
        answer_parts.append("\n💡 **Additional Recommended Resources:**")
        answer_parts.append("• **Reddit r/StructuralEngineering** - Active community discussions")
        answer_parts.append("• **Engineering StackExchange** - Q&A format with expert answers")
        answer_parts.append("• **SESOC (sesoc.org.nz)** - NZ structural engineering society")
        answer_parts.append("• **IPENZ/Engineering NZ** - Professional engineering body")
        answer_parts.append("• **Structural Engineering forums** on LinkedIn")
        
        return "\n".join(answer_parts)

    def _format_web_search_sources(self, search_results: Dict[str, List[Dict]]) -> List[Dict]:
        """Format web search results as sources."""
        sources = []
        
        for category, results in search_results.items():
            for result in results:
                sources.append({
                    'filename': result.get('title', 'External Resource'),
                    'project_id': f"External ({category})",
                    'relevance_score': result.get('relevance_score', 0.8),
                    'blob_url': result.get('url', ''),
                    'excerpt': result.get('snippet', '')[:200] + '...'
                })
        
        return sources

    async def _handle_contractor_search_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle queries asking about builders, contractors, or construction companies."""
        try:
            logger.info("Processing contractor search query", question=question)
            
            # Search for documents mentioning contractors, builders, or construction companies
            contractor_search_terms = [
                "contractor", "builder", "construction company", "built by", 
                "constructed by", "main contractor", "subcontractor",
                "building company", "construction team", "project manager"
            ]
            
            # Create search query focusing on contractor information
            search_query = f"{question} contractor builder construction company"
            
            # Search documents
            results = self.search_client.search(
                search_text=search_query,
                top=50,
                select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                query_type="semantic",
                semantic_configuration_name="default"
            )
            
            contractor_docs = []
            contractor_info = {}
            
            for result in results:
                doc_dict = dict(result)
                content = (doc_dict.get('content') or '').lower()
                
                # Look for contractor mentions in the content
                if any(term in content for term in contractor_search_terms):
                    contractor_docs.append(doc_dict)
                    
                    # Extract contractor names and contact info using regex
                    project_id = doc_dict.get('project_name', 'Unknown')
                    contractors = self._extract_contractor_info(doc_dict.get('content', ''))
                    
                    if contractors and project_id not in contractor_info:
                        contractor_info[project_id] = contractors
            
            if not contractor_docs:
                return {
                    'answer': 'I could not find specific contractor or builder information in our project documents. You might want to check project correspondence or construction documentation directly.',
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': 0
                }
            
            # Format the answer
            answer = self._format_contractor_answer(contractor_info, question)
            sources = self._format_contractor_sources(contractor_docs)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'medium',
                'documents_searched': len(contractor_docs)
            }
            
        except Exception as e:
            logger.error("Contractor search query failed", error=str(e))
            return {
                'answer': 'I encountered an error while searching for contractor information.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    def _extract_contractor_info(self, content: str) -> List[Dict[str, str]]:
        """Extract contractor names and contact information from document content."""
        contractors = []
        
        # Common patterns for contractor information
        contractor_patterns = [
            r'(?:contractor|builder|construction)\s*[:\-]?\s*([A-Z][A-Za-z\s&\.]+(?:Ltd|Limited|Inc|Corporation)?)',
            r'(?:built by|constructed by|main contractor)\s*[:\-]?\s*([A-Z][A-Za-z\s&\.]+)',
            r'([A-Z][A-Za-z\s&\.]+(?:Construction|Building|Contractors?))',
        ]
        
        # Email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        
        # Phone pattern (NZ format)
        phone_pattern = r'(?:\+64|0)[2-9]\d{7,9}'
        
        for pattern in contractor_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                contractor_name = match.strip()
                if len(contractor_name) > 3:  # Filter out very short matches
                    
                    # Look for contact info near the contractor name
                    context_start = max(0, content.find(contractor_name) - 200)
                    context_end = min(len(content), content.find(contractor_name) + len(contractor_name) + 200)
                    context = content[context_start:context_end]
                    
                    emails = re.findall(email_pattern, context)
                    phones = re.findall(phone_pattern, context)
                    
                    contractors.append({
                        'name': contractor_name,
                        'emails': emails,
                        'phones': phones
                    })
        
        return contractors

    def _format_contractor_answer(self, contractor_info: Dict[str, List[Dict]], question: str) -> str:
        """Format contractor information into a readable answer."""
        if not contractor_info:
            return "I could not find specific contractor information in the available documents."
        
        answer_parts = []
        answer_parts.append("Based on our project documents, here are the contractors and builders we've worked with:")
        
        for project_id, contractors in contractor_info.items():
            answer_parts.append(f"\n🏗️ **Project {project_id}:**")
            
            for contractor in contractors:
                answer_parts.append(f"• **{contractor['name']}**")
                
                if contractor['emails']:
                    answer_parts.append(f"  📧 Email: {', '.join(contractor['emails'])}")
                
                if contractor['phones']:
                    answer_parts.append(f"  📞 Phone: {', '.join(contractor['phones'])}")
        
        # Add recommendations based on the question
        if "steel" in question.lower() and "retrofit" in question.lower():
            answer_parts.append("\n💡 **For steel structure retrofits, consider:**")
            answer_parts.append("• Contractors with steel construction experience")
            answer_parts.append("• Companies familiar with heritage/existing building work")
            answer_parts.append("• Builders experienced with structural modifications")
        
        answer_parts.append("\n⚠️ **Note:** This information is from project documents. Please verify current contact details and availability.")
        
        return "\n".join(answer_parts)

    def _format_contractor_sources(self, contractor_docs: List[Dict]) -> List[Dict]:
        """Format contractor documents as sources."""
        sources = []
        
        for doc in contractor_docs[:5]:  # Limit to top 5 sources
            sources.append({
                'filename': doc.get('filename', 'Unknown Document'),
                'project_id': doc.get('project_name', 'Unknown Project'),
                'relevance_score': doc.get('@search.score', 0.8),
                'blob_url': doc.get('blob_url', ''),
                'excerpt': (doc.get('content', '')[:200] + '...') if doc.get('content') else ''
            })
        
        return sources

    async def _handle_scenario_technical_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle scenario-based technical queries that combine building type, conditions, and location."""
        try:
            logger.info("Processing scenario-based technical query", question=question)
            
            # Extract scenario components from the question
            scenario_components = self._extract_scenario_components(question)
            
            # Build enhanced search terms for scenario matching
            search_terms = self._build_scenario_search_terms(question, scenario_components)
            
            # Search with scenario-optimized terms
            relevant_docs = await self._search_scenario_documents(search_terms, scenario_components)
            
            if not relevant_docs:
                return {
                    'answer': f"I couldn't find specific examples matching your criteria: {scenario_components.get('summary', question)}. Try searching for broader terms or check if there are similar projects with different conditions.",
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': 0,
                    'search_type': 'scenario_technical'
                }
            
            # Generate scenario-specific answer
            answer = await self._generate_scenario_answer(question, relevant_docs, scenario_components)
            
            # Format sources with project context
            sources = self._format_scenario_sources(relevant_docs, scenario_components)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'high' if len(relevant_docs) >= 3 else 'medium',
                'documents_searched': len(relevant_docs),
                'search_type': 'scenario_technical',
                'scenario_components': scenario_components
            }
            
        except Exception as e:
            logger.error("Scenario technical query failed", error=str(e))
            return {
                'answer': 'I encountered an error while searching for scenario-based examples. Please try rephrasing your query or search for individual components.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    def _extract_scenario_components(self, question: str) -> Dict[str, Any]:
        """Extract building type, conditions, location, and system components from scenario query."""
        question_lower = question.lower()
        
        components = {
            'building_types': [],
            'structural_systems': [],
            'environmental_conditions': [],
            'locations': [],
            'specific_elements': [],
            'summary': ''
        }
        
        # Building types
        building_types = {
            'mid-rise': ['mid-rise', 'medium rise', 'multi-story', 'multi-storey'],
            'timber frame': ['timber frame', 'wood frame', 'timber construction'],
            'apartment': ['apartment', 'residential complex', 'unit'],
            'house': ['house', 'dwelling', 'home', 'residence'],
            'commercial': ['commercial', 'office', 'retail']
        }
        
        # Structural systems
        structural_systems = {
            'concrete shear walls': ['concrete shear wall', 'shear wall', 'concrete wall'],
            'foundation': ['foundation', 'footing', 'pile', 'basement'],
            'timber frame': ['timber frame', 'wood frame', 'CLT', 'LVL'],
            'steel frame': ['steel frame', 'steel structure', 'structural steel'],
            'connections': ['connection', 'joint', 'fastener', 'bracket']
        }
        
        # Environmental conditions
        environmental_conditions = {
            'high wind': ['high wind', 'wind zone', 'cyclone', 'hurricane', 'wind load'],
            'seismic': ['seismic', 'earthquake', 'seismic strengthening', 'seismic zone'],
            'coastal': ['coastal', 'marine', 'salt exposure', 'corrosion'],
            'steep slope': ['steep slope', 'sloping site', 'hillside', 'gradient']
        }
        
        # Locations
        locations = {
            'wellington': ['wellington', 'wgtn'],
            'auckland': ['auckland', 'akl'],
            'christchurch': ['christchurch', 'chch'],
            'queenstown': ['queenstown'],
            'coastal': ['coastal', 'beachfront', 'waterfront']
        }
        
        # Specific elements
        specific_elements = {
            'balcony': ['balcony', 'deck', 'terrace'],
            'connections': ['connection detail', 'connection', 'joint detail'],
            'foundation system': ['foundation system', 'foundation type'],
            'reinforcement': ['reinforcement', 'strengthening', 'retrofit']
        }
        
        # Extract components
        for category, terms_dict in [
            ('building_types', building_types),
            ('structural_systems', structural_systems), 
            ('environmental_conditions', environmental_conditions),
            ('locations', locations),
            ('specific_elements', specific_elements)
        ]:
            for key, terms in terms_dict.items():
                if any(term in question_lower for term in terms):
                    components[category].append(key)
        
        # Create summary
        summary_parts = []
        if components['building_types']:
            summary_parts.append(f"Building: {', '.join(components['building_types'])}")
        if components['structural_systems']:
            summary_parts.append(f"Structure: {', '.join(components['structural_systems'])}")
        if components['environmental_conditions']:
            summary_parts.append(f"Conditions: {', '.join(components['environmental_conditions'])}")
        if components['locations']:
            summary_parts.append(f"Location: {', '.join(components['locations'])}")
        if components['specific_elements']:
            summary_parts.append(f"Elements: {', '.join(components['specific_elements'])}")
            
        components['summary'] = " | ".join(summary_parts) if summary_parts else question
        
        return components

    def _build_scenario_search_terms(self, question: str, components: Dict[str, Any]) -> str:
        """Build optimized search terms for scenario matching."""
        search_terms = []
        
        # Add original question terms
        search_terms.append(question)
        
        # Add component-specific terms
        for category in ['building_types', 'structural_systems', 'environmental_conditions', 'locations', 'specific_elements']:
            search_terms.extend(components.get(category, []))
        
        # Add technical document keywords that might contain these scenarios
        technical_keywords = [
            'structural calculation', 'design report', 'engineering analysis',
            'project summary', 'design brief', 'structural drawing',
            'specification', 'technical report', 'assessment'
        ]
        search_terms.extend(technical_keywords)
        
        return " OR ".join(f'"{term}"' for term in search_terms[:15])  # Limit to prevent too long query

    async def _search_scenario_documents(self, search_terms: str, components: Dict[str, Any]) -> List[Dict]:
        """Search for documents matching scenario criteria."""
        try:
            # Search with broader terms first
            results = self.search_client.search(
                search_text=search_terms,
                top=30,
                highlight_fields="filename,project_name,content",
                select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                search_mode="any"
            )
            
            relevant_docs = []
            seen_projects = set()
            
            for result in results:
                # Score documents based on how many scenario components they match
                score = self._calculate_scenario_relevance(result, components)
                
                if score > 0.3:  # Minimum relevance threshold
                    # Avoid duplicate projects unless they're highly relevant
                    project_id = result.get('project_name', 'unknown')
                    if project_id not in seen_projects or score > 0.8:
                        result['scenario_score'] = score
                        relevant_docs.append(result)
                        seen_projects.add(project_id)
            
            # Sort by scenario relevance score
            relevant_docs.sort(key=lambda x: x.get('scenario_score', 0), reverse=True)
            
            logger.info("Scenario document search completed", 
                       total_found=len(relevant_docs),
                       components=components['summary'])
            
            return relevant_docs[:10]  # Top 10 most relevant
            
        except Exception as e:
            logger.error("Scenario document search failed", error=str(e))
            return []

    def _calculate_scenario_relevance(self, document: Dict, components: Dict[str, Any]) -> float:
        """Calculate how well a document matches the scenario components."""
        content = (
            (document.get('content') or '') + ' ' + 
            (document.get('filename') or '') + ' ' + 
            (document.get('project_name') or '')
        ).lower()
        
        score = 0.0
        total_components = 0
        
        # Check each component category
        for category in ['building_types', 'structural_systems', 'environmental_conditions', 'locations', 'specific_elements']:
            components_list = components.get(category, [])
            if components_list:
                total_components += len(components_list)
                for component in components_list:
                    if component.lower() in content:
                        # Weight different categories
                        if category == 'structural_systems':
                            score += 0.3  # Structural systems are most important
                        elif category == 'environmental_conditions':
                            score += 0.25
                        elif category == 'building_types':
                            score += 0.2
                        elif category == 'locations':
                            score += 0.15
                        else:
                            score += 0.1
        
        # Normalize score
        if total_components > 0:
            score = score / total_components
        
        # Bonus for documents that match multiple categories
        matched_categories = sum(1 for category in ['building_types', 'structural_systems', 'environmental_conditions', 'locations'] 
                               if any(comp.lower() in content for comp in components.get(category, [])))
        
        if matched_categories >= 2:
            score += 0.2
        if matched_categories >= 3:
            score += 0.3
            
        return min(score, 1.0)  # Cap at 1.0

    async def _generate_scenario_answer(self, question: str, documents: List[Dict], components: Dict[str, Any]) -> str:
        """Generate a comprehensive answer for scenario-based queries."""
        if not documents:
            return "No matching examples found for your scenario criteria."
        
        # Create context from top documents
        context_parts = []
        for i, doc in enumerate(documents[:5]):
            project = doc.get('project_name', 'Unknown Project')
            filename = doc.get('filename', 'Unknown Document')
            content_excerpt = doc.get('content', '')[:500]
            
            context_parts.append(f"Document {i+1}: {filename} (Project: {project})\n{content_excerpt}...")
        
        context = "\n\n".join(context_parts)
        
        # Generate AI response with scenario context
        scenario_prompt = f"""Based on the following engineering documents from DTCE projects, provide a comprehensive answer for this scenario-based query:

Question: {question}

Scenario Components Identified: {components['summary']}

Relevant Project Documents:
{context}

Please provide:
1. **Examples Found**: List specific projects that match the scenario criteria
2. **Technical Details**: Key structural systems, connection details, or design approaches used
3. **Location-Specific Considerations**: Any location-specific factors (wind, seismic, coastal, etc.)
4. **Design Solutions**: Specific solutions, products, or methodologies employed
5. **References**: Which projects/documents contain the most relevant information

Format your response with clear headings and bullet points. Focus on practical engineering information that can be applied to similar scenarios."""

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a senior structural engineer analyzing DTCE project documents to provide scenario-based technical guidance."},
                    {"role": "user", "content": scenario_prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error("Scenario answer generation failed", error=str(e))
            return f"Found {len(documents)} relevant examples matching your scenario criteria. Please review the source documents for detailed technical information."

    def _format_scenario_sources(self, documents: List[Dict], components: Dict[str, Any]) -> List[Dict]:
        """Format scenario-based document sources with enhanced context."""
        sources = []
        
        for doc in documents[:5]:
            scenario_score = doc.get('scenario_score', 0)
            filename = doc.get('filename', 'Unknown Document')
            
            # Handle case where filename is literally 'None' or missing
            if not filename or filename == 'None':
                # Try to create a meaningful filename from content
                filename = self._generate_meaningful_filename(doc)
            
            sources.append({
                'filename': filename,
                'project_id': self._extract_project_from_document(doc), 
                'relevance_score': doc.get('@search.score', scenario_score),
                'scenario_score': round(scenario_score, 2),
                'blob_url': doc.get('blob_url', ''),
                'excerpt': (doc.get('content', '')[:200] + '...') if doc.get('content') else '',
                'matching_components': components['summary']
            })
        
        return sources

    async def _handle_regulatory_precedent_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle queries about regulatory challenges, council interactions, alternative solutions, and consent precedents."""
        try:
            logger.info("Processing regulatory precedent query", question=question)
            
            # Extract regulatory components from the question
            regulatory_components = self._extract_regulatory_components(question)
            
            # Build search terms focused on regulatory documents
            search_terms = self._build_regulatory_search_terms(question, regulatory_components)
            
            # Search for regulatory/consent-related documents
            relevant_docs = await self._search_regulatory_documents(search_terms, regulatory_components)
            
            if not relevant_docs:
                return {
                    'answer': f"I couldn't find specific examples of regulatory precedents for: {regulatory_components.get('summary', question)}. Try searching for broader terms or check council correspondence files.",
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': 0,
                    'search_type': 'regulatory_precedent'
                }
            
            # Generate regulatory-focused answer
            answer = await self._generate_regulatory_answer(question, relevant_docs, regulatory_components)
            sources = self._format_regulatory_sources(relevant_docs, regulatory_components)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'high' if len(relevant_docs) >= 3 else 'medium',
                'documents_searched': len(relevant_docs),
                'search_type': 'regulatory_precedent',
                'regulatory_components': regulatory_components
            }
            
        except Exception as e:
            logger.error("Regulatory precedent query failed", error=str(e))
            return {
                'answer': 'I encountered an error while searching for regulatory precedents. Please try searching for specific project names or council correspondence.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    async def _handle_cost_time_insights_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle queries about project timelines, costs, durations, and scope changes."""
        try:
            logger.info("Processing cost/time insights query", question=question)
            
            # Extract cost/time components from the question
            cost_time_components = self._extract_cost_time_components(question)
            
            # Build search terms focused on project timeline and cost documents
            search_terms = self._build_cost_time_search_terms(question, cost_time_components)
            
            # Search for cost/time-related documents
            relevant_docs = await self._search_cost_time_documents(search_terms, cost_time_components)
            
            if not relevant_docs:
                return {
                    'answer': f"I couldn't find specific cost or timeline information for: {cost_time_components.get('summary', question)}. Try searching for project reports, fee proposals, or correspondence files.",
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': 0,
                    'search_type': 'cost_time_insights',
                    'cost_time_components': cost_time_components
                }
            
            # Generate AI answer focused on cost/time insights
            answer = await self._generate_cost_time_answer(question, relevant_docs, cost_time_components)
            sources = self._format_cost_time_sources(relevant_docs, cost_time_components)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'high' if len(relevant_docs) >= 3 else 'medium',
                'documents_searched': len(relevant_docs),
                'search_type': 'cost_time_insights',
                'cost_time_components': cost_time_components
            }
            
        except Exception as e:
            logger.error("Cost/time insights query failed", error=str(e))
            return {
                'answer': 'I encountered an error while searching for cost and timeline information. Please try searching for specific project types or timeframe ranges.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    def _extract_cost_time_components(self, question: str) -> Dict[str, Any]:
        """Extract cost, timeline, and project duration components from the query."""
        question_lower = question.lower()
        
        components = {
            'timeline_types': [],
            'cost_types': [],
            'project_types': [],
            'scope_aspects': [],
            'duration_indicators': []
        }
        
        # Timeline and milestone types
        timeline_types = {
            'concept_to_ps1': ['concept to ps1', 'concept design to ps1', 'initial to ps1'],
            'ps1_to_completion': ['ps1 to completion', 'ps1 to finished', 'ps1 to end'],
            'design_phase': ['design phase', 'design duration', 'design time'],
            'consent_process': ['consent time', 'consent duration', 'building consent', 'approval time'],
            'total_project': ['total duration', 'project length', 'start to finish', 'overall timeline'],
            'milestone_phases': ['phases', 'milestones', 'stages']
        }
        
        # Cost categories
        cost_types = {
            'structural_design': ['structural design cost', 'engineering fee', 'structural fee'],
            'total_project_cost': ['total cost', 'project cost', 'overall cost'],
            'design_fees': ['design fee', 'consultant fee', 'professional fee'],
            'scope_expansion': ['scope increase', 'additional work', 'extra cost', 'cost overrun'],
            'cost_range': ['cost range', 'typical cost', 'cost estimate', 'budget range']
        }
        
        # Project types and categories
        project_types = {
            'commercial_alterations': ['commercial alteration', 'commercial renovation', 'office alteration'],
            'residential': ['residential', 'house', 'home', 'dwelling'],
            'multi_unit': ['multi-unit', 'apartment', 'townhouse', 'duplex'],
            'industrial': ['industrial', 'warehouse', 'factory'],
            'heritage': ['heritage', 'historic', 'character building'],
            'new_build': ['new build', 'new construction', 'new development'],
            'small_projects': ['small', 'minor', 'simple'],
            'large_projects': ['large', 'major', 'complex']
        }
        
        # Scope change indicators
        scope_aspects = {
            'scope_expansion': ['scope expanded', 'scope increased', 'additional work', 'scope change', 'expanded significantly', 'scope grew', 'scope expansion', 'extra scope'],
            'scope_reduction': ['scope reduced', 'scope decreased', 'scope cut'],
            'design_changes': ['design change', 'design revision', 'redesign'],
            'structural_additions': ['structural addition', 'extra structural', 'additional structural']
        }
        
        # Duration and time indicators
        duration_indicators = {
            'typical_duration': ['typical', 'usually', 'normally', 'average'],
            'fast_track': ['fast', 'quick', 'urgent', 'expedited'],
            'extended_timeline': ['long', 'extended', 'delayed', 'slow'],
            'specific_timeframes': ['weeks', 'months', 'days', 'years']
        }
        
        # Extract components
        for category, terms_dict in [
            ('timeline_types', timeline_types),
            ('cost_types', cost_types),
            ('project_types', project_types),
            ('scope_aspects', scope_aspects),
            ('duration_indicators', duration_indicators)
        ]:
            for key, terms in terms_dict.items():
                if any(term in question_lower for term in terms):
                    components[category].append(key)
        
        # Create summary
        summary_parts = []
        if components['timeline_types']:
            summary_parts.append(f"Timeline: {', '.join(components['timeline_types'])}")
        if components['cost_types']:
            summary_parts.append(f"Cost: {', '.join(components['cost_types'])}")
        if components['project_types']:
            summary_parts.append(f"Projects: {', '.join(components['project_types'])}")
        if components['scope_aspects']:
            summary_parts.append(f"Scope: {', '.join(components['scope_aspects'])}")
        if components['duration_indicators']:
            summary_parts.append(f"Duration: {', '.join(components['duration_indicators'])}")
            
        components['summary'] = " | ".join(summary_parts) if summary_parts else question
        
        return components

    def _build_cost_time_search_terms(self, question: str, components: Dict[str, Any]) -> str:
        """Build search terms optimized for finding cost and timeline documents."""
        search_terms = []
        
        # Add original question
        search_terms.append(question)
        
        # Add cost/time-specific terms
        cost_time_keywords = [
            # Timeline terms
            'timeline', 'duration', 'time', 'schedule', 'milestone', 'phase',
            'concept design', 'ps1', 'ps3', 'completion', 'start', 'finish',
            
            # Cost terms
            'cost', 'fee', 'budget', 'price', 'estimate', 'proposal', 'quote',
            'structural design fee', 'engineering cost', 'professional fee',
            
            # Project phases
            'concept', 'developed design', 'detailed design', 'consent',
            'construction', 'completion', 'sign-off',
            
            # Scope terms
            'scope', 'additional work', 'variation', 'change', 'expansion',
            'extra', 'revised scope', 'scope increase',
            
            # Document types
            'fee proposal', 'report', 'correspondence', 'memo', 'email',
            'project brief', 'scope document'
        ]
        
        # Add component-specific terms
        for category in ['timeline_types', 'cost_types', 'project_types', 'scope_aspects', 'duration_indicators']:
            search_terms.extend(components.get(category, []))
        
        # Add cost/time keywords
        search_terms.extend(cost_time_keywords)
        
        return " OR ".join(f'"{term}"' for term in search_terms[:25])  # Limit to prevent too long query

    def _build_best_practices_search_terms(self, question: str, components: Dict[str, Any]) -> str:
        """Build search terms for best practices and templates queries."""
        search_terms = []
        
        # Extract key terms from question
        question_lower = question.lower()
        search_terms.extend([word for word in question_lower.split() if len(word) > 3])
        
        # Add component-specific terms
        for category in ['practice_types', 'template_types', 'methodology_types', 'scope_areas', 'deliverable_types']:
            search_terms.extend(components.get(category, []))
        
        # Add best practices keywords
        best_practices_keywords = [
            'standard approach', 'methodology', 'template', 'procedure', 'guideline',
            'best practice', 'calculation sheet', 'design process', 'quality assurance',
            'specification', 'checklist', 'protocol', 'format', 'process'
        ]
        search_terms.extend(best_practices_keywords)
        
        return " OR ".join(f'"{term}"' for term in search_terms[:25])  # Limit to prevent too long query

    def _build_materials_methods_search_terms(self, question: str, components: Dict[str, Any]) -> str:
        """Build search terms for materials and methods queries."""
        search_terms = []
        
        # Extract key terms from question
        question_lower = question.lower()
        search_terms.extend([word for word in question_lower.split() if len(word) > 3])
        
        # Add component-specific terms
        for category in ['material_types', 'structural_systems', 'comparison_aspects', 'building_elements', 'project_contexts', 'decision_factors']:
            search_terms.extend(components.get(category, []))
        
        # Add materials/methods keywords
        materials_methods_keywords = [
            'material selection', 'concrete', 'steel', 'timber', 'comparison', 'alternative',
            'chosen', 'selected', 'rationale', 'decision', 'performance', 'construction',
            'versus', 'vs', 'compared', 'why', 'because', 'reason'
        ]
        search_terms.extend(materials_methods_keywords)
        
        return " OR ".join(f'"{term}"' for term in search_terms[:25])  # Limit to prevent too long query

    def _build_internal_knowledge_search_terms(self, question: str, components: Dict[str, Any]) -> str:
        """Build search terms for internal knowledge and expertise queries."""
        search_terms = []
        
        # Extract key terms from question
        question_lower = question.lower()
        search_terms.extend([word for word in question_lower.split() if len(word) > 3])
        
        # Add component-specific terms
        for category in ['expertise_areas', 'engineer_roles', 'project_types', 'technical_skills', 'experience_levels', 'knowledge_types']:
            search_terms.extend(components.get(category, []))
        
        # Add internal knowledge keywords
        internal_knowledge_keywords = [
            'engineer', 'expertise', 'experience', 'specialist', 'team', 'staff',
            'designed by', 'checked by', 'responsible', 'involved', 'worked on',
            'skills', 'knowledge', 'capability', 'qualified', 'competent'
        ]
        search_terms.extend(internal_knowledge_keywords)
        
        return " OR ".join(f'"{term}"' for term in search_terms[:25])  # Limit to prevent too long query

    async def _search_cost_time_documents(self, search_terms: str, components: Dict[str, Any]) -> List[Dict]:
        """Search for documents containing cost and timeline information."""
        try:
            # Search with cost/time focus
            results = self.search_client.search(
                search_text=search_terms,
                top=30,
                highlight_fields="filename,project_name,content",
                select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                search_mode="any"
            )
            
            relevant_docs = []
            seen_docs = set()
            
            for result in results:
                # Score documents based on cost/time relevance
                score = self._calculate_cost_time_relevance(result, components)
                
                if score > 0.2:  # Threshold for cost/time relevance
                    # Avoid duplicate documents
                    doc_id = result.get('id', result.get('filename', ''))
                    if doc_id not in seen_docs:
                        result['cost_time_score'] = score
                        relevant_docs.append(result)
                        seen_docs.add(doc_id)
            
            # Sort by cost/time relevance score
            relevant_docs.sort(key=lambda x: x.get('cost_time_score', 0), reverse=True)
            
            logger.info("Cost/time document search completed", 
                       total_found=len(relevant_docs),
                       components=components['summary'])
            
            return relevant_docs[:15]  # Top 15 most relevant
            
        except Exception as e:
            logger.error("Cost/time document search failed", error=str(e))
            return []

    async def _search_best_practices_documents(self, search_terms: str, components: Dict[str, Any]) -> List[Dict]:
        """Search for documents containing best practices and templates."""
        try:
            # Search with best practices focus
            results = self.search_client.search(
                search_text=search_terms,
                top=30,
                highlight_fields="filename,project_name,content",
                select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                filter=None
            )
            
            relevant_docs = []
            seen_docs = set()
            
            for result in results:
                if result.get('id'):
                    doc_id = result['id']
                    if doc_id not in seen_docs:
                        # Calculate best practices relevance
                        score = self._calculate_best_practices_relevance(result, components)
                        if score >= 0.2:  # Threshold for best practices relevance
                            result['best_practices_score'] = score
                            relevant_docs.append(result)
                            seen_docs.add(doc_id)
            
            # Sort by best practices relevance score
            relevant_docs.sort(key=lambda x: x.get('best_practices_score', 0), reverse=True)
            
            logger.info("Best practices document search completed", 
                       total_found=len(relevant_docs),
                       components=components['summary'])
            
            return relevant_docs[:15]  # Top 15 most relevant
            
        except Exception as e:
            logger.error("Best practices document search failed", error=str(e))
            return []

    async def _search_materials_methods_documents(self, search_terms: str, components: Dict[str, Any]) -> List[Dict]:
        """Search for documents containing materials and methods information."""
        try:
            # Search with materials/methods focus
            results = self.search_client.search(
                search_text=search_terms,
                top=30,
                highlight_fields="filename,project_name,content",
                select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                filter=None
            )
            
            relevant_docs = []
            seen_docs = set()
            
            for result in results:
                if result.get('id'):
                    doc_id = result['id']
                    if doc_id not in seen_docs:
                        # Calculate materials/methods relevance
                        score = self._calculate_materials_methods_relevance(result, components)
                        if score >= 0.2:  # Threshold for materials/methods relevance
                            result['materials_methods_score'] = score
                            relevant_docs.append(result)
                            seen_docs.add(doc_id)
            
            # Sort by materials/methods relevance score
            relevant_docs.sort(key=lambda x: x.get('materials_methods_score', 0), reverse=True)
            
            logger.info("Materials/methods document search completed", 
                       total_found=len(relevant_docs),
                       components=components['summary'])
            
            return relevant_docs[:15]  # Top 15 most relevant
            
        except Exception as e:
            logger.error("Materials/methods document search failed", error=str(e))
            return []

    async def _search_internal_knowledge_documents(self, search_terms: str, components: Dict[str, Any]) -> List[Dict]:
        """Search for documents containing internal knowledge and expertise information."""
        try:
            # Search with internal knowledge focus
            results = self.search_client.search(
                search_text=search_terms,
                top=30,
                highlight_fields="filename,project_name,content",
                select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                filter=None
            )
            
            relevant_docs = []
            seen_docs = set()
            
            for result in results:
                if result.get('id'):
                    doc_id = result['id']
                    if doc_id not in seen_docs:
                        # Calculate internal knowledge relevance
                        score = self._calculate_internal_knowledge_relevance(result, components)
                        if score >= 0.2:  # Threshold for internal knowledge relevance
                            result['internal_knowledge_score'] = score
                            relevant_docs.append(result)
                            seen_docs.add(doc_id)
            
            # Sort by internal knowledge relevance score
            relevant_docs.sort(key=lambda x: x.get('internal_knowledge_score', 0), reverse=True)
            
            logger.info("Internal knowledge document search completed", 
                       total_found=len(relevant_docs),
                       components=components['summary'])
            
            return relevant_docs[:15]  # Top 15 most relevant
            
        except Exception as e:
            logger.error("Internal knowledge document search failed", error=str(e))
            return []

    def _calculate_cost_time_relevance(self, document: Dict, components: Dict[str, Any]) -> float:
        """Calculate how well a document matches cost/time analysis criteria."""
        content = (
            (document.get('content') or '') + ' ' + 
            (document.get('filename') or '') + ' ' + 
            (document.get('project_name') or '') + ' ' +
            (document.get('folder') or '')
        ).lower()
        
        score = 0.0
        
        # High-value cost/time indicators
        high_value_terms = {
            'fee_proposal': ['fee proposal', 'proposal', 'quote', 'estimate'],
            'timeline_docs': ['timeline', 'schedule', 'milestone', 'phase'],
            'cost_analysis': ['cost', 'fee', 'budget', 'price'],
            'scope_documents': ['scope', 'brief', 'specification', 'requirements'],
            'scope_changes': ['scope expanded', 'additional work', 'scope change', 'scope increased', 'extra scope'],
            'project_reports': ['report', 'summary', 'review', 'analysis']
        }
        
        for category, terms in high_value_terms.items():
            if all(term in content for term in terms[:2]):  # At least 2 terms must match
                score += 0.4
            elif any(term in content for term in terms):
                score += 0.2
        
        # Document type indicators
        doc_type_indicators = {
            'proposal': 0.35,       # Fee proposals likely to contain cost/time info
            'report': 0.25,         # Project reports may contain timeline info
            'brief': 0.3,           # Project briefs contain scope info
            'correspondence': 0.2,  # Emails may discuss timelines/costs
            'memo': 0.25,           # Internal memos about project status
            'schedule': 0.4,        # Schedules contain timeline info
            'budget': 0.4,          # Budget documents contain cost info
            'scope': 0.35,          # Scope documents contain expansion info
            'variation': 0.4,       # Variations indicate scope changes
            'change': 0.3,          # Change documents indicate scope evolution
            'additional': 0.25      # Additional work documents
        }
        
        for indicator, weight in doc_type_indicators.items():
            if indicator in content:
                score += weight
        
        # Check component matches with higher weight for cost/time terms
        for category in ['timeline_types', 'cost_types', 'scope_aspects']:
            components_list = components.get(category, [])
            for component in components_list:
                if component.replace('_', ' ') in content:
                    score += 0.25
        
        # Project type matches
        for component in components.get('project_types', []):
            if component.replace('_', ' ') in content:
                score += 0.15
        
        return min(score, 1.0)  # Cap at 1.0

    def _calculate_best_practices_relevance(self, document: Dict, components: Dict[str, Any]) -> float:
        """Calculate how well a document matches best practices criteria."""
        content = (
            (document.get('content') or '') + ' ' + 
            (document.get('filename') or '') + ' ' + 
            (document.get('project_name') or '')
        ).lower()
        
        score = 0.0
        
        # High-value best practices indicators
        high_value_terms = {
            'methodology': ['methodology', 'approach', 'method', 'procedure'],
            'template': ['template', 'standard', 'format', 'form'],
            'practice': ['practice', 'guideline', 'protocol', 'process'],
            'calculation': ['calculation', 'calc', 'analysis', 'design'],
            'specification': ['specification', 'spec', 'requirement', 'criteria'],
            'checklist': ['checklist', 'check', 'verification', 'review']
        }
        
        for category, terms in high_value_terms.items():
            if all(term in content for term in terms[:2]):  # At least 2 terms must match
                score += 0.4
            elif any(term in content for term in terms):
                score += 0.2
        
        # Document type indicators for best practices
        doc_type_indicators = {
            'template': 0.4,        # Templates are direct best practices
            'standard': 0.4,        # Standards contain best practices
            'guideline': 0.35,      # Guidelines are best practices
            'procedure': 0.35,      # Procedures are methodologies
            'manual': 0.3,          # Manuals contain practices
            'specification': 0.3,   # Specs contain standard approaches
            'calculation': 0.25,    # Calculations show methods
            'report': 0.2,          # Reports may contain methodologies
            'methodology': 0.4,     # Direct methodology documents
            'approach': 0.3,        # Approach documents
            'process': 0.3,         # Process documents
            'checklist': 0.35       # Checklists are templates
        }
        
        for indicator, weight in doc_type_indicators.items():
            if indicator in content:
                score += weight
        
        # Check component matches
        for category in ['practice_types', 'template_types', 'methodology_types']:
            components_list = components.get(category, [])
            for component in components_list:
                if component.replace('_', ' ') in content:
                    score += 0.25
        
        # Scope and deliverable matches
        for category in ['scope_areas', 'deliverable_types']:
            components_list = components.get(category, [])
            for component in components_list:
                if component.replace('_', ' ') in content:
                    score += 0.15
        
        return min(score, 1.0)  # Cap at 1.0

    def _calculate_materials_methods_relevance(self, document: Dict, components: Dict[str, Any]) -> float:
        """Calculate how well a document matches materials/methods criteria."""
        content = (
            (document.get('content') or '') + ' ' + 
            (document.get('filename') or '') + ' ' + 
            (document.get('project_name') or '')
        ).lower()
        
        score = 0.0
        
        # High-value materials/methods indicators
        high_value_terms = {
            'material_selection': ['material selection', 'chosen', 'selected', 'opted'],
            'comparison': ['comparison', 'compared', 'versus', 'vs', 'alternative'],
            'decision': ['decision', 'rationale', 'reason', 'why', 'because'],
            'performance': ['performance', 'strength', 'durability', 'behavior'],
            'construction': ['construction', 'buildability', 'installation', 'erection'],
            'cost_benefit': ['cost', 'economic', 'budget', 'expensive', 'cheaper']
        }
        
        for category, terms in high_value_terms.items():
            if all(term in content for term in terms[:2]):  # At least 2 terms must match
                score += 0.4
            elif any(term in content for term in terms):
                score += 0.2
        
        # Document type indicators for materials/methods
        doc_type_indicators = {
            'specification': 0.4,   # Specs contain material choices
            'report': 0.3,          # Reports explain decisions
            'calculation': 0.3,     # Calcs show material properties
            'comparison': 0.4,      # Direct comparison documents
            'assessment': 0.35,     # Assessments compare options
            'analysis': 0.3,        # Analysis documents
            'design': 0.25,         # Design docs show choices
            'structural': 0.2,      # Structural docs use materials
            'methodology': 0.3,     # Methodologies explain approaches
            'rationale': 0.4,       # Rationale explains decisions
            'option': 0.35,         # Option documents compare
            'alternative': 0.35     # Alternative assessments
        }
        
        for indicator, weight in doc_type_indicators.items():
            if indicator in content:
                score += weight
        
        # Check component matches
        for category in ['material_types', 'structural_systems', 'comparison_aspects']:
            components_list = components.get(category, [])
            for component in components_list:
                if component.replace('_', ' ') in content:
                    score += 0.25
        
        # Building elements and context matches
        for category in ['building_elements', 'project_contexts', 'decision_factors']:
            components_list = components.get(category, [])
            for component in components_list:
                if component.replace('_', ' ') in content:
                    score += 0.15
        
        return min(score, 1.0)  # Cap at 1.0

    def _calculate_internal_knowledge_relevance(self, document: Dict, components: Dict[str, Any]) -> float:
        """Calculate how well a document matches internal knowledge criteria."""
        content = (
            (document.get('content') or '') + ' ' + 
            (document.get('filename') or '') + ' ' + 
            (document.get('project_name') or '')
        ).lower()
        
        score = 0.0
        
        # High-value internal knowledge indicators
        high_value_terms = {
            'engineer_names': ['engineer', 'designed by', 'checked by', 'lead', 'project engineer'],
            'expertise': ['expertise', 'experience', 'specialist', 'expert', 'skilled'],
            'team': ['team', 'staff', 'personnel', 'resource', 'capability'],
            'knowledge': ['knowledge', 'know-how', 'understanding', 'familiar'],
            'skills': ['skills', 'competent', 'qualified', 'proficient', 'capable'],
            'project_involvement': ['involved', 'worked on', 'responsible', 'assigned']
        }
        
        for category, terms in high_value_terms.items():
            if all(term in content for term in terms[:2]):  # At least 2 terms must match
                score += 0.4
            elif any(term in content for term in terms):
                score += 0.2
        
        # Document type indicators for internal knowledge
        doc_type_indicators = {
            'cv': 0.4,              # CVs contain expertise info
            'resume': 0.4,          # Resumes contain expertise
            'profile': 0.35,        # Staff profiles
            'org_chart': 0.3,       # Organizational charts
            'project_list': 0.3,    # Project lists show involvement
            'capability': 0.35,     # Capability statements
            'experience': 0.3,      # Experience documents
            'team': 0.25,           # Team documents
            'resource': 0.25,       # Resource allocation docs
            'assignment': 0.2,      # Project assignments
            'bio': 0.35,            # Staff bios
            'expertise': 0.4        # Expertise documents
        }
        
        for indicator, weight in doc_type_indicators.items():
            if indicator in content:
                score += weight
        
        # Check component matches
        for category in ['expertise_areas', 'engineer_roles', 'technical_skills']:
            components_list = components.get(category, [])
            for component in components_list:
                if component.replace('_', ' ') in content:
                    score += 0.25
        
        # Project types and knowledge matches
        for category in ['project_types', 'experience_levels', 'knowledge_types']:
            components_list = components.get(category, [])
            for component in components_list:
                if component.replace('_', ' ') in content:
                    score += 0.15
        
        return min(score, 1.0)  # Cap at 1.0

    async def _generate_cost_time_answer(self, question: str, documents: List[Dict], components: Dict[str, Any]) -> str:
        """Generate a comprehensive answer for cost/time insights queries."""
        if not documents:
            return "No cost or timeline information found for your query."
        
        # Group documents by project for better organization
        projects_found = {}
        for doc in documents:
            project_id = self._extract_project_from_document(doc)
            if project_id not in projects_found:
                projects_found[project_id] = {
                    'documents': [],
                    'max_score': 0
                }
            
            projects_found[project_id]['documents'].append(doc)
            projects_found[project_id]['max_score'] = max(
                projects_found[project_id]['max_score'],
                doc.get('cost_time_score', 0)
            )
        
        # Create context from top documents
        context_parts = []
        for i, doc in enumerate(documents[:5]):
            project = doc.get('project_name', 'Unknown Project')
            filename = self._generate_meaningful_filename(doc) if not doc.get('filename') or doc.get('filename') == 'None' else doc.get('filename', 'Unknown Document')
            content_excerpt = doc.get('content', '')[:400]
            
            context_parts.append(f"Document {i+1}: {filename} (Project: {project})\n{content_excerpt}...")
        
        context = "\n\n".join(context_parts)
        
        # Generate AI response focused on cost/time insights
        cost_time_prompt = f"""Based on the following project documents from DTCE, provide a comprehensive answer for this cost/time insights query:

Question: {question}

Cost/Time Components Identified: {components['summary']}

Relevant Project Documents:
{context}

Please provide:
1. **Timeline Insights**: Typical durations, milestones, and project phases from the examples
2. **Cost Analysis**: Fee ranges, budget information, and cost factors from similar projects
3. **Scope Evolution**: Examples of how project scope changed during development
4. **Project Comparisons**: How similar projects compared in terms of cost and timeline
5. **Lessons Learned**: Key insights for planning similar future projects

Focus on extracting specific numerical data, timeframes, and cost ranges where available. Include project references for context."""

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a senior project manager and structural engineer analyzing DTCE project data to provide cost and timeline insights for future project planning."},
                    {"role": "user", "content": cost_time_prompt}
                ],
                temperature=0.3,
                max_tokens=1200
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error("Cost/time answer generation failed", error=str(e))
            return f"Found {len(documents)} relevant project examples across {len(projects_found)} projects. Please review the source documents for detailed cost and timeline information."

    async def _generate_best_practices_answer(self, question: str, documents: List[Dict], components: Dict[str, Any]) -> str:
        """Generate a comprehensive answer for best practices queries."""
        if not documents:
            return "No best practices or templates found for your query."
        
        # Prepare document context
        context = ""
        for i, doc in enumerate(documents[:10]):  # Limit to top 10 for context
            project_info = self._extract_project_from_document(doc)
            content_preview = (doc.get('content') or '')[:800]
            
            context += f"""
Document {i+1}: {doc.get('filename', 'Unknown')}
Project: {project_info}
Content: {content_preview}...

"""
        
        # Generate AI response focused on best practices
        best_practices_prompt = f"""Based on the following DTCE project documents, provide comprehensive best practices guidance for this query:

Question: {question}

Best Practices Components Identified: {components['summary']}

Relevant Project Documents:
{context}

Please provide:
1. **Standard Approaches**: Common methodologies and approaches used by DTCE for similar work
2. **Templates & Tools**: Available templates, calculation sheets, or standard documents
3. **Design Methodologies**: Proven design processes and analytical approaches
4. **Quality Processes**: Standard checking procedures, review processes, and QA methods
5. **Documentation Standards**: Typical report formats, drawing standards, and deliverable requirements
6. **Lessons & Recommendations**: Key insights and recommendations for best practice implementation

Focus on extracting specific methodologies, standard approaches, and practical guidance that can be applied to similar projects."""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a senior structural engineering consultant providing best practices guidance based on DTCE's project experience."},
                    {"role": "user", "content": best_practices_prompt}
                ],
                max_tokens=1000,
                temperature=0.3
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error("Best practices answer generation failed", error=str(e))
            return "I encountered an error while analyzing the best practices information. Please try refining your query."

    async def _generate_materials_methods_answer(self, question: str, documents: List[Dict], components: Dict[str, Any]) -> str:
        """Generate a comprehensive answer for materials/methods queries."""
        if not documents:
            return "No materials or methods comparison information found for your query."
        
        # Prepare document context
        context = ""
        for i, doc in enumerate(documents[:10]):  # Limit to top 10 for context
            project_info = self._extract_project_from_document(doc)
            content_preview = (doc.get('content') or '')[:800]
            
            context += f"""
Document {i+1}: {doc.get('filename', 'Unknown')}
Project: {project_info}
Content: {content_preview}...

"""
        
        # Generate AI response focused on materials/methods
        materials_methods_prompt = f"""Based on the following DTCE project documents, provide comprehensive materials and methods analysis for this query:

Question: {question}

Materials/Methods Components Identified: {components['summary']}

Relevant Project Documents:
{context}

Please provide:
1. **Material Comparisons**: Specific examples of material choices and comparisons from similar projects
2. **Decision Rationale**: Reasons why certain materials or methods were chosen over alternatives
3. **Performance Considerations**: How materials performed in terms of structural, cost, and construction factors
4. **Construction Methods**: Different construction approaches used and their relative merits
5. **Project Context**: How site conditions, project requirements, or other factors influenced material/method selection
6. **Recommendations**: Guidance on when to choose specific materials or methods based on project characteristics

Focus on extracting specific examples, decision criteria, and practical guidance for material and method selection."""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a senior structural engineering consultant providing materials and methods guidance based on DTCE's project experience."},
                    {"role": "user", "content": materials_methods_prompt}
                ],
                max_tokens=1000,
                temperature=0.3
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error("Materials/methods answer generation failed", error=str(e))
            return "I encountered an error while analyzing the materials and methods information. Please try refining your query."

    async def _generate_internal_knowledge_answer(self, question: str, documents: List[Dict], components: Dict[str, Any]) -> str:
        """Generate a comprehensive answer for internal knowledge queries."""
        if not documents:
            return "No internal knowledge or expertise information found for your query."
        
        # Prepare document context
        context = ""
        for i, doc in enumerate(documents[:10]):  # Limit to top 10 for context
            project_info = self._extract_project_from_document(doc)
            content_preview = (doc.get('content') or '')[:800]
            
            context += f"""
Document {i+1}: {doc.get('filename', 'Unknown')}
Project: {project_info}
Content: {content_preview}...

"""
        
        # Generate AI response focused on internal knowledge
        internal_knowledge_prompt = f"""Based on the following DTCE project documents, provide comprehensive internal knowledge and expertise information for this query:

Question: {question}

Internal Knowledge Components Identified: {components['summary']}

Relevant Project Documents:
{context}

Please provide:
1. **Team Expertise**: Engineers and their areas of specialization and experience
2. **Project Experience**: Specific projects and the expertise involved in their delivery
3. **Technical Capabilities**: Software skills, analysis capabilities, and specialized knowledge areas
4. **Knowledge Areas**: Specific technical domains where DTCE has demonstrated expertise
5. **Resource Allocation**: Insights into how expertise is distributed across the team
6. **Capability Recommendations**: Suggestions for leveraging internal expertise for similar future projects

Focus on identifying specific engineers, their expertise areas, and practical guidance for knowledge utilization within DTCE."""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an internal knowledge management system providing expertise mapping and capability insights for DTCE."},
                    {"role": "user", "content": internal_knowledge_prompt}
                ],
                max_tokens=1000,
                temperature=0.3
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error("Internal knowledge answer generation failed", error=str(e))
            return "I encountered an error while analyzing the internal knowledge information. Please try refining your query."

    def _format_cost_time_sources(self, documents: List[Dict], components: Dict[str, Any]) -> List[Dict]:
        """Format cost/time document sources with enhanced context."""
        sources = []
        
        for doc in documents[:5]:
            cost_time_score = doc.get('cost_time_score', 0)
            
            # Use comprehensive document info extraction
            doc_info = self._extract_document_info(doc)
            filename = doc_info['filename']
            project_id = doc_info['project_id'] or 'Unknown Project'
            
            # Create enhanced excerpt with cost/time context
            content = doc.get('content', '')
            cost_time_indicators = ['cost', 'fee', 'budget', 'timeline', 'duration', 'milestone', 'scope']
            
            excerpt = ""
            if content:
                # Look for sentences containing cost/time indicators
                sentences = content.split('.')
                for sentence in sentences:
                    if any(indicator in sentence.lower() for indicator in cost_time_indicators):
                        excerpt = sentence.strip()[:200] + "..."
                        break
                
                if not excerpt:
                    excerpt = content[:250] + "..." if len(content) > 250 else content
            
            sources.append({
                'filename': filename,
                'project_id': project_id,
                'relevance_score': doc.get('@search.score', cost_time_score),
                'cost_time_score': round(cost_time_score, 2),
                'blob_url': doc.get('blob_url', ''),
                'excerpt': excerpt,
                'cost_time_focus': components['summary'],
                'folder_path': doc_info['folder_path']
            })
        
        return sources

    async def _handle_best_practices_templates_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle queries about standard approaches, best practices, calculation templates, and design methodologies."""
        try:
            logger.info("Processing best practices/templates query", question=question)
            
            # Extract best practices components from the question
            bp_components = self._extract_best_practices_components(question)
            
            # Build search terms focused on templates, standards, and methodologies
            search_terms = self._build_best_practices_search_terms(question, bp_components)
            
            # Search for best practices and template documents
            relevant_docs = await self._search_best_practices_documents(search_terms, bp_components)
            
            if not relevant_docs:
                return {
                    'answer': f"I couldn't find specific best practices or templates for: {bp_components.get('summary', question)}. Try searching for design guides, calculation sheets, or methodology documents.",
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': 0,
                    'search_type': 'best_practices_templates',
                    'bp_components': bp_components
                }
            
            # Generate AI answer focused on best practices and templates
            answer = await self._generate_best_practices_answer(question, relevant_docs, bp_components)
            sources = self._format_best_practices_sources(relevant_docs, bp_components)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'high' if len(relevant_docs) >= 3 else 'medium',
                'documents_searched': len(relevant_docs),
                'search_type': 'best_practices_templates',
                'bp_components': bp_components
            }
            
        except Exception as e:
            logger.error("Best practices/templates query failed", error=str(e))
            return {
                'answer': 'I encountered an error while searching for best practices and templates. Please try searching for specific design methods or calculation approaches.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    async def _handle_materials_methods_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle queries about materials comparisons, construction methods, and technical specifications."""
        try:
            logger.info("Processing materials/methods query", question=question)
            
            # Extract materials/methods components from the question
            mm_components = self._extract_materials_methods_components(question)
            
            # Build search terms focused on materials and methods
            search_terms = self._build_materials_methods_search_terms(question, mm_components)
            
            # Search for materials and methods documents
            relevant_docs = await self._search_materials_methods_documents(search_terms, mm_components)
            
            if not relevant_docs:
                return {
                    'answer': f"I couldn't find specific materials or methods information for: {mm_components.get('summary', question)}. Try searching for specification documents, material reports, or construction method comparisons.",
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': 0,
                    'search_type': 'materials_methods',
                    'mm_components': mm_components
                }
            
            # Generate AI answer focused on materials and methods
            answer = await self._generate_materials_methods_answer(question, relevant_docs, mm_components)
            sources = self._format_materials_methods_sources(relevant_docs, mm_components)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'high' if len(relevant_docs) >= 3 else 'medium',
                'documents_searched': len(relevant_docs),
                'search_type': 'materials_methods',
                'mm_components': mm_components
            }
            
        except Exception as e:
            logger.error("Materials/methods query failed", error=str(e))
            return {
                'answer': 'I encountered an error while searching for materials and methods information. Please try searching for specific material types or construction techniques.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    async def _handle_internal_knowledge_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle queries about internal team expertise, engineer experience, and knowledge mapping."""
        try:
            logger.info("Processing internal knowledge query", question=question)
            
            # Extract internal knowledge components from the question
            ik_components = self._extract_internal_knowledge_components(question)
            
            # Build search terms focused on engineer expertise and internal knowledge
            search_terms = self._build_internal_knowledge_search_terms(question, ik_components)
            
            # Search for internal knowledge documents
            relevant_docs = await self._search_internal_knowledge_documents(search_terms, ik_components)
            
            if not relevant_docs:
                return {
                    'answer': f"I couldn't find specific internal knowledge or expertise information for: {ik_components.get('summary', question)}. Try searching for specific engineer names, project notes, or technical specializations.",
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': 0,
                    'search_type': 'internal_knowledge',
                    'ik_components': ik_components
                }
            
            # Generate AI answer focused on internal knowledge and expertise
            answer = await self._generate_internal_knowledge_answer(question, relevant_docs, ik_components)
            sources = self._format_internal_knowledge_sources(relevant_docs, ik_components)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'high' if len(relevant_docs) >= 3 else 'medium',
                'documents_searched': len(relevant_docs),
                'search_type': 'internal_knowledge',
                'ik_components': ik_components
            }
            
        except Exception as e:
            logger.error("Internal knowledge query failed", error=str(e))
            return {
                'answer': 'I encountered an error while searching for internal knowledge and expertise information. Please try searching for specific engineers or technical areas.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    def _extract_best_practices_components(self, question: str) -> Dict[str, Any]:
        """Extract best practices and templates components from the query."""
        question_lower = question.lower()
        
        components = {
            'practice_types': [],
            'template_types': [],
            'methodology_types': [],
            'scope_areas': [],
            'deliverable_types': [],
            'summary': ''
        }
        
        # Practice types
        practice_types = {
            'standard_approach': ['standard approach', 'typical approach', 'usual method', 'standard method', 'common practice'],
            'design_process': ['design process', 'design workflow', 'design methodology', 'design approach'],
            'calculation_method': ['calculation method', 'calculation approach', 'analysis method', 'design calculation'],
            'documentation': ['documentation', 'report format', 'report structure', 'document template'],
            'quality_assurance': ['quality assurance', 'qa process', 'checking procedure', 'review process'],
            'coordination': ['coordination', 'interface', 'collaboration', 'team approach']
        }
        
        # Template types
        template_types = {
            'calculation_template': ['calculation template', 'calc template', 'spreadsheet template', 'calculation sheet'],
            'report_template': ['report template', 'document template', 'report format', 'standard report'],
            'drawing_template': ['drawing template', 'drawing format', 'standard drawing', 'cad template'],
            'specification': ['specification', 'spec template', 'technical specification', 'design spec'],
            'checklist': ['checklist', 'check list', 'verification list', 'review checklist'],
            'procedure': ['procedure', 'process document', 'methodology', 'step-by-step']
        }
        
        # Methodology types
        methodology_types = {
            'structural_analysis': ['structural analysis', 'structural design', 'analysis method', 'design method'],
            'load_assessment': ['load assessment', 'loading', 'load analysis', 'load calculation'],
            'seismic_design': ['seismic design', 'earthquake design', 'seismic analysis', 'earthquake analysis'],
            'foundation_design': ['foundation design', 'foundation analysis', 'geotechnical design'],
            'steel_design': ['steel design', 'steel structure', 'steel analysis', 'steel member'],
            'concrete_design': ['concrete design', 'concrete structure', 'concrete analysis', 'reinforced concrete']
        }
        
        # Scope areas
        scope_areas = {
            'residential': ['residential', 'house', 'dwelling', 'apartment', 'townhouse'],
            'commercial': ['commercial', 'office', 'retail', 'mixed use', 'commercial building'],
            'industrial': ['industrial', 'warehouse', 'factory', 'manufacturing', 'industrial building'],
            'infrastructure': ['infrastructure', 'bridge', 'civil', 'public works', 'utilities'],
            'alteration': ['alteration', 'renovation', 'refurbishment', 'modification', 'upgrade'],
            'new_build': ['new build', 'new construction', 'greenfield', 'new development']
        }
        
        # Deliverable types
        deliverable_types = {
            'producer_statement': ['producer statement', 'ps1', 'ps2', 'ps3', 'ps4'],
            'structural_drawings': ['structural drawings', 'structural plans', 'engineering drawings'],
            'calculations': ['calculations', 'structural calculations', 'design calculations', 'engineering calculations'],
            'specifications': ['specifications', 'technical specifications', 'material specifications'],
            'reports': ['structural report', 'engineering report', 'assessment report', 'design report'],
            'certificates': ['certificates', 'compliance certificate', 'design certificate']
        }
        
        # Extract components from question
        for category, terms_dict in [
            ('practice_types', practice_types),
            ('template_types', template_types), 
            ('methodology_types', methodology_types),
            ('scope_areas', scope_areas),
            ('deliverable_types', deliverable_types)
        ]:
            for term_type, terms in terms_dict.items():
                if any(term in question_lower for term in terms):
                    components[category].append(term_type)
        
        # Create summary
        summary_parts = []
        if components['practice_types']:
            summary_parts.append(f"practice types: {', '.join(components['practice_types'])}")
        if components['template_types']:
            summary_parts.append(f"templates: {', '.join(components['template_types'])}")
        if components['methodology_types']:
            summary_parts.append(f"methodologies: {', '.join(components['methodology_types'])}")
        if components['scope_areas']:
            summary_parts.append(f"scope: {', '.join(components['scope_areas'])}")
        if components['deliverable_types']:
            summary_parts.append(f"deliverables: {', '.join(components['deliverable_types'])}")
            
        components['summary'] = '; '.join(summary_parts) if summary_parts else 'general best practices query'
        
        return components

    def _extract_materials_methods_components(self, question: str) -> Dict[str, Any]:
        """Extract materials and methods comparison components from the query."""
        question_lower = question.lower()
        
        components = {
            'material_types': [],
            'structural_systems': [],
            'comparison_aspects': [],
            'building_elements': [],
            'project_contexts': [],
            'decision_factors': [],
            'summary': ''
        }
        
        # Material types
        material_types = {
            'concrete': ['concrete', 'reinforced concrete', 'precast concrete', 'in-situ concrete', 'prestressed concrete'],
            'steel': ['steel', 'structural steel', 'steel frame', 'steel structure', 'cold-formed steel'],
            'timber': ['timber', 'wood', 'laminated timber', 'glulam', 'engineered timber', 'clt'],
            'masonry': ['masonry', 'brick', 'block', 'concrete block', 'clay brick', 'stone'],
            'composite': ['composite', 'steel-concrete composite', 'hybrid', 'mixed construction'],
            'other': ['aluminum', 'aluminium', 'fibre reinforced', 'frp', 'carbon fibre']
        }
        
        # Structural systems
        structural_systems = {
            'frame': ['frame', 'moment frame', 'braced frame', 'steel frame', 'concrete frame'],
            'wall': ['wall', 'shear wall', 'load bearing wall', 'concrete wall', 'masonry wall'],
            'slab': ['slab', 'floor slab', 'concrete slab', 'composite slab', 'precast slab'],
            'foundation': ['foundation', 'pile', 'pad foundation', 'strip foundation', 'raft foundation'],
            'roof': ['roof', 'roof structure', 'roof framing', 'roof truss', 'portal frame'],
            'tilt_slab': ['tilt slab', 'tilt-up', 'tilt panel', 'precast panel']
        }
        
        # Comparison aspects
        comparison_aspects = {
            'cost': ['cost', 'price', 'budget', 'economic', 'financial', 'expensive', 'cheap'],
            'performance': ['performance', 'structural performance', 'seismic performance', 'strength'],
            'construction': ['construction', 'buildability', 'constructability', 'installation', 'erection'],
            'time': ['time', 'duration', 'schedule', 'fast', 'quick', 'slow', 'construction time'],
            'durability': ['durability', 'longevity', 'maintenance', 'life cycle', 'weathering'],
            'sustainability': ['sustainability', 'environmental', 'carbon', 'embodied energy', 'green']
        }
        
        # Building elements
        building_elements = {
            'floors': ['floor', 'floor slab', 'suspended floor', 'ground floor', 'upper floor'],
            'walls': ['wall', 'external wall', 'internal wall', 'partition wall', 'structural wall'],
            'columns': ['column', 'pillar', 'post', 'vertical support', 'structural column'],
            'beams': ['beam', 'girder', 'lintel', 'header', 'structural beam'],
            'foundations': ['foundation', 'footing', 'pile', 'base', 'substructure'],
            'connections': ['connection', 'joint', 'fastener', 'weld', 'bolt']
        }
        
        # Project contexts
        project_contexts = {
            'seismic': ['seismic', 'earthquake', 'seismic zone', 'high seismic', 'seismic design'],
            'high_rise': ['high rise', 'multi-storey', 'tall building', 'tower', 'high building'],
            'industrial': ['industrial', 'warehouse', 'factory', 'heavy loading', 'crane'],
            'residential': ['residential', 'house', 'apartment', 'dwelling', 'housing'],
            'commercial': ['commercial', 'office', 'retail', 'mixed use'],
            'coastal': ['coastal', 'marine', 'salt', 'corrosive', 'exposure']
        }
        
        # Decision factors
        decision_factors = {
            'client_preference': ['client preference', 'client requirement', 'owner preference'],
            'site_constraints': ['site constraints', 'access', 'site conditions', 'ground conditions'],
            'code_requirements': ['code requirements', 'building code', 'standards', 'compliance'],
            'engineer_experience': ['experience', 'expertise', 'familiarity', 'knowledge'],
            'contractor_capability': ['contractor', 'builder', 'construction capability', 'trade'],
            'availability': ['availability', 'supply', 'material availability', 'lead time']
        }
        
        # Extract components from question
        for category, terms_dict in [
            ('material_types', material_types),
            ('structural_systems', structural_systems),
            ('comparison_aspects', comparison_aspects),
            ('building_elements', building_elements),
            ('project_contexts', project_contexts),
            ('decision_factors', decision_factors)
        ]:
            for term_type, terms in terms_dict.items():
                if any(term in question_lower for term in terms):
                    components[category].append(term_type)
        
        # Create summary
        summary_parts = []
        if components['material_types']:
            summary_parts.append(f"materials: {', '.join(components['material_types'])}")
        if components['structural_systems']:
            summary_parts.append(f"systems: {', '.join(components['structural_systems'])}")
        if components['comparison_aspects']:
            summary_parts.append(f"comparing: {', '.join(components['comparison_aspects'])}")
        if components['building_elements']:
            summary_parts.append(f"elements: {', '.join(components['building_elements'])}")
        if components['project_contexts']:
            summary_parts.append(f"context: {', '.join(components['project_contexts'])}")
        if components['decision_factors']:
            summary_parts.append(f"factors: {', '.join(components['decision_factors'])}")
            
        components['summary'] = '; '.join(summary_parts) if summary_parts else 'general materials/methods comparison'
        
        return components

    def _extract_internal_knowledge_components(self, question: str) -> Dict[str, Any]:
        """Extract internal knowledge and expertise components from the query."""
        question_lower = question.lower()
        
        components = {
            'expertise_areas': [],
            'engineer_roles': [],
            'project_types': [],
            'technical_skills': [],
            'experience_levels': [],
            'knowledge_types': [],
            'summary': ''
        }
        
        # Expertise areas
        expertise_areas = {
            'structural_design': ['structural design', 'structural engineering', 'structural analysis'],
            'seismic_engineering': ['seismic', 'earthquake', 'seismic design', 'seismic analysis'],
            'geotechnical': ['geotechnical', 'foundation', 'soil', 'ground', 'pile design'],
            'steel_structures': ['steel', 'steel structures', 'steel design', 'steel frame'],
            'concrete_structures': ['concrete', 'reinforced concrete', 'concrete design', 'precast'],
            'timber_structures': ['timber', 'wood', 'timber design', 'engineered timber'],
            'masonry': ['masonry', 'brick', 'block', 'unreinforced masonry'],
            'assessment': ['assessment', 'existing building', 'strengthening', 'evaluation'],
            'tilt_slab': ['tilt slab', 'tilt-up', 'precast', 'tilt panel'],
            'industrial': ['industrial', 'warehouse', 'crane', 'heavy loading'],
            'high_rise': ['high rise', 'multi-storey', 'tall building', 'tower'],
            'bridge': ['bridge', 'civil', 'infrastructure', 'transportation']
        }
        
        # Engineer roles
        engineer_roles = {
            'senior_engineer': ['senior engineer', 'principal engineer', 'lead engineer', 'senior'],
            'project_engineer': ['project engineer', 'project lead', 'project manager'],
            'design_engineer': ['design engineer', 'designer', 'design team'],
            'graduate_engineer': ['graduate engineer', 'junior engineer', 'graduate'],
            'specialist': ['specialist', 'expert', 'consultant', 'technical specialist'],
            'checker': ['checker', 'reviewer', 'peer reviewer', 'design checker']
        }
        
        # Project types for experience
        project_types = {
            'residential': ['residential', 'house', 'apartment', 'dwelling', 'housing'],
            'commercial': ['commercial', 'office', 'retail', 'mixed use'],
            'industrial': ['industrial', 'warehouse', 'factory', 'manufacturing'],
            'infrastructure': ['infrastructure', 'bridge', 'civil', 'public works'],
            'education': ['education', 'school', 'university', 'institutional'],
            'healthcare': ['healthcare', 'hospital', 'medical', 'clinic'],
            'alteration': ['alteration', 'renovation', 'strengthening', 'seismic upgrade']
        }
        
        # Technical skills
        technical_skills = {
            'software': ['software', 'etabs', 'sap', 'spacegass', 'tekla', 'revit', 'autocad'],
            'analysis': ['analysis', 'finite element', 'dynamic analysis', 'non-linear'],
            'design_codes': ['design codes', 'nzs', 'standards', 'eurocode', 'building code'],
            'calculation': ['calculation', 'hand calculation', 'spreadsheet', 'verification'],
            'modeling': ['modeling', 'modelling', '3d model', 'structural model'],
            'detailing': ['detailing', 'connection design', 'reinforcement detailing']
        }
        
        # Experience levels
        experience_levels = {
            'experienced': ['experienced', 'senior', 'expert', 'specialist', 'veteran'],
            'intermediate': ['intermediate', 'mid-level', 'competent', 'capable'],
            'junior': ['junior', 'graduate', 'new', 'recent', 'entry level'],
            'highly_experienced': ['highly experienced', 'very experienced', 'extensive experience']
        }
        
        # Knowledge types
        knowledge_types = {
            'technical_knowledge': ['technical knowledge', 'engineering knowledge', 'design knowledge'],
            'project_experience': ['project experience', 'practical experience', 'hands-on'],
            'specialist_expertise': ['specialist expertise', 'specialized knowledge', 'niche'],
            'software_skills': ['software skills', 'technical skills', 'computer skills'],
            'industry_knowledge': ['industry knowledge', 'market knowledge', 'sector'],
            'mentoring': ['mentoring', 'training', 'guidance', 'teaching']
        }
        
        # Extract components from question
        for category, terms_dict in [
            ('expertise_areas', expertise_areas),
            ('engineer_roles', engineer_roles),
            ('project_types', project_types),
            ('technical_skills', technical_skills),
            ('experience_levels', experience_levels),
            ('knowledge_types', knowledge_types)
        ]:
            for term_type, terms in terms_dict.items():
                if any(term in question_lower for term in terms):
                    components[category].append(term_type)
        
        # Create summary
        summary_parts = []
        if components['expertise_areas']:
            summary_parts.append(f"expertise: {', '.join(components['expertise_areas'])}")
        if components['engineer_roles']:
            summary_parts.append(f"roles: {', '.join(components['engineer_roles'])}")
        if components['project_types']:
            summary_parts.append(f"projects: {', '.join(components['project_types'])}")
        if components['technical_skills']:
            summary_parts.append(f"skills: {', '.join(components['technical_skills'])}")
        if components['experience_levels']:
            summary_parts.append(f"level: {', '.join(components['experience_levels'])}")
        if components['knowledge_types']:
            summary_parts.append(f"knowledge: {', '.join(components['knowledge_types'])}")
            
        components['summary'] = '; '.join(summary_parts) if summary_parts else 'general internal knowledge query'
        
        return components

    def _extract_regulatory_components(self, question: str) -> Dict[str, Any]:
        """Extract regulatory, council, and consent components from the query."""
        question_lower = question.lower()
        
        components = {
            'regulatory_bodies': [],
            'challenge_types': [],
            'solution_types': [],
            'building_elements': [],
            'regulatory_processes': [],
            'summary': ''
        }
        
        # Regulatory bodies and authorities
        regulatory_bodies = {
            'council': ['council', 'city council', 'district council', 'regional council', 'local authority'],
            'mbie': ['mbie', 'building and housing', 'ministry of business'],
            'building_consent_authority': ['bca', 'building consent authority', 'consent authority'],
            'engineer': ['engineer', 'structural engineer', 'reviewing engineer'],
            'code_compliance': ['code compliance', 'ccc', 'certificate of code compliance']
        }
        
        # Types of regulatory challenges
        challenge_types = {
            'questioned_calculations': ['questioned', 'queried', 'challenged', 'disputed', 'raised concerns', 'requested clarification'],
            'alternative_solution': ['alternative solution', 'alternative design', 'alternative method', 'departures'],
            'non_compliance': ['non-compliant', 'non-standard', 'non-conforming', 'deviation'],
            'additional_requirements': ['additional requirements', 'further information', 'more detail', 'peer review'],
            'appeals': ['appeal', 'objection', 'dispute', 'disagreement']
        }
        
        # Solution types
        solution_types = {
            'precedent': ['precedent', 'previous approval', 'similar case', 'past example'],
            'engineering_justification': ['engineering justification', 'technical report', 'peer review'],
            'alternative_compliance': ['alternative compliance', 'alternative solution', 'performance-based'],
            'specialist_input': ['specialist', 'expert', 'consultant', 'third party review']
        }
        
        # Building elements commonly requiring special attention
        building_elements = {
            'wind_loads': ['wind load', 'wind pressure', 'wind analysis', 'wind calculations'],
            'seismic': ['seismic', 'earthquake', 'seismic analysis', 'seismic design'],
            'stairs': ['stair', 'staircase', 'stairway', 'step'],
            'bracing': ['bracing', 'lateral stability', 'shear walls', 'diaphragm'],
            'heritage': ['heritage', 'historic', 'conservation', 'character'],
            'fire_safety': ['fire', 'fire safety', 'fire rating', 'egress'],
            'accessibility': ['accessibility', 'disabled access', 'barrier-free']
        }
        
        # Regulatory processes
        regulatory_processes = {
            'consent_application': ['consent application', 'building consent', 'resource consent'],
            'design_review': ['design review', 'plan review', 'structural review'],
            'inspection': ['inspection', 'site visit', 'verification'],
            'certification': ['certification', 'sign-off', 'ps1', 'ps3', 'ps4']
        }
        
        # Extract components
        for category, terms_dict in [
            ('regulatory_bodies', regulatory_bodies),
            ('challenge_types', challenge_types),
            ('solution_types', solution_types),
            ('building_elements', building_elements),
            ('regulatory_processes', regulatory_processes)
        ]:
            for key, terms in terms_dict.items():
                if any(term in question_lower for term in terms):
                    components[category].append(key)
        
        # Create summary
        summary_parts = []
        if components['regulatory_bodies']:
            summary_parts.append(f"Authority: {', '.join(components['regulatory_bodies'])}")
        if components['challenge_types']:
            summary_parts.append(f"Challenge: {', '.join(components['challenge_types'])}")
        if components['building_elements']:
            summary_parts.append(f"Element: {', '.join(components['building_elements'])}")
        if components['solution_types']:
            summary_parts.append(f"Solution: {', '.join(components['solution_types'])}")
        if components['regulatory_processes']:
            summary_parts.append(f"Process: {', '.join(components['regulatory_processes'])}")
            
        components['summary'] = " | ".join(summary_parts) if summary_parts else question
        
        return components

    def _build_regulatory_search_terms(self, question: str, components: Dict[str, Any]) -> str:
        """Build search terms optimized for finding regulatory/consent documents."""
        search_terms = []
        
        # Add original question
        search_terms.append(question)
        
        # Add regulatory-specific terms
        regulatory_keywords = [
            # Council communication
            'council', 'building consent', 'consent application', 'council response',
            'council query', 'council comments', 'peer review', 'reviewing engineer',
            
            # Alternative solutions
            'alternative solution', 'alternative design', 'alternative method',
            'departures', 'non-standard', 'special design',
            
            # Documentation types
            'engineering report', 'technical justification', 'design rationale',
            'correspondence', 'email', 'letter', 'memo', 'response',
            
            # Regulatory processes  
            'building consent', 'resource consent', 'code compliance',
            'ps1', 'ps3', 'ps4', 'certificate', 'approval'
        ]
        
        # Add component-specific terms
        for category in ['regulatory_bodies', 'challenge_types', 'solution_types', 'building_elements', 'regulatory_processes']:
            search_terms.extend(components.get(category, []))
        
        # Add regulatory keywords
        search_terms.extend(regulatory_keywords)
        
        return " OR ".join(f'"{term}"' for term in search_terms[:20])  # Limit to prevent too long query

    async def _search_regulatory_documents(self, search_terms: str, components: Dict[str, Any]) -> List[Dict]:
        """Search for documents containing regulatory/consent information."""
        try:
            # Search with regulatory focus
            results = self.search_client.search(
                search_text=search_terms,
                top=30,
                highlight_fields="filename,project_name,content",
                select=["id", "filename", "content", "blob_url", "project_name", "folder"],
                search_mode="any"
            )
            
            relevant_docs = []
            seen_docs = set()
            
            for result in results:
                # Score documents based on regulatory relevance
                score = self._calculate_regulatory_relevance(result, components)
                
                if score > 0.2:  # Lower threshold for regulatory docs as they might be more subtle
                    # Avoid duplicate documents
                    doc_id = result.get('id', result.get('filename', ''))
                    if doc_id not in seen_docs:
                        result['regulatory_score'] = score
                        relevant_docs.append(result)
                        seen_docs.add(doc_id)
            
            # Sort by regulatory relevance score
            relevant_docs.sort(key=lambda x: x.get('regulatory_score', 0), reverse=True)
            
            logger.info("Regulatory document search completed", 
                       total_found=len(relevant_docs),
                       components=components['summary'])
            
            return relevant_docs[:15]  # Top 15 most relevant
            
        except Exception as e:
            logger.error("Regulatory document search failed", error=str(e))
            return []

    def _calculate_regulatory_relevance(self, document: Dict, components: Dict[str, Any]) -> float:
        """Calculate how well a document matches regulatory precedent criteria."""
        content = (
            (document.get('content') or '') + ' ' + 
            (document.get('filename') or '') + ' ' + 
            (document.get('project_name') or '') + ' ' +
            (document.get('folder') or '')
        ).lower()
        
        score = 0.0
        
        # High-value regulatory indicators
        high_value_terms = {
            'council correspondence': ['council', 'email', 'correspondence', 'letter', 'response'],
            'consent process': ['consent', 'application', 'approval', 'building consent'],
            'engineering review': ['peer review', 'reviewing engineer', 'technical review'],
            'alternative solutions': ['alternative', 'solution', 'departures', 'special'],
            'regulatory challenge': ['questioned', 'queried', 'concerns', 'clarification', 'additional']
        }
        
        for category, terms in high_value_terms.items():
            if all(term in content for term in terms[:2]):  # At least 2 terms must match
                score += 0.4
            elif any(term in content for term in terms):
                score += 0.2
        
        # Document type indicators
        doc_type_indicators = {
            'correspondence': 0.3,  # emails, letters likely to contain regulatory discussions
            'report': 0.2,          # engineering reports may contain justifications
            'memo': 0.25,           # internal memos about regulatory issues
            'response': 0.3,        # responses to council queries
            'justification': 0.35,  # technical justifications
            'precedent': 0.4        # explicit precedent discussions
        }
        
        for indicator, weight in doc_type_indicators.items():
            if indicator in content:
                score += weight
        
        # Check component matches with higher weight for regulatory terms
        for category in ['regulatory_bodies', 'challenge_types', 'solution_types']:
            components_list = components.get(category, [])
            for component in components_list:
                if component.replace('_', ' ') in content:
                    score += 0.25
        
        # Building element matches
        for component in components.get('building_elements', []):
            if component.replace('_', ' ') in content:
                score += 0.15
        
        return min(score, 1.0)  # Cap at 1.0

    async def _generate_regulatory_answer(self, question: str, documents: List[Dict], components: Dict[str, Any]) -> str:
        """Generate a comprehensive answer for regulatory precedent queries."""
        if not documents:
            return "No regulatory precedents found for your query."
        
        # Group documents by project for better organization
        projects_found = {}
        for doc in documents:
            project_id = self._extract_project_from_document(doc)
            if project_id not in projects_found:
                projects_found[project_id] = {
                    'documents': [],
                    'max_score': 0
                }
            
            projects_found[project_id]['documents'].append(doc)
            projects_found[project_id]['max_score'] = max(
                projects_found[project_id]['max_score'],
                doc.get('regulatory_score', 0)
            )
        
        # Create context from top documents
        context_parts = []
        for i, doc in enumerate(documents[:5]):
            project = doc.get('project_name', 'Unknown Project')
            filename = doc.get('filename', 'Unknown Document')
            content_excerpt = doc.get('content', '')[:400]
            
            context_parts.append(f"Document {i+1}: {filename} (Project: {project})\n{content_excerpt}...")
        
        context = "\n\n".join(context_parts)
        
        # Generate AI response focused on regulatory precedents
        regulatory_prompt = f"""Based on the following regulatory and consent documents from DTCE projects, provide a comprehensive answer for this regulatory precedent query:

Question: {question}

Regulatory Components Identified: {components['summary']}

Relevant Regulatory Documents:
{context}

Please provide:
1. **Regulatory Precedents**: Specific examples of how similar regulatory challenges were handled
2. **Council Interactions**: How councils responded to these situations and what they required
3. **Alternative Solutions**: Any alternative compliance methods or special designs that were approved
4. **Documentation Approach**: How DTCE justified their approach to regulatory authorities
5. **Lessons Learned**: Key insights for handling similar regulatory challenges in future

Focus on practical regulatory guidance that can be applied to similar situations. Include specific project references where relevant."""

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a senior structural engineer analyzing DTCE regulatory precedents and consent processes to provide guidance on navigating building consent challenges."},
                    {"role": "user", "content": regulatory_prompt}
                ],
                temperature=0.3,
                max_tokens=1200
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error("Regulatory answer generation failed", error=str(e))
            return f"Found {len(documents)} relevant regulatory examples across {len(projects_found)} projects. Please review the source documents for detailed regulatory precedent information."

    def _format_regulatory_sources(self, documents: List[Dict], components: Dict[str, Any]) -> List[Dict]:
        """Format regulatory document sources with enhanced context."""
        sources = []
        
        for doc in documents[:5]:
            regulatory_score = doc.get('regulatory_score', 0)
            filename = doc.get('filename', 'Unknown Document')
            
            # Handle case where filename is literally 'None' or missing
            if not filename or filename == 'None':
                # Try to create a meaningful filename from content
                filename = self._generate_meaningful_filename(doc)
            
            sources.append({
                'filename': filename,
                'project_id': self._extract_project_from_document(doc),
                'relevance_score': doc.get('@search.score', regulatory_score),
                'regulatory_score': round(regulatory_score, 2),
                'blob_url': doc.get('blob_url', ''),
                'excerpt': (doc.get('content', '')[:250] + '...') if doc.get('content') else '',
                'regulatory_focus': components['summary']
            })
        
        return sources

    async def _handle_template_search_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Handle queries asking for templates, forms, spreadsheets, or design tools."""
        try:
            logger.info("Processing template search query", question=question)
            
            # Extract template type from question
            template_type = self._identify_template_type(question)
            
            # Search for template documents
            template_docs = await self._search_template_documents(question, template_type)
            
            if not template_docs:
                # If no templates found in SuiteFiles, provide external links
                return await self._provide_external_template_links(question, template_type)
            
            # Format the answer with direct SuiteFiles links
            answer = self._format_template_answer(template_docs, template_type, question)
            sources = self._format_template_sources(template_docs)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'high',
                'documents_searched': len(template_docs),
                'search_type': 'template_search'
            }
            
        except Exception as e:
            logger.error("Template search query failed", error=str(e))
            return {
                'answer': 'I encountered an error while searching for templates. Please check SuiteFiles directly or contact your team for template access.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0
            }

    def _identify_template_type(self, question: str) -> str:
        """Identify what type of template the user is looking for."""
        question_lower = question.lower()
        
        # PS Templates
        if any(term in question_lower for term in ['ps1', 'ps 1', 'producer statement 1']):
            return 'PS1'
        elif any(term in question_lower for term in ['ps1a', 'ps 1a', 'producer statement 1a']):
            return 'PS1A'
        elif any(term in question_lower for term in ['ps3', 'ps 3', 'producer statement 3']):
            return 'PS3'
        elif any(term in question_lower for term in ['ps4', 'ps 4', 'producer statement 4']):
            return 'PS4'
        elif 'producer statement' in question_lower:
            return 'PS_GENERAL'
            
        # Design Spreadsheets
        elif any(term in question_lower for term in ['timber beam', 'beam design', 'timber design']):
            return 'TIMBER_BEAM_DESIGN'
        elif any(term in question_lower for term in ['concrete beam', 'concrete design']):
            return 'CONCRETE_DESIGN'
        elif any(term in question_lower for term in ['steel beam', 'steel design']):
            return 'STEEL_DESIGN'
        elif any(term in question_lower for term in ['spreadsheet', 'calculator', 'design tool']):
            return 'DESIGN_SPREADSHEET'
            
        # General templates
        elif any(term in question_lower for term in ['template', 'form', 'document']):
            return 'GENERAL_TEMPLATE'
        else:
            return 'UNKNOWN'

    async def _search_template_documents(self, question: str, template_type: str) -> List[Dict]:
        """Search for template documents in SuiteFiles."""
        
        # Build search terms based on template type
        search_terms = {
            'PS1': ['PS1', 'producer statement 1', 'PS-1', 'producer statement', 'template'],
            'PS1A': ['PS1A', 'PS1-A', 'producer statement 1A', 'PS-1A', 'template'],
            'PS3': ['PS3', 'producer statement 3', 'PS-3', 'producer statement', 'template'],
            'PS4': ['PS4', 'producer statement 4', 'PS-4', 'producer statement', 'template'],
            'PS_GENERAL': ['producer statement', 'PS', 'template', 'form'],
            'TIMBER_BEAM_DESIGN': ['timber beam', 'timber design', 'beam calculator', 'timber spreadsheet'],
            'CONCRETE_DESIGN': ['concrete beam', 'concrete design', 'concrete calculator', 'concrete spreadsheet'],
            'STEEL_DESIGN': ['steel beam', 'steel design', 'steel calculator', 'steel spreadsheet'],
            'DESIGN_SPREADSHEET': ['design spreadsheet', 'calculator', 'design tool', 'template'],
            'GENERAL_TEMPLATE': ['template', 'form', 'document'],
            'UNKNOWN': [question]  # Use the original question
        }
        
        terms = search_terms.get(template_type, [question])
        search_query = ' '.join(terms)
        
        # Search with focus on templates and forms
        results = self.search_client.search(
            search_text=search_query,
            top=20,
            select=["id", "filename", "content", "blob_url", "project_name", "folder"],
            query_type="semantic",
            semantic_configuration_name="default"
        )
        
        template_docs = []
        for result in results:
            doc_dict = dict(result)
            filename = (doc_dict.get('filename') or '').lower()
            content = (doc_dict.get('content') or '').lower()
            
            # Filter for template-like documents
            template_indicators = [
                'template', 'form', 'ps1', 'ps3', 'ps4', 'producer statement',
                'spreadsheet', 'calculator', 'design tool', '.xlsx', '.xls',
                'beam design', 'concrete design', 'steel design'
            ]
            
            if any(indicator in filename or indicator in content for indicator in template_indicators):
                template_docs.append(doc_dict)
        
        return template_docs

    async def _provide_external_template_links(self, question: str, template_type: str) -> Dict[str, Any]:
        """Provide external links when templates are not found in SuiteFiles."""
        
        external_links = {
            'PS1': {
                'title': 'PS1 - Producer Statement Design',
                'links': [
                    'https://www.building.govt.nz/building-code-compliance/how-the-building-consent-process-works/documentation-for-a-building-consent/producer-statements/',
                    'https://www.ipenz.org.nz/practice/producer-statements/'
                ]
            },
            'PS3': {
                'title': 'PS3 - Producer Statement Construction',
                'links': [
                    'https://www.building.govt.nz/building-code-compliance/how-the-building-consent-process-works/documentation-for-a-building-consent/producer-statements/',
                    'https://www.ipenz.org.nz/practice/producer-statements/'
                ]
            },
            'PS4': {
                'title': 'PS4 - Producer Statement Construction Review',
                'links': [
                    'https://www.building.govt.nz/building-code-compliance/how-the-building-consent-process-works/documentation-for-a-building-consent/producer-statements/'
                ]
            }
        }
        
        link_info = external_links.get(template_type, {
            'title': 'Engineering Templates',
            'links': [
                'https://www.building.govt.nz/building-code-compliance/',
                'https://www.engineering.org.nz/resources/'
            ]
        })
        
        answer = f"I couldn't find a {template_type} template in our SuiteFiles documents.\n\n"
        answer += f"📋 **{link_info['title']} - External Resources:**\n"
        
        for link in link_info['links']:
            answer += f"• {link}\n"
        
        answer += "\n💡 **Recommendations:**\n"
        answer += "• Check with your team lead for DTCE-specific templates\n"
        answer += "• Contact Engineering New Zealand for official forms\n"
        answer += "• Ask your local council for their preferred template formats\n"
        
        return {
            'answer': answer,
            'sources': [],
            'confidence': 'medium',
            'documents_searched': 0,
            'search_type': 'external_template_links'
        }

    def _format_template_answer(self, template_docs: List[Dict], template_type: str, question: str) -> str:
        """Format template search results into a comprehensive answer."""
        if not template_docs:
            return f"No {template_type} templates found in SuiteFiles."
        
        answer_parts = []
        
        # Filter out documents with missing essential info and group by project
        valid_templates = []
        templates_by_project = {}
        
        for doc in template_docs:
            filename = (doc.get('filename') or '').strip()
            project = (doc.get('project_name') or '').strip() or 'General Templates'
            blob_url = (doc.get('blob_url') or '').strip()
            
            # Skip documents with missing filename
            if not filename or filename == 'None':
                continue
                
            valid_templates.append(doc)
            
            if project not in templates_by_project:
                templates_by_project[project] = []
            
            templates_by_project[project].append({
                'filename': filename,
                'url': blob_url
            })
        
        if not valid_templates:
            return f"Found potential {template_type} documents but they lack proper metadata. Please search SuiteFiles manually or contact your team."
        
        answer_parts.append(f"📋 **{template_type} Templates Found in SuiteFiles:**\n")
        
        for project, templates in templates_by_project.items():
            if len(templates_by_project) > 1 and project != 'General Templates':
                answer_parts.append(f"\n**Project {project}:**")
            
            for template in templates:
                if template['url']:
                    answer_parts.append(f"• [{template['filename']}]({template['url']})")
                else:
                    answer_parts.append(f"• {template['filename']} (Contact team for access)")
        
        # Add usage instructions
        answer_parts.append(f"\n💡 **How to Access:**")
        answer_parts.append(f"• Click the links above to access templates directly in SuiteFiles")
        answer_parts.append(f"• Download and customize for your specific project")
        answer_parts.append(f"• Ensure you're using the most current version")
        
        # Add specific guidance based on template type
        if 'PS' in template_type:
            answer_parts.append(f"\n⚠️ **Important for Producer Statements:**")
            answer_parts.append(f"• Ensure you're a Chartered Professional Engineer (CPEng)")
            answer_parts.append(f"• Review MBIE guidelines for producer statements")
            answer_parts.append(f"• Check council-specific requirements")
        
        return "\n".join(answer_parts)

    def _format_template_sources(self, template_docs: List[Dict]) -> List[Dict]:
        """Format template documents as sources."""
        sources = []
        
        for doc in template_docs[:5]:  # Limit to top 5 sources
            filename = (doc.get('filename') or '').strip()
            project_name = (doc.get('project_name') or '').strip()
            
            # Skip sources with missing essential info
            if not filename or filename == 'None':
                continue
                
            sources.append({
                'filename': filename,
                'project_id': project_name or 'Template Library',
                'relevance_score': doc.get('@search.score', 0.9),
                'blob_url': doc.get('blob_url', ''),
                'excerpt': f"Template document: {filename}"
            })
        
        return sources

    def _format_best_practices_sources(self, documents: List[Dict], components: Dict[str, Any]) -> List[Dict]:
        """Format best practices document sources with enhanced context."""
        sources = []
        
        for doc in documents:
            # Use comprehensive document info extraction
            doc_info = self._extract_document_info(doc)
            filename = doc_info['filename']
            project_name = doc_info['project_id'] or 'Practice Library'
            
            # Get the best practices relevance score
            relevance_score = doc.get('best_practices_score', doc.get('@search.score', 0.5))
            
            # Create context-aware excerpt
            content = doc.get('content', '')
            
            # Look for practice-specific excerpts
            practice_indicators = [
                'standard approach', 'methodology', 'template', 'procedure',
                'checklist', 'guideline', 'specification', 'process'
            ]
            
            excerpt = ""
            for indicator in practice_indicators:
                if indicator in content.lower():
                    # Find sentence containing the indicator
                    sentences = content.split('.')
                    for sentence in sentences:
                        if indicator in sentence.lower():
                            excerpt = sentence.strip()[:200] + "..."
                            break
                    if excerpt:
                        break
            
            if not excerpt:
                excerpt = content[:200] + "..." if content else "Best practices document"
            
            sources.append({
                'filename': filename,
                'project_id': project_name,
                'relevance_score': relevance_score,
                'blob_url': doc.get('blob_url', ''),
                'excerpt': excerpt,
                'folder_path': doc_info['folder_path']
            })
        
        return sources

    def _format_materials_methods_sources(self, documents: List[Dict], components: Dict[str, Any]) -> List[Dict]:
        """Format materials/methods document sources with enhanced context."""
        sources = []
        
        for doc in documents:
            # Use comprehensive document info extraction
            doc_info = self._extract_document_info(doc)
            filename = doc_info['filename']
            project_name = doc_info['project_id'] or 'Technical Library'
            
            # Get the materials/methods relevance score
            relevance_score = doc.get('materials_methods_score', doc.get('@search.score', 0.5))
            
            # Create context-aware excerpt
            content = doc.get('content', '')
            
            # Look for materials/methods-specific excerpts
            materials_indicators = [
                'concrete', 'steel', 'timber', 'material selection', 'chosen',
                'comparison', 'versus', 'alternative', 'decision', 'rationale'
            ]
            
            excerpt = ""
            for indicator in materials_indicators:
                if indicator in content.lower():
                    # Find sentence containing the indicator
                    sentences = content.split('.')
                    for sentence in sentences:
                        if indicator in sentence.lower():
                            excerpt = sentence.strip()[:200] + "..."
                            break
                    if excerpt:
                        break
            
            if not excerpt:
                excerpt = content[:200] + "..." if content else "Materials/methods document"
            
            sources.append({
                'filename': filename,
                'project_id': project_name,
                'relevance_score': relevance_score,
                'blob_url': doc.get('blob_url', ''),
                'excerpt': excerpt,
                'folder_path': doc_info['folder_path']
            })
        
        return sources

    def _format_internal_knowledge_sources(self, documents: List[Dict], components: Dict[str, Any]) -> List[Dict]:
        """Format internal knowledge document sources with enhanced context."""
        sources = []
        
        for doc in documents:
            # Use comprehensive document info extraction
            doc_info = self._extract_document_info(doc)
            filename = doc_info['filename']
            project_name = doc_info['project_id'] or 'Knowledge Base'
            
            # Get the internal knowledge relevance score
            relevance_score = doc.get('internal_knowledge_score', doc.get('@search.score', 0.5))
            
            # Create context-aware excerpt
            content = doc.get('content', '')
            
            # Look for knowledge-specific excerpts
            knowledge_indicators = [
                'engineer', 'expertise', 'experience', 'specialist', 'skilled',
                'team', 'responsible', 'designed by', 'worked on', 'involved'
            ]
            
            excerpt = ""
            for indicator in knowledge_indicators:
                if indicator in content.lower():
                    # Find sentence containing the indicator
                    sentences = content.split('.')
                    for sentence in sentences:
                        if indicator in sentence.lower():
                            excerpt = sentence.strip()[:200] + "..."
                            break
                    if excerpt:
                        break
            
            if not excerpt:
                excerpt = content[:200] + "..." if content else "Internal knowledge document"
            
            sources.append({
                'filename': filename,
                'project_id': project_name,
                'relevance_score': relevance_score,
                'blob_url': doc.get('blob_url', ''),
                'excerpt': excerpt,
                'folder_path': doc_info['folder_path']
            })
        
        return sources
