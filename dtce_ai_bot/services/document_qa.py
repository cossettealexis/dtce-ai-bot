"""
GPT integration service for answering questions about documents.
Connects to Azure OpenAI or OpenAI to provide intelligent responses.
Features fallback to SharePoint search when Azure Search results are insufficient.
"""

import asyncio
import re
from typing import List, Dict, Any, Optional
import structlog
from azure.search.documents import SearchClient
from openai import AsyncAzureOpenAI
from ..config.settings import get_settings
from ..integrations.microsoft.sharepoint_client import SharePointClient

logger = structlog.get_logger(__name__)


class DocumentQAService:
    """Service for answering questions about indexed documents using GPT with SharePoint fallback."""
    
    def __init__(self, search_client: SearchClient):
        """Initialize the QA service."""
        self.search_client = search_client
        self.sharepoint_client = SharePointClient()  # Add SharePoint fallback
        settings = get_settings()
        
        # Initialize Azure OpenAI client
        self.openai_client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version
        )
        
        self.model_name = settings.azure_openai_deployment_name
        self.max_context_length = 8000  # Conservative limit for context
        
        # Fallback thresholds
        self.min_search_score = 1.0  # Minimum score for Azure Search results
        self.min_document_count = 3   # Minimum documents needed for confidence
        
    async def answer_question(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Answer a question using document context from the search index.
        Falls back to SharePoint search if Azure Search results are insufficient.
        
        Args:
            question: The question to answer
            project_filter: Optional project filter to limit search scope
            
        Returns:
            Dictionary with answer, sources, and metadata
        """
        try:
            logger.info("Processing question", question=question, project_filter=project_filter)
            
            # Convert dates in the question to match filename formats
            converted_question = self._convert_date_formats(question)
            
            # Step 1: Try Azure Search first
            relevant_docs = await self._search_relevant_documents(converted_question, project_filter)
            search_source = "azure_search"
            
            # Step 2: Check if Azure Search results are sufficient
            needs_fallback = self._should_fallback_to_sharepoint(relevant_docs, question)
            
            if needs_fallback:
                logger.info("Azure Search results insufficient, trying SharePoint fallback", 
                          docs_found=len(relevant_docs), 
                          question=question)
                
                # Try SharePoint fallback
                sharepoint_docs = await self._search_sharepoint_fallback(question, project_filter)
                if sharepoint_docs:
                    relevant_docs.extend(sharepoint_docs)
                    search_source = "azure_search_with_sharepoint_fallback"
                    logger.info("SharePoint fallback found additional documents", 
                              sharepoint_docs=len(sharepoint_docs))
                else:
                    search_source = "azure_search_only_insufficient"
            
            if not relevant_docs:
                return {
                    'answer': 'I could not find any relevant documents to answer your question. The information might not be indexed yet, or it may not exist in the document repositories.',
                    'sources': [],
                    'confidence': 'low',
                    'documents_searched': 0,
                    'search_source': 'no_results'
                }
            
            # Step 3: Prepare context from relevant documents
            context = self._prepare_context(relevant_docs)
            
            # Step 4: Generate answer using GPT
            answer_response = await self._generate_answer(question, context)
            
            # Step 5: Format response with sources
            return {
                'answer': answer_response['answer'],
                'sources': [
                    {
                        'filename': doc.get('filename', doc.get('name', 'Unknown')),
                        'project_id': self._extract_project_from_url(doc.get('blob_url', '')) or doc.get('project_name', '') or 'Unknown',
                        'relevance_score': doc.get('@search.score', 0.8),  # Default score for SharePoint docs
                        'blob_url': doc.get('blob_url', ''),
                        'sharepoint_url': doc.get('sharepoint_url', ''),
                        'source_type': doc.get('source_type', 'azure_search'),
                        'excerpt': self._get_excerpt(doc)
                    }
                    for doc in relevant_docs[:5]  # Top 5 sources for better context
                ],
                'confidence': answer_response['confidence'],
                'documents_searched': len(relevant_docs),
                'search_source': search_source,
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
            # Start with the original question - keep it simple and smart
            search_text = question
            
            # Convert date formats in the question to match filename patterns
            search_text = self._convert_date_formats(search_text)
            
            # Perform the search - let Azure Search do the heavy lifting
            results = self.search_client.search(
                search_text=search_text,
                top=20,  # Get good number of relevant results
                highlight_fields="filename,project_name,content",
                select=["id", "filename", "content", "blob_url", "last_modified", "project_name", "folder"],
                query_type="semantic" if hasattr(self.search_client, 'query_type') else "simple"
            )
            
            # Convert to list - include ALL results, let GPT decide relevance
            documents = []
            for result in results:
                doc_dict = dict(result)
                documents.append(doc_dict)
            
            logger.info("Found relevant documents", count=len(documents), question=question)
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
            filename = doc.get('filename', 'Unknown')
            project = self._extract_project_from_url(doc.get('blob_url', '')) or doc.get('project_name', '') or 'Unknown'
            # Use the correct field name for content
            content = doc.get('content', '')
            
            # Truncate content if too long but keep more content for better context
            if len(content) > 1500:
                content = content[:1500] + "..."
            
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
            system_prompt = """You are an advanced AI assistant for DTCE (engineering consultancy) with expertise in structural and civil engineering, particularly New Zealand construction standards and practices.

            YOUR CAPABILITIES:
            1. DOCUMENT-BASED ANSWERS: Analyze and summarize information from provided documents when available
            2. ENGINEERING EXPERTISE: Provide professional engineering knowledge, especially for:
               - NZS (New Zealand Standards) codes and requirements
               - Structural design principles and calculations
               - Concrete, steel, timber, and other construction materials
               - Foundation design and geotechnical considerations
               - Building Code compliance and best practices
            3. PROFESSIONAL GUIDANCE: Offer practical engineering advice and industry best practices
            4. PROJECT INSIGHTS: When documents are available, provide comprehensive project overviews

            RESPONSE STRATEGY:
            1. For GENERAL ENGINEERING QUESTIONS (like NZS codes, design requirements, etc.):
               - Provide comprehensive professional knowledge even if no specific documents are found
               - Reference relevant standards, codes, and best practices
               - Give practical, actionable guidance
               - Explain the engineering principles behind requirements

            2. For PROJECT-SPECIFIC QUESTIONS:
               - Use available project documents when relevant
               - Provide project overviews, document summaries, and specific details

            3. For BUSINESS PROCESS QUESTIONS:
               - Provide step-by-step guidance for workflows and procedures

            IMPORTANT: Don't be limited by available documents. If someone asks about NZS standards, concrete cover requirements, design loads, etc., provide comprehensive professional engineering knowledge based on standard industry practices and codes, even if specific documents aren't in your search results.

            EXAMPLES:
            - "What are NZS 3101 concrete cover requirements?" → Provide detailed professional knowledge about concrete cover standards
            - "How do I design a retaining wall?" → Give comprehensive engineering guidance regardless of available documents
            - "Project 219 information?" → Use available project documents to provide specific details
            """
            
            # Prepare enhanced user prompt
            user_prompt = f"""
            Question: {question}

            Available Document Context:
            {context if context.strip() else "No specific documents found for this query."}

            INSTRUCTIONS FOR YOUR RESPONSE:
            
            If this is a GENERAL ENGINEERING QUESTION (about standards, codes, design principles, etc.):
            - Provide comprehensive professional engineering knowledge
            - Don't be limited by the available documents
            - Reference relevant NZS standards, building codes, and best practices
            - Give practical, actionable engineering guidance
            
            If this is a PROJECT-SPECIFIC QUESTION and documents are available:
            - Use the document context to provide specific project details
            - Include file names, dates, and project information
            - Explain what the documents contain and their relevance
            
            If this is a BUSINESS PROCESS QUESTION:
            - Provide step-by-step guidance for workflows and procedures
            
            Always be helpful, comprehensive, and provide valuable engineering expertise regardless of whether specific documents are available.
            """
            
            # Call OpenAI/Azure OpenAI with enhanced parameters
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,  # Lower for more focused, factual responses
                max_tokens=1200   # Increased for more comprehensive answers
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
        # Simple heuristics for confidence assessment
        if "I don't" in answer or "cannot find" in answer or "not mentioned" in answer:
            return 'low'
        elif len(context) > 2000 and len(answer) > 100:
            return 'high'
        elif len(context) > 1000:
            return 'medium'
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

    def _get_excerpt(self, doc: Dict[str, Any]) -> str:
        """Get excerpt from document with proper highlight handling."""
        # Try to get highlighted content first
        highlights = doc.get('@search.highlights')
        if highlights and isinstance(highlights, dict):
            if 'content' in highlights and highlights['content']:
                # Highlights are usually a list of strings
                highlight_text = highlights['content']
                if isinstance(highlight_text, list) and highlight_text:
                    return highlight_text[0][:200] + '...'
                elif isinstance(highlight_text, str):
                    return highlight_text[:200] + '...'
        
        # Fall back to regular content
        content = doc.get('content', '')
        if content:
            return content[:200] + '...'
        
        return 'No content preview available'
    
    def _should_fallback_to_sharepoint(self, azure_docs: List[Dict], question: str) -> bool:
        """
        Determine if we should fallback to SharePoint search based on Azure Search results quality.
        
        Args:
            azure_docs: Documents returned from Azure Search
            question: Original question
            
        Returns:
            True if SharePoint fallback should be attempted
        """
        # No documents found - definitely need fallback
        if not azure_docs:
            return True
        
        # Too few documents found
        if len(azure_docs) < self.min_document_count:
            return True
        
        # Check if search scores are too low (indicating poor relevance)
        high_score_docs = [doc for doc in azure_docs 
                          if doc.get('@search.score', 0) >= self.min_search_score]
        
        if len(high_score_docs) < 2:  # Less than 2 high-relevance documents
            return True
        
        # Check for specific patterns that might need SharePoint fallback
        question_lower = question.lower()
        sharepoint_indicators = [
            'latest', 'recent', 'current', 'new', 'updated',
            'sharepoint', 'suitefiles', 'live', 'online'
        ]
        
        if any(indicator in question_lower for indicator in sharepoint_indicators):
            return True
        
        return False
    
    async def _search_sharepoint_fallback(self, question: str, project_filter: Optional[str] = None) -> List[Dict]:
        """
        Search SharePoint/SuiteFiles as fallback when Azure Search is insufficient.
        
        Args:
            question: Original question
            project_filter: Optional project filter
            
        Returns:
            List of SharePoint documents formatted for compatibility
        """
        try:
            # Authenticate with SharePoint
            if not await self.sharepoint_client.authenticate():
                logger.warning("SharePoint authentication failed, skipping fallback")
                return []
            
            # Extract project info from question for targeted search
            project_id = self._extract_project_from_question(question)
            if project_filter:
                project_id = project_filter
            
            # Search specific project folder if identified
            sharepoint_docs = []
            if project_id:
                project_path = f"Projects/{project_id}"
                try:
                    project_docs = await self._search_sharepoint_folder(project_path, question)
                    sharepoint_docs.extend(project_docs)
                except Exception as e:
                    logger.warning("Failed to search specific project folder", 
                                 project_id=project_id, error=str(e))
            
            # Also search general Engineering folder for technical questions
            if self._is_technical_question(question):
                try:
                    engineering_docs = await self._search_sharepoint_folder("Engineering", question)
                    sharepoint_docs.extend(engineering_docs)
                except Exception as e:
                    logger.warning("Failed to search Engineering folder", error=str(e))
            
            # Format SharePoint docs for compatibility with Azure Search format
            formatted_docs = []
            for doc in sharepoint_docs[:10]:  # Limit to top 10 results
                formatted_doc = {
                    'filename': doc.get('name', 'Unknown'),
                    'content': doc.get('content', ''),
                    'blob_url': '',  # SharePoint doesn't use blob URLs
                    'sharepoint_url': doc.get('webUrl', ''),
                    'project_name': project_id or 'SharePoint',
                    'last_modified': doc.get('lastModifiedDateTime', ''),
                    'source_type': 'sharepoint',
                    '@search.score': 0.8  # Default good score for fallback results
                }
                formatted_docs.append(formatted_doc)
            
            logger.info("SharePoint fallback search completed", 
                       question=question, 
                       docs_found=len(formatted_docs))
            
            return formatted_docs
            
        except Exception as e:
            logger.error("SharePoint fallback search failed", error=str(e))
            return []
    
    async def _search_sharepoint_folder(self, folder_path: str, question: str) -> List[Dict]:
        """
        Search a specific SharePoint folder for relevant documents.
        
        Args:
            folder_path: Path to search in SharePoint
            question: Question to search for
            
        Returns:
            List of relevant documents from SharePoint
        """
        try:
            # Get folder contents
            folder_contents = await self.sharepoint_client.list_folder_contents(folder_path)
            
            relevant_docs = []
            search_terms = self._extract_search_terms(question)
            
            for item in folder_contents:
                if item.get('folder'):
                    # Skip folders for now - could implement recursive search later
                    continue
                
                # Check if file is relevant based on name and search terms
                if self._is_sharepoint_file_relevant(item, search_terms):
                    # Try to get file content for better matching
                    try:
                        file_metadata = await self.sharepoint_client.get_file_metadata(
                            f"{folder_path}/{item['name']}"
                        )
                        if file_metadata:
                            item.update(file_metadata)
                            relevant_docs.append(item)
                    except Exception as e:
                        logger.warning("Failed to get SharePoint file metadata", 
                                     file=item['name'], error=str(e))
                        # Add without metadata if we can't get it
                        relevant_docs.append(item)
            
            return relevant_docs
            
        except Exception as e:
            logger.error("SharePoint folder search failed", folder=folder_path, error=str(e))
            return []
    
    def _extract_search_terms(self, question: str) -> List[str]:
        """Extract key search terms from the question."""
        # Remove common stop words and extract meaningful terms
        stop_words = {'what', 'where', 'when', 'how', 'is', 'are', 'the', 'a', 'an', 'and', 'or', 'but'}
        
        # Split and clean terms
        terms = re.findall(r'\b\w{3,}\b', question.lower())  # Words with 3+ characters
        meaningful_terms = [term for term in terms if term not in stop_words]
        
        return meaningful_terms[:5]  # Return top 5 terms
    
    def _is_sharepoint_file_relevant(self, file_item: Dict, search_terms: List[str]) -> bool:
        """Check if a SharePoint file is relevant to the search terms."""
        file_name = file_item.get('name', '').lower()
        
        # Check if any search terms appear in filename
        for term in search_terms:
            if term in file_name:
                return True
        
        # Check file type - prefer documents over images
        supported_types = ['.pdf', '.docx', '.doc', '.txt', '.xlsx', '.xls']
        if any(file_name.endswith(ext) for ext in supported_types):
            return True
        
        return False
    
    def _is_technical_question(self, question: str) -> bool:
        """Determine if the question is technical/engineering related."""
        technical_keywords = [
            'standard', 'code', 'design', 'engineering', 'structural', 'calculation',
            'analysis', 'specification', 'drawing', 'nzs', 'as', 'load', 'concrete',
            'steel', 'foundation', 'beam', 'column', 'seismic', 'wind'
        ]
        
        question_lower = question.lower()
        return any(keyword in question_lower for keyword in technical_keywords)
