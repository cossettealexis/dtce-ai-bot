"""
Document Question Answering Service

Provides intelligent responses to questions about DTCE's engineering documents,
project files, policies, and technical standards using RAG (Retrieval-Augmented Generation).

Main capabilities:
- Search across indexed documents in Azure Search
- Generate contextual answers using OpenAI GPT models
- Handle greetings and basic user interactions
- Route complex queries to specialized RAG processing

Usage:
    qa_service = DocumentQAService(search_client)
    result = await qa_service.answer_question("What is our IT policy?")
"""

import time
from typing import Dict, Any, Optional
import structlog
from azure.search.documents import SearchClient
from openai import AsyncAzureOpenAI

from ..config.settings import get_settings
from .google_sheets_knowledge import GoogleSheetsKnowledgeService

logger = structlog.get_logger(__name__)


class DocumentQAService:
    """
    Service for answering questions about DTCE's indexed documents.
    
    This service acts as the main entry point for document-based question answering.
    It handles user greetings and routes all substantive questions to the RAGHandler
    which performs semantic search and generates intelligent responses.
    
    Attributes:
        search_client: Azure Search client for document retrieval
        openai_client: OpenAI client for generating responses
        rag_handler: RAG processor with smart prompting capabilities
    """
    
    def __init__(self, search_client: SearchClient):
        self.search_client = search_client
        settings = get_settings()
        
        # Initialize OpenAI client
        self.openai_client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint
        )
        
        self.model_name = settings.azure_openai_deployment_name
        
        # Initialize RAG handler with smart prompting (Single Responsibility)
        from .rag_handler import RAGHandler
        self.rag_handler = RAGHandler(self.search_client, self.openai_client, self.model_name, settings)
        
        # Initialize Google Sheets Knowledge Service as primary knowledge source
        self.google_sheets_service = GoogleSheetsKnowledgeService()
        
    async def answer_question(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Answer a question using Google Sheets knowledge first, then RAG as fallback.
        
        Process:
        1. Check Google Sheets for similar question/answer pairs
        2. If match found with high confidence, return that answer
        3. Otherwise, fall back to existing RAG system
        
        Args:
            question: The question to answer
            project_filter: Optional project filter to limit search scope
            
        Returns:
            Dictionary with answer, sources, and metadata
        """
        try:
            start_time = time.time()
            logger.info("Processing question", question=question, project_filter=project_filter)
            
            # Handle basic greetings (Single Responsibility)
            if self._is_greeting(question):
                return self._get_greeting_response()
            
            # STEP 1: Check Google Sheets knowledge first
            sheets_match = await self.google_sheets_service.find_similar_question(
                question, 
                similarity_threshold=0.4  # Adjusted for better partial matching
            )
            
            if sheets_match:
                logger.info("Found match in Google Sheets knowledge", 
                           similarity=sheets_match['similarity'],
                           matched_question=sheets_match['question'][:100])
                
                return {
                    'answer': sheets_match['answer'],
                    'sources': [{
                        'title': 'DTCE Knowledge Base',
                        'content': f"Q: {sheets_match['question']}\nA: {sheets_match['answer']}",
                        'similarity': sheets_match['similarity'],
                        'url': '#knowledge-base'
                    }],
                    'confidence': 'high' if sheets_match['similarity'] > 0.8 else 'medium',
                    'documents_searched': 0,
                    'search_type': 'google_sheets_knowledge',
                    'processing_time': time.time() - start_time,
                    'knowledge_base_match': True,
                    'similarity_score': sheets_match['similarity']
                }
            
            # STEP 2: Fall back to existing RAG system if no Google Sheets match
            logger.info("No Google Sheets match found, using RAG system")
            session_id = project_filter or "default"  # Use project as session context
            result = await self.rag_handler.process_question(question, session_id)
            
            # Add processing metadata
            result['processing_time'] = time.time() - start_time
            result['knowledge_base_match'] = False
            
            logger.info("Question answered via RAG", 
                       question=question,
                       confidence=result.get('confidence', 'unknown'),
                       processing_time=result['processing_time'])
            
            return result
            
        except Exception as e:
            logger.error("Question answering failed", error=str(e), question=question)
            return {
                'answer': f'I encountered an error while processing your question: {str(e)}',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0,
                'search_type': 'error',
                'processing_time': 0
            }
    
    def _is_greeting(self, question: str) -> bool:
        """Check if the question is a basic greeting."""
        if not question:
            return True
            
        greetings = ['hi', 'hello', 'hey', 'greetings', 'good morning', 'good afternoon']
        question_lower = question.lower().strip()
        
        return (
            question_lower in greetings or
            len(question_lower.split()) <= 2 and any(greeting in question_lower for greeting in greetings)
        )
    
    def _get_greeting_response(self) -> Dict[str, Any]:
        """Return a standard greeting response."""
        return {
            'answer': """Hello! I'm the DTCE AI Assistant. I can help you find information from DTCE's project documents, engineering standards, policies, and provide technical guidance.

What would you like to know? You can ask about:
- Project documents and reports
- Engineering standards and codes  
- Company policies and procedures
- Technical calculations and specifications
- Past project examples and references""",
            'sources': [],
            'confidence': 'high',
            'documents_searched': 0,
            'search_type': 'greeting',
            'processing_time': 0
        }
