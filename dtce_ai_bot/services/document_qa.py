"""
GPT integration service for answering questions about documents.
Connects to Azure OpenAI or OpenAI to provide intelligent responses.
"""

import asyncio
from typing import List, Dict, Any, Optional
import structlog
from azure.search.documents import SearchClient
from openai import AsyncOpenAI
from ..config.settings import get_settings

logger = structlog.get_logger(__name__)


class DocumentQAService:
    """Service for answering questions about indexed documents using GPT."""
    
    def __init__(self, search_client: SearchClient):
        """Initialize the QA service."""
        self.search_client = search_client
        settings = get_settings()
        
        # Initialize OpenAI client
        self.openai_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=getattr(settings, 'AZURE_OPENAI_ENDPOINT', None),
            api_version=getattr(settings, 'AZURE_OPENAI_API_VERSION', '2024-02-01')
        )
        
        self.model_name = getattr(settings, 'OPENAI_MODEL_NAME', 'gpt-4-turbo-preview')
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
            
            # Step 1: Search for relevant documents
            relevant_docs = await self._search_relevant_documents(question, project_filter)
            
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
                        'project_id': doc.get('project_name', 'Unknown'),
                        'relevance_score': doc['@search.score'],
                        'blob_url': doc.get('blob_url', ''),
                        'excerpt': doc.get('@search.highlights', {}).get('content', [''])[0][:200] + '...'
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
            # Build search filter
            search_filter = None
            if project_filter:
                search_filter = f"project_name eq '{project_filter}'"
            
            # Search with semantic ranking if available
            results = self.search_client.search(
                search_text=question,
                top=10,  # Get top 10 results
                filter=search_filter,
                highlight_fields="content",
                select=["id", "blob_name", "filename", "content", "project_name", 
                       "folder", "blob_url", "last_modified"],
                query_type="semantic" if hasattr(self.search_client, 'query_type') else "simple"
            )
            
            # Convert to list and return
            documents = []
            for result in results:
                documents.append(dict(result))
            
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
            # Extract relevant information
            filename = doc.get('filename', 'Unknown')
            project = doc.get('project_name', 'Unknown')
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

    async def _generate_answer(self, question: str, context: str) -> Dict[str, Any]:
        """Generate answer using GPT with document context."""
        try:
            import time
            start_time = time.time()
            
            # Prepare system prompt
            system_prompt = """You are an AI assistant helping engineers find information from project documents. 
            
            Your role:
            - Answer questions based ONLY on the provided document context
            - Be specific and cite relevant details from the documents
            - If the context doesn't contain the answer, clearly state that
            - Focus on engineering-relevant information like specifications, calculations, reports, and project details
            - Be concise but thorough
            
            Context format: Each document includes filename, project, and content.
            """
            
            # Prepare user prompt
            user_prompt = f"""
            Based on the following document context, please answer this question:
            
            Question: {question}
            
            Document Context:
            {context}
            
            Please provide a clear, specific answer based on the documents provided.
            """
            
            # Call OpenAI/Azure OpenAI
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # Low temperature for factual responses
                max_tokens=500   # Reasonable limit for answers
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
