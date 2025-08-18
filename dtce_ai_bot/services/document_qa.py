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
                        'filename': doc['filename'],
                        'project_id': self._extract_project_from_url(doc.get('blob_url', '')) or doc.get('project_name', '') or 'Unknown',
                        'relevance_score': doc['@search.score'],
                        'blob_url': doc.get('blob_url', ''),
                        'excerpt': self._get_excerpt(doc)
                    }
                    for doc in relevant_docs[:5]  # Top 5 sources for better context
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
            system_prompt = """You are an advanced AI assistant for DTCE (engineering consultancy) that provides detailed, contextual answers using available documentation and professional knowledge.

            YOUR CAPABILITIES:
            1. DOCUMENT-BASED ANSWERS: Analyze and summarize information from provided documents
            2. PROJECT INSIGHTS: When asked about projects, provide comprehensive overviews including:
               - Project structure and sub-projects
               - Document types and contents
               - Key dates and personnel
               - Project status and activities
            3. BUSINESS PROCESS GUIDANCE: Provide step-by-step guidance for workflows
            4. ENGINEERING EXPERTISE: Answer technical questions with references
            5. CONTEXTUAL INTELLIGENCE: Always provide relevant context even for simple queries

            RESPONSE PRINCIPLES:
            1. BE COMPREHENSIVE: Don't just say documents exist - explain what they contain
            2. BE SPECIFIC: Mention file names, dates, project numbers, and details
            3. BE CONTEXTUAL: For any project query, provide an overview of what's available
            4. BE HELPFUL: Always suggest next steps or where to find more information
            5. BE INTELLIGENT: Even for simple queries, provide valuable context

            FOR PROJECT QUERIES (like "project 219"):
            - Provide an overview of all sub-projects and their purposes
            - List key documents and their contents
            - Mention important dates, locations, or personnel if available
            - Suggest specific areas the user might want to explore further

            FOR DOCUMENT QUERIES:
            - Explain what the document contains
            - Provide relevant excerpts or summaries
            - Mention related documents or projects

            FOR GENERAL QUERIES:
            - Use any relevant context from documents
            - Provide professional guidance based on DTCE's work
            - Suggest specific resources or next steps
            """
            
            # Prepare enhanced user prompt
            user_prompt = f"""
            Question: {question}

            Available Document Context:
            {context if context.strip() else "No specific documents found for this query."}

            INSTRUCTIONS FOR YOUR RESPONSE:
            - Provide a comprehensive, detailed answer
            - If this is about a project, give a complete overview of what's available
            - Include specific file names, dates, and project details when available
            - Explain what each document likely contains based on its name and context
            - For simple queries, still provide valuable context and insights
            - Suggest specific next steps or areas to explore
            - Be conversational but informative

            Provide a detailed response that fully addresses the question with all available context.
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
