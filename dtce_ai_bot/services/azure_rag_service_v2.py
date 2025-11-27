"""
Azure RAG (Retrieval-Augmented Generation) Service - V2
Orchestration Layer: Intent Detection → Dynamic Filter Building → Hybrid Search → RAG Generation

Architecture (following best practices):
1. Intent Classification (GPT-4o-mini for fast classification)
2. Dynamic Filter Construction (OData filters based on intent + extracted metadata)
3. Hybrid Search + Semantic Ranking (Azure AI Search: Vector + Keyword + Semantic)
4. Context-Aware Answer Synthesis (GPT-4o with proper RAG prompt)
"""

import json
import structlog
from typing import List, Dict, Any, Optional
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.aio import SearchClient
from azure.search.documents.models import VectorizedQuery
from openai import AsyncAzureOpenAI
from .intent_detector_ai import IntentDetector
from ..utils.suitefiles_urls import suitefiles_converter

logger = structlog.get_logger(__name__)


class AzureRAGService:
    """
    RAG Orchestration Layer
    
    Implements the complete RAG pipeline with intent-based routing:
    1. Intent Detection: Classify query into knowledge categories
    2. Dynamic Routing: Build OData filters based on intent and extracted metadata
    3. Hybrid Search: Vector + Keyword search with semantic ranking
    4. Answer Synthesis: Generate natural, citation-backed responses
    """
    
    def __init__(self, search_client: SearchClient, openai_client: AsyncAzureOpenAI, model_name: str, intent_model_name: str, max_retries: int = 3):
        """
        Initialize RAG service with Azure clients.
        
        Args:
            search_client: Azure AI Search async client
            openai_client: Azure OpenAI async client
            model_name: GPT model name for answer synthesis (e.g., "gpt-4o")
            intent_model_name: GPT model for intent classification (e.g., "gpt-4o-mini")
            max_retries: The maximum number of retries for OpenAI API calls.
        """
        self.search_client = search_client
        self.openai_client = openai_client
        self.openai_client.max_retries = max_retries
        self.model_name = model_name
        self.embedding_model = "text-embedding-3-small"  # Azure OpenAI embedding deployment
        self.intent_detector = IntentDetector(openai_client, intent_model_name, max_retries)
        
    async def process_query(self, user_query: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """
        Main RAG Orchestration Pipeline
        
        Pipeline Steps:
        1. Intent Classification (detect query category)
        2. Dynamic Filter Building (construct OData filter)
        3. Hybrid Search with Semantic Ranking
        4. Answer Synthesis (generate natural response with citations)
        
        Args:
            user_query: The user's question
            conversation_history: Optional conversation context
            
        Returns:
            Dict containing answer, sources, intent, and metadata
        """
        try:
            logger.info("Starting RAG orchestration", query=user_query)
            
            # STEP 1: Intent Classification
            intent = await self.intent_detector.classify_intent(user_query)
            
            # Handle Simple Test queries without document search
            if intent == "Simple_Test":
                logger.info("Simple test query detected - providing direct response", query=user_query)
                return {
                    'answer': "Hello! I'm the DTCE AI Assistant. I can help you with:\n\n• Company policies and procedures\n• Engineering standards and codes\n• Past project information\n• Client details\n• Technical questions\n\nWhat would you like to know about?",
                    'sources': [],
                    'intent': intent,
                    'search_type': 'direct_response',
                    'total_documents_searched': 0,
                    'final_documents_used': 0,
                    'has_relevant_content': True,
                    'confidence_score': 1.0
                }
            
            # STEP 2: Dynamic Filter Construction
            search_filter = self.intent_detector.build_search_filter(intent, user_query)
            
            logger.info("Intent-based routing configured", 
                       intent=intent,
                       filter=search_filter)
            
            # STEP 3: Hybrid Search + Semantic Ranking
            search_results = await self._hybrid_search_with_ranking(
                query=user_query,
                filter_str=search_filter,
                top_k=50  # Increased from 10 to get more results for list queries
            )
            
            # STEP 4: Answer Synthesis
            # For list/comprehensive queries, use more results
            is_list_query = any(word in user_query.lower() for word in [
                'list', 'all', 'comprehensive', 'past', 'years', 'numbers', 'show me projects'
            ])
            
            results_to_use = min(20, len(search_results)) if is_list_query else min(5, len(search_results))
            
            logger.info("Answer synthesis configuration",
                       is_list_query=is_list_query,
                       results_to_use=results_to_use,
                       total_results=len(search_results))
            
            answer = await self._synthesize_answer(
                user_query=user_query,
                search_results=search_results[:results_to_use],
                conversation_history=conversation_history,
                intent=intent
            )
            
            return {
                'answer': answer,
                'sources': [self._format_source(r) for r in search_results[:5]],
                'intent': intent,
                'search_filter': search_filter,
                'total_documents': len(search_results),
                'search_type': 'hybrid_rag_with_intent_routing'
            }
            
        except Exception as e:
            logger.error("RAG orchestration failed", error=str(e), query=user_query)
            return {
                'answer': f"I encountered an error processing your question: {str(e)}",
                'sources': [],
                'intent': 'error',
                'search_filter': None,
                'total_documents': 0,
                'search_type': 'error'
            }
    
    async def _hybrid_search_with_ranking(self, query: str, filter_str: Optional[str] = None, top_k: int = 10) -> List[Dict]:
        """
        STEP 3.1: Hybrid Search & Semantic Ranking
        
        Combines:
        - Vector Search (semantic similarity via embeddings)
        - Keyword Search (BM25 for exact matches)
        - Semantic Ranking (Azure's L2 re-ranker)
        - Dynamic Filtering (based on intent)
        
        Args:
            query: The search query
            filter_str: OData filter string (e.g., "folder eq 'Policies'")
            top_k: Number of results to return
            
        Returns:
            List of search results with content and metadata
        """
        try:
            # Generate query embedding for vector search
            query_vector = await self._get_query_embedding(query)
            
            # Create vectorized query for semantic search
            vector_query = VectorizedQuery(
                vector=query_vector,
                k_nearest_neighbors=top_k,
                fields="content_vector"  # Matches index schema
            )
            
            # Build hybrid search parameters
            search_params = {
                "search_text": query,  # Keyword search (BM25)
                "vector_queries": [vector_query],  # Vector search (semantic)
                "query_type": "semantic",  # Enable semantic ranking
                "semantic_configuration_name": "default",  # Use default semantic config
                "top": top_k,
                "select": ["content", "filename", "folder", "project_name", "blob_url", "blob_name"],  # Include blob_name for full path
                "include_total_count": True
            }
            
            # Add filter if provided (intent-based routing)
            if filter_str:
                search_params["filter"] = filter_str
                logger.info("Applying search filter", filter=filter_str)
            
            # Execute hybrid search
            search_results_paged = await self.search_client.search(**search_params)
            
            # Process results
            results = []
            async for result in search_results_paged:
                filename = result.get('filename', 'Unknown Document')
                content = result.get('content', '')
                
                # Skip irrelevant files (placeholder and system files)
                if self._should_skip_file_in_results(filename, content):
                    logger.debug("Skipping irrelevant file from results", filename=filename)
                    continue
                
                # Log if content is minimal (placeholder documents)
                if not content or len(content) < 100:
                    logger.warning("Search result has minimal content", 
                                 filename=filename,
                                 content_length=len(content))
                    continue  # Skip files with no meaningful content
                
                results.append({
                    'content': content,
                    'filename': filename,
                    'folder': result.get('folder', ''),
                    'project_name': result.get('project_name', ''),
                    'search_score': result.get('@search.score', 0),
                    'reranker_score': result.get('@search.reranker_score', 0)
                })
            
            logger.info("Hybrid search completed", 
                       query=query, 
                       results_count=len(results),
                       filter_applied=filter_str is not None)
            
            return results
            
        except Exception as e:
            logger.error("Hybrid search failed", error=str(e), query=query)
            return []
    
    async def _get_query_embedding(self, query: str) -> List[float]:
        """
        Generate embedding for the query using Azure OpenAI.
        
        Args:
            query: The text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        try:
            response = await self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=query
            )
            return response.data[0].embedding
            
        except Exception as e:
            logger.error("Embedding generation failed", error=str(e))
            return []
    
    async def _synthesize_answer(
        self, 
        user_query: str, 
        search_results: List[Dict],
        conversation_history: List[Dict] = None,
        intent: str = "General_Knowledge"
    ) -> str:
        """
        STEP 3.2: RAG Answer Synthesis
        
        Generates a natural, conversational answer using retrieved documents.
        Follows the RAG Synthesis Prompt pattern:
        - Synthesize information from multiple sources
        - Include citations
        - Handle insufficient context gracefully
        - Maintain professional tone
        
        Args:
            user_query: The original user question
            search_results: Retrieved document chunks
            conversation_history: Optional conversation context
            intent: The classified intent category
            
        Returns:
            Natural language answer with citations
        """
        try:
            # Build context from retrieved documents
            if not search_results:
                return "I don't have specific information about that in our system. You might want to check with your colleagues, HR, or the relevant project teams who may have more detailed information."
            
            # Use ALL search results passed in (already filtered by caller based on query type)
            # Caller decides: 20 for list queries, 5 for regular queries
            context_chunks = []
            for i, result in enumerate(search_results, 1):  # Use ALL results passed in
                content = result.get('content', '')
                filename = result.get('filename', 'Unknown')
                folder = result.get('folder', '')
                blob_url = result.get('blob_url', '')
                blob_name = result.get('blob_name', '')
                
                # Get SuiteFiles URL for this document
                suitefiles_url = ""
                if blob_url:
                    # Extract proper folder path from blob_name if available
                    actual_folder_path = folder
                    if blob_name and '/' in blob_name:
                        # Extract folder path from full blob name (more accurate)
                        actual_folder_path = blob_name.rsplit('/', 1)[0]
                    
                    # Use actual folder path and filename to construct proper SharePoint path
                    suitefiles_url = suitefiles_converter.get_safe_suitefiles_url(
                        blob_url, 
                        folder_path=actual_folder_path, 
                        filename=filename
                    ) or ""
                
                # Use more generous truncation - try to get meaningful content
                # Take both the beginning and end of the document to catch key info
                if len(content) > 8000:
                    # Take first 4000 chars and last 3000 chars with separator
                    truncated_content = content[:4000] + "\n\n[... CONTENT TRUNCATED ...]\n\n" + content[-3000:]
                    logger.warning("Document content truncated for synthesis", 
                                   filename=filename,
                                   original_length=len(content),
                                   truncated_length=len(truncated_content))
                else:
                    truncated_content = content
                
                # Include metadata for citation formatting
                source_metadata = f"FILENAME: {filename}\nFOLDER: {folder}"
                if suitefiles_url:
                    source_metadata += f"\nSUITEFILES_URL: {suitefiles_url}"
                
                chunk = f"[Source {i}]\n{source_metadata}\nCONTENT:\n{truncated_content}"
                context_chunks.append(chunk)
            
            context = "\n\n".join(context_chunks)
            
            # Build conversation context if available
            conversation_context = ""
            if conversation_history:
                recent_turns = conversation_history[-3:]  # Last 3 turns
                conversation_context = "\n".join([
                    f"{turn['role'].capitalize()}: {turn['content']}" 
                    for turn in recent_turns
                ])
            
            # RAG Synthesis Prompt (following best practices)
            system_prompt = """You are the DTCE AI Chatbot. Your goal is to provide accurate, concise, and helpful answers based ONLY on the provided context.

Tone & Persona Rules:
1. Chatty and Friendly: Use a conversational, professional, but casual tone. Use contractions (I'm, you're, we'll, that's). Write like you're chatting with a colleague.
2. Proactive Greeting: Start every response by acknowledging the user's question directly. (e.g., "That's a great question, I can certainly check that for you!" or "I found the details on that policy..." or "Let me help you with that!")
3. Avoid Stiff Language: Do not use overly technical or formal business jargon. Write clearly, like a helpful colleague explaining something. Never mention "documents", "provided information", "based on the context" or similar stiff references.
4. Smart Analysis: Look for connections, patterns, and relevant information. If you find related information but not exact matches, mention what you found and explain how it might be helpful.
5. When Information is Missing: If you can't find the specific information requested, be honest but helpful in a conversational way. Say something like "I don't have information about [specific request], but I did find [related information] that might be useful" or "I couldn't find that specific info, but you might want to check with [suggestion]."
6. Answer Directly: Start with a direct, friendly answer to their question, then provide supporting information naturally.
7. Encouraging Closure: End the response with a helpful, open-ended closing statement, encouraging follow-up (e.g., "Let me know if you need anything else!" or "Feel free to ask if you have more questions!" or "Happy to help with anything else!")

Special Instructions for LIST QUERIES:
- When asked for "project numbers", "list of projects", "all projects from X years", extract and list PROJECT NUMBERS from folder paths
- Project numbers are 6-digit codes like 225126, 223112, 221045 found in folder paths like "Projects/225/225126/"
- For comprehensive lists, provide ALL unique project numbers found in the sources
- Group by year if helpful (e.g., "2021 Projects: 221001, 221045, 221089...")

CRITICAL: DTCE Year Code System
- The first 3 digits of project numbers indicate the year: 221=2021, 222=2022, 223=2023, 224=2024, 225=2025, 226=2026
- When grouping projects by year, use the CORRECT year based on the first 3 digits
- Example: Project 225126 is from 2025, NOT 2024
- Example: Project 224161 is from 2024, NOT 2023

Citation Rules:
8. Grounding: Provide concise answers based ONLY on the provided text. If you can't find it, state that directly and politely.
9. Sources MUST be embedded clickable links: Use markdown format to create clickable text without showing URLs.
10. Source Format: Document Name (Folder) with embedded [Open Link] that uses the SUITEFILES_URL

Format your response EXACTLY like this structure:

ANSWER:
[Start with a friendly acknowledgment like "That's a great question!" or "I can help with that!" Then give your direct, natural answer here - speak as if you're a helpful colleague sharing information. End with an encouraging closure like "Let me know if you need anything else!"]

SOURCES:
- Document Name (Folder) [Open Link](SUITEFILES_URL)
- Document Name (Folder) [Open Link](SUITEFILES_URL)

CRITICAL: The [Open Link](URL) creates an embedded clickable link. Users will see "Open Link" text but it will be clickable.

Example of a good conversational response:
"That's a great question! I looked into Aaron from TGCS but I don't have specific contact information in our system right now. However, I found several project records that might be relevant to your search. You might want to check with the project teams or HR for more details about external contractors. Let me know if you need anything else!"

Example of correct source format:
SOURCES:
- Safety Manual (Health and Safety) [Open Link](https://donthomson.sharepoint.com/sites/suitefiles/AppPages/documents.aspx#/HR/Safety_Manual.pdf)
- Project Guidelines (Templates) [Open Link](https://donthomson.sharepoint.com/sites/suitefiles/AppPages/documents.aspx#/Templates/Guidelines.docx)"""

            # Build conversation context separately to avoid f-string backslash issues
            conversation_section = ""
            if conversation_context:
                conversation_section = f"Previous Conversation:\n{conversation_context}\n"
            
            user_prompt = f"""Context from DTCE Knowledge Base:
{context}

{conversation_section}User Query: "{user_query}"

Please help answer this question using the information available in our knowledge base. Be conversational and helpful."""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Slightly creative for natural language, but mostly factual
                max_tokens=1500
            )
            
            full_response = response.choices[0].message.content
            
            # Parse structured response but preserve sources in the answer
            parsed_answer = self._extract_answer_with_sources(full_response)
            
            logger.info("Answer synthesized", 
                       query=user_query,
                       sources_used=len(search_results[:5]),
                       answer_length=len(parsed_answer))
            
            return parsed_answer
            
        except Exception as e:
            logger.error("Answer synthesis failed", error=str(e))
            return f"I encountered an error generating an answer: {str(e)}"
    
    def _extract_answer_with_sources(self, full_response: str) -> str:
        """
        Extract answer and sources from structured response, combining them for user display.
        
        Expected format:
        ANSWER:
        [answer text]
        
        SOURCES:
        [source list]
        
        Args:
            full_response: The complete structured response from GPT
            
        Returns:
            Combined answer with sources formatted for display
        """
        try:
            # Split on "ANSWER:" and "SOURCES:"
            if "ANSWER:" in full_response and "SOURCES:" in full_response:
                # Extract both sections
                parts = full_response.split("ANSWER:")[1].split("SOURCES:")
                answer_section = parts[0].strip()
                sources_section = parts[1].strip()
                
                # Combine with proper formatting
                if sources_section:
                    return f"{answer_section}\n\n**Sources:**\n{sources_section}"
                else:
                    return answer_section
                    
            elif "ANSWER:" in full_response:
                # Handle case where only ANSWER: is present
                answer_section = full_response.split("ANSWER:")[1].strip()
                return answer_section
            else:
                # Fallback - return the full response if format not followed
                logger.warning("Structured response format not followed, returning full response")
                return full_response.strip()
        except Exception as e:
            logger.error("Failed to parse structured response", error=str(e))
            return full_response.strip()

    def _extract_answer_from_structured_response(self, full_response: str) -> str:
        """
        Extract just the answer portion from the structured response format.
        
        Expected format:
        ANSWER:
        [answer text]
        
        SOURCES:
        [source list]
        
        Args:
            full_response: The complete structured response from GPT
            
        Returns:
            Just the answer portion, clean of source mentions
        """
        try:
            # Split on "ANSWER:" and "SOURCES:"
            if "ANSWER:" in full_response and "SOURCES:" in full_response:
                # Extract the answer section
                answer_section = full_response.split("ANSWER:")[1].split("SOURCES:")[0]
                return answer_section.strip()
            elif "ANSWER:" in full_response:
                # Handle case where only ANSWER: is present
                answer_section = full_response.split("ANSWER:")[1]
                return answer_section.strip()
            else:
                # Fallback - return the full response if format not followed
                logger.warning("Structured response format not followed, returning full response")
                return full_response.strip()
        except Exception as e:
            logger.error("Failed to parse structured response", error=str(e))
            return full_response.strip()
    
    def _format_source(self, result: Dict) -> Dict:
        """
        Format search result as a source reference for citations.
        
        Args:
            result: Raw search result dict
            
        Returns:
            Formatted source dict with title, excerpt, and metadata
        """
        content = result.get('content', '')
        excerpt = content[:200] + '...' if len(content) > 200 else content
        
        return {
            'title': result.get('filename', 'Unknown Document'),
            'folder': result.get('folder', ''),
            'project_name': result.get('project_name', ''),
            'relevance_score': result.get('reranker_score', result.get('search_score', 0)),
            'excerpt': excerpt
        }

    def _should_skip_file_in_results(self, filename: str, content: str) -> bool:
        """
        Determine if a file should be skipped from search results.
        
        Args:
            filename: Name of the file
            content: File content
            
        Returns:
            True if file should be skipped
        """
        # Skip placeholder and system files
        skip_files = [
            '.keep',
            '.gitkeep', 
            'Thumbs.db',
            '.DS_Store',
            'desktop.ini',
            '.directory'
        ]
        
        # Skip files with irrelevant extensions
        skip_extensions = [
            '.tmp', '.temp', '.log', '.cache',
            '.bak', '.backup', '.old',
            '.lock', '.pid'
        ]
        
        filename_lower = filename.lower()
        
        # Check exact filename matches
        if filename_lower in [f.lower() for f in skip_files]:
            return True
            
        # Check extension matches
        for ext in skip_extensions:
            if filename_lower.endswith(ext.lower()):
                return True
        
        # Skip if content is too short to be meaningful (likely placeholder)
        if len(content.strip()) < 50:
            return True
            
        return False


class RAGOrchestrator:
    """
    Main RAG orchestrator for managing conversation sessions and processing questions.
    """
    
    def __init__(self, search_client: SearchClient, openai_client: AsyncAzureOpenAI, model_name: str, max_retries: int = 3):
        """
        Initialize orchestrator with Azure clients.
        
        Args:
            search_client: Azure AI Search client
            openai_client: Azure OpenAI async client
            model_name: GPT model name
            max_retries: The maximum number of retries for OpenAI API calls.
        """
        self.rag_service = AzureRAGService(search_client, openai_client, model_name, max_retries)
        self.conversation_history = {}  # Store by session_id
        
    async def process_question(self, question: str, session_id: str = "default") -> Dict[str, Any]:
        """
        Main entry point for question processing using Azure RAG.
        
        Args:
            question: User's question
            session_id: Conversation session identifier
            
        Returns:
            Dict containing answer, sources, and metadata
        """
        try:
            # Get conversation history for this session
            history = self.conversation_history.get(session_id, [])
            
            # Process with RAG
            result = await self.rag_service.process_query(question, history)
            
            # Update conversation history
            self._update_conversation_history(session_id, question, result['answer'])
            
            return result
            
        except Exception as e:
            logger.error("RAG orchestrator failed", error=str(e), session_id=session_id)
            return {
                'answer': f"I encountered an error: {str(e)}",
                'sources': [],
                'intent': 'error',
                'search_filter': None,
                'total_documents': 0,
                'search_type': 'error'
            }
    
    def _update_conversation_history(self, session_id: str, question: str, answer: str):
        """
        Update conversation history for the session.
        
        Args:
            session_id: Conversation session identifier
            question: User's question
            answer: Assistant's answer
        """
        if session_id not in self.conversation_history:
            self.conversation_history[session_id] = []
        
        history = self.conversation_history[session_id]
        
        # Add user question and bot answer
        history.extend([
            {'role': 'user', 'content': question},
            {'role': 'assistant', 'content': answer}
        ])
        
        # Keep only recent history (last 10 turns = 20 messages)
        if len(history) > 20:
            self.conversation_history[session_id] = history[-20:]
