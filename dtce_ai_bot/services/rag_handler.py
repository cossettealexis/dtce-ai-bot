"""
RAG (Retrieval-Augmented Generation) Handler for DTCE AI Bot
UNIFIED SEMANTIC SEARCH FLOW - No pattern matching, direct search for ALL questions
"""

import re
from typing import List, Dict, Any, Optional
import structlog
from azure.search.documents import SearchClient
from openai import AsyncAzureOpenAI

logger = structlog.get_logger(__name__)


class RAGHandler:
    """Handles RAG processing with unified semantic search flow for ALL questions."""
    
    def __init__(self, search_client: SearchClient, openai_client: AsyncAzureOpenAI, model_name: str):
        self.search_client = search_client
        self.openai_client = openai_client
        self.model_name = model_name
    
    async def process_rag_query(self, question: str, project_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        UNIFIED SEMANTIC SEARCH FLOW - No pattern matching, direct search for ALL questions:
        
        The user has asked the following question: "{user_question}"
        You will now perform the following steps:
        1. Search the user's question in SuiteFiles using semantic + OR-based keyword query
        2. From SuiteFiles, retrieve the most relevant documents or excerpts related to the question
        3. Read and understand the user's intent
        4. Use the retrieved content to construct a helpful and natural-sounding answer, only if the content is relevant to the user's query
        5. If the retrieved documents are not relevant, answer the question based on your general knowledge instead
        """
        try:
            logger.info("Processing ALL questions with unified semantic search", question=question)
            
            # STEP 1: Search user's question using SEMANTIC SEARCH for better intent understanding
            documents = await self._search_documents(question, project_filter, use_semantic=True)
            
            # If semantic search doesn't find enough results, also try keyword OR search
            if len(documents) < 5:
                logger.info("Enhancing results with keyword search")
                search_words = [word.strip() for word in question.split() if len(word.strip()) > 2]
                keyword_query = ' OR '.join(search_words)
                keyword_docs = await self._search_documents(keyword_query, project_filter, use_semantic=False)
                
                # Combine and deduplicate results
                seen_ids = {doc.get('id') for doc in documents}
                for doc in keyword_docs:
                    if doc.get('id') not in seen_ids:
                        documents.append(doc)
                        seen_ids.add(doc.get('id'))
            
            logger.info("Unified semantic + keyword search results", 
                       total_documents=len(documents),
                       sample_filenames=[doc.get('filename', 'Unknown') for doc in documents[:3]])
            
            # STEP 2: Retrieve most relevant documents from index
            if documents:
                # Format retrieved content from the index
                index_results = []
                for doc in documents[:10]:  # Top 10 most relevant
                    filename = doc.get('filename', 'Unknown')
                    content = doc.get('content', '')
                    blob_url = doc.get('blob_url', '')
                    suitefiles_link = self._get_safe_suitefiles_url(blob_url)
                    
                    doc_result = f"**Document: {filename}**\n"
                    if suitefiles_link and suitefiles_link != "Document available in SuiteFiles":
                        doc_result += f"SuiteFiles Link: {suitefiles_link}\n"
                    doc_result += f"Content: {content[:800]}..."
                    index_results.append(doc_result)
                
                retrieved_content = "\n\n".join(index_results)
            else:
                retrieved_content = "No relevant documents found in SuiteFiles."
            
            # STEP 3: GPT analyzes user intent and constructs natural answer
            prompt = f"""The user has asked the following question: "{question}"

I have ALREADY searched SuiteFiles and retrieved the most relevant content for you.

Your task is to:
1. Read and understand the user's intent from their question
2. Analyze the retrieved content I'm providing below from SuiteFiles
3. Use the retrieved content to construct a helpful and natural-sounding answer, ONLY if the content is relevant to the user's query
4. If the retrieved documents are not relevant to the user's question, answer based on your general engineering knowledge instead

ℹ️ Reference Example (rag.txt)
You may refer to the following example file — rag.txt — which contains example question-answer formats showing how the AI could respond to different structural engineering and project-related queries.
However, do not copy from this file or rely on its content directly. It is only a reference to help you understand the style and expectations of the response. You must still follow the actual question, the user's intent, and the retrieved documents.

📎 Retrieved content from SuiteFiles:
{retrieved_content}

✅ Final Task:
Based on the above retrieved content from SuiteFiles and the user's intent, provide a helpful, relevant, and human-like response.

🔗 CRITICAL: When you mention ANY document from the retrieved content, you MUST include its clickable SuiteFiles link immediately after mentioning the document name. The links are provided in the retrieved content above - USE THEM!

Example: "According to the Manual for Design (SuiteFiles Link: https://dtce.suitefiles.com/...)"

- Use content from the retrieved documents only if applicable and relevant
- ALWAYS include the actual SuiteFiles links when referencing specific documents
- If documents do not help answer the user's specific question, use your own general knowledge
- Your goal is to be informative and context-aware, not robotic or overly reliant on past formats
- Focus on practical engineering guidance for New Zealand conditions when applicable"""
            
            answer = await self._generate_project_answer_with_links(prompt, retrieved_content)
            
            return {
                'answer': answer,
                'sources': self._format_sources(documents) if documents else [],
                'confidence': 'high' if documents else 'medium',
                'documents_searched': len(documents),
                'rag_type': 'unified_semantic_search'
            }
                
        except Exception as e:
            logger.error("RAG processing failed", error=str(e), question=question)
            return {
                'answer': f'I encountered an error while processing your question: {str(e)}',
                'sources': [],
                'confidence': 'error',
                'documents_searched': 0,
                'rag_type': 'error'
            }
    
    async def _search_documents(self, search_query: str, project_filter: Optional[str] = None, 
                              doc_types: Optional[List[str]] = None, use_semantic: bool = True) -> List[Dict]:
        """Search for relevant documents using both semantic and keyword search."""
        try:
            logger.info("Searching Azure index", search_query=search_query, doc_types=doc_types, use_semantic=use_semantic)
            
            # Build search parameters with semantic search capability
            search_params = {
                'search_text': search_query,
                'top': 20,
                'select': ["id", "filename", "content", "blob_url", "project_name", "folder"]
            }
            
            # Add semantic search configuration for better intent understanding
            if use_semantic:
                search_params.update({
                    'query_type': 'semantic',
                    'semantic_configuration_name': 'default',
                    'query_caption': 'extractive',
                    'query_answer': 'extractive'
                })
                logger.info("Using semantic search for better intent understanding")
            
            # Add document type filter if specified
            if doc_types:
                doc_filter = ' or '.join([f"search.ismatch('*.{ext}', 'filename')" for ext in doc_types])
                search_params['filter'] = doc_filter
                logger.info("Added document type filter", filter=doc_filter)
            
            # Try semantic search first, fallback to keyword if it fails
            try:
                results = self.search_client.search(**search_params)
                documents = [dict(result) for result in results]
                
                logger.info("Search completed successfully", 
                           search_type="semantic" if use_semantic else "keyword",
                           documents_found=len(documents),
                           filenames=[doc.get('filename', 'Unknown') for doc in documents[:5]])
                
            except Exception as semantic_error:
                if use_semantic:
                    logger.warning("Semantic search failed, falling back to keyword search", 
                                 error=str(semantic_error))
                    
                    # Fallback to keyword search
                    search_params.pop('query_type', None)
                    search_params.pop('semantic_configuration_name', None)
                    search_params.pop('query_caption', None)
                    search_params.pop('query_answer', None)
                    
                    results = self.search_client.search(**search_params)
                    documents = [dict(result) for result in results]
                    
                    logger.info("Keyword search fallback completed", 
                               documents_found=len(documents),
                               filenames=[doc.get('filename', 'Unknown') for doc in documents[:5]])
                else:
                    raise semantic_error
            
            return documents
            
        except Exception as e:
            logger.error("Document search failed", error=str(e), search_query=search_query)
            return []
    
    def _get_safe_suitefiles_url(self, blob_url: str, link_type: str = "file") -> str:
        """Get SuiteFiles URL or fallback message if conversion fails."""
        if not blob_url:
            return "Document available in SuiteFiles"
        
        suitefiles_url = self._convert_to_suitefiles_url(blob_url, link_type)
        return suitefiles_url or "Document available in SuiteFiles"
    
    def _convert_to_suitefiles_url(self, blob_url: str, link_type: str = "file") -> Optional[str]:
        """Convert Azure blob URL to SuiteFiles URL."""
        if not blob_url:
            return None
        
        try:
            # Extract path from blob URL
            if "/dtce-ai-documents/" in blob_url:
                path_part = blob_url.split("/dtce-ai-documents/")[1]
                # Remove any query parameters
                if "?" in path_part:
                    path_part = path_part.split("?")[0]
                
                # Build SuiteFiles URL
                base_url = "https://dtce.suitefiles.com/suitefileswebdav/DTCE%20SuiteFiles/Projects"
                suitefiles_url = f"{base_url}/{path_part}"
                
                return suitefiles_url
                
        except Exception as e:
            logger.warning("Failed to convert blob URL to SuiteFiles", error=str(e), blob_url=blob_url)
            
        return None
    
    def _format_sources(self, documents: List[Dict]) -> List[Dict]:
        """Format document sources for response."""
        sources = []
        for doc in documents[:5]:  # Limit to top 5 sources
            source = {
                'filename': doc.get('filename', 'Unknown'),
                'project': doc.get('project_name', 'Unknown'),
                'folder': doc.get('folder', '')
            }
            
            # Add SuiteFiles link if available
            blob_url = doc.get('blob_url', '')
            if blob_url:
                suitefiles_url = self._get_safe_suitefiles_url(blob_url)
                if suitefiles_url and suitefiles_url != "Document available in SuiteFiles":
                    source['suitefiles_url'] = suitefiles_url
            
            sources.append(source)
        
        return sources
    
    async def _generate_project_answer_with_links(self, prompt: str, context: str) -> str:
        """Generate answer using GPT with project context and SuiteFiles links."""
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a helpful structural engineering AI assistant for DTCE. Provide practical, accurate engineering guidance for New Zealand conditions. Include SuiteFiles links when referencing specific documents."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1500,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error("GPT response generation failed", error=str(e))
            return f"I encountered an error generating the response: {str(e)}"
