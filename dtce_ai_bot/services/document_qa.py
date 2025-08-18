"""
GPT integration service for answering questions about documents.
Connects to Azure OpenAI or OpenAI to provide intelligent responses.
"""

import asyncio
import re
from typing import List, Dict, Any, Optional
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
            
            # Check if this is a keyword-based project search query
            if self._is_project_keyword_query(question):
                return await self._handle_keyword_project_query(question, project_filter)
            
            # Check if this is an NZ Standards/code query
            if self._is_nz_standards_query(question):
                return await self._handle_nz_standards_query(question, project_filter)
            
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
                        'filename': doc['filename'],  # Use existing field name
                        'project_id': self._extract_project_from_url(doc.get('blob_url', '')) or doc.get('project_name', ''),  # Use existing field name
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
