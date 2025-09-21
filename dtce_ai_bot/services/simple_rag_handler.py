"""
Simple RAG Handler for DTCE AI Bot
Minimal working implementation without external service dependencies
"""

import re
import os
from typing import List, Dict, Any, Optional
import structlog
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from openai import AsyncAzureOpenAI

logger = structlog.get_logger(__name__)


class SimpleRAGHandler:
    """Simple RAG handler with no external service dependencies."""
    
    def __init__(self):
        # Initialize Azure Search client
        search_service_name = os.getenv("AZURE_SEARCH_SERVICE_NAME")
        search_admin_key = os.getenv("AZURE_SEARCH_ADMIN_KEY") 
        search_index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "dtce-docs")
        
        if not all([search_service_name, search_admin_key]):
            raise ValueError("Missing Azure Search configuration")
        
        search_endpoint = f"https://{search_service_name}.search.windows.net"
        credential = AzureKeyCredential(search_admin_key)
        self.search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=search_index_name,
            credential=credential
        )
        
        # Initialize OpenAI client
        openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        openai_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        
        if not all([openai_endpoint, openai_api_key]):
            raise ValueError("Missing Azure OpenAI configuration")
        
        self.openai_client = AsyncAzureOpenAI(
            azure_endpoint=openai_endpoint,
            api_key=openai_api_key,
            api_version="2024-02-15-preview"
        )
        
        self.model_name = os.getenv("AZURE_OPENAI_CHAT_MODEL", "gpt-4")
    
    async def process_question(self, question: str) -> Dict[str, Any]:
        """Process a question and return an answer with sources."""
        try:
            logger.info("Processing question", question=question)
            
            # Search for relevant documents
            documents = await self._search_documents(question)
            
            if documents:
                # Generate answer using found documents
                return await self._generate_answer_with_documents(question, documents)
            else:
                # No documents found - provide general response
                return await self._handle_no_documents(question)
                
        except Exception as e:
            logger.error("Error processing question", error=str(e))
            return {
                'answer': f'I encountered an error processing your question: {str(e)}',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0,
                'rag_type': 'error'
            }
    
    async def _search_documents(self, query: str, top: int = 10) -> List[Dict]:
        """Search for relevant documents in Azure Search."""
        try:
            # Simple search parameters - use existing index fields
            search_params = {
                'search_text': query,
                'top': top,
                'select': ["id", "filename", "content", "blob_url"]  # Use known fields
            }
            
            results = self.search_client.search(**search_params)
            documents = [dict(result) for result in results]
            
            logger.info("Search completed", documents_found=len(documents))
            return documents
            
        except Exception as e:
            logger.error("Document search failed", error=str(e))
            return []
    
    async def _generate_answer_with_documents(self, question: str, documents: List[Dict]) -> Dict[str, Any]:
        """Generate an answer using the found documents."""
        try:
            # Format documents for the prompt
            formatted_docs = self._format_documents(documents)
            
            # Create the prompt
            prompt = f"""Based on the following documents, please answer the user's question:

Documents:
{formatted_docs}

Question: {question}

Please provide a comprehensive answer based on the documents above. Include references to the source documents where appropriate."""

            # Generate response
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful AI assistant for DTCE, a New Zealand engineering consultancy. Answer questions based on the provided documents."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.1
            )
            
            answer = response.choices[0].message.content
            
            # Format sources
            sources = self._format_sources(documents)
            
            return {
                'answer': answer,
                'sources': sources,
                'confidence': 'high',
                'documents_searched': len(documents),
                'rag_type': 'document_based'
            }
            
        except Exception as e:
            logger.error("Error generating answer", error=str(e))
            return {
                'answer': 'I encountered an error generating the answer.',
                'sources': [],
                'confidence': 'error',
                'documents_searched': len(documents),
                'rag_type': 'error'
            }
    
    async def _handle_no_documents(self, question: str) -> Dict[str, Any]:
        """Handle cases where no documents are found."""
        try:
            # Provide general engineering advice
            prompt = f"""You are a senior structural engineering consultant. A user asked: "{question}"

Since no specific documents were found, please provide general engineering guidance based on your knowledge of:
- New Zealand building codes and standards
- Structural engineering best practices
- Common engineering approaches and considerations

Please provide a helpful response while noting that this is general guidance and specific DTCE procedures should be checked."""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a senior structural engineering consultant providing general engineering guidance for a New Zealand engineering firm."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.1
            )
            
            answer = response.choices[0].message.content
            disclaimer = "\n\n**Note:** This is general engineering guidance. For specific DTCE procedures or project information, please check SuiteFiles or consult with colleagues."
            
            return {
                'answer': answer + disclaimer,
                'sources': [],
                'confidence': 'general',
                'documents_searched': 0,
                'rag_type': 'general_knowledge'
            }
            
        except Exception as e:
            logger.error("Error generating fallback response", error=str(e))
            return {
                'answer': 'I couldn\'t find specific information about your question. Please try rephrasing or check SuiteFiles directly.',
                'sources': [],
                'confidence': 'low',
                'documents_searched': 0,
                'rag_type': 'fallback'
            }
    
    def _format_documents(self, documents: List[Dict]) -> str:
        """Format documents for the prompt."""
        formatted = []
        for i, doc in enumerate(documents[:5], 1):  # Limit to top 5 documents
            filename = doc.get('filename', 'Unknown')
            content = doc.get('content', '')[:1000]  # Truncate content
            formatted.append(f"Document {i} ({filename}):\n{content}")
        
        return "\n\n".join(formatted)
    
    def _format_sources(self, documents: List[Dict]) -> List[Dict]:
        """Format sources for the response."""
        sources = []
        for doc in documents[:5]:  # Limit to top 5 sources
            source = {
                'filename': doc.get('filename', 'Unknown'),
                'title': doc.get('filename', 'Unknown'),
                'url': doc.get('blob_url', 'No URL')
            }
            sources.append(source)
        
        return sources
