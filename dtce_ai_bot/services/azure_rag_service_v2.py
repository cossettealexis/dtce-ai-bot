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
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from openai import AsyncAzureOpenAI
from .intent_detector_ai import IntentDetector

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
    
    def __init__(self, search_client: SearchClient, openai_client: AsyncAzureOpenAI, model_name: str):
        """
        Initialize RAG service with Azure clients.
        
        Args:
            search_client: Azure AI Search client
            openai_client: Azure OpenAI async client
            model_name: GPT model name (e.g., "gpt-4o")
        """
        self.search_client = search_client
        self.openai_client = openai_client
        self.model_name = model_name
        self.embedding_model = "text-embedding-3-small"  # Azure OpenAI embedding deployment
        self.intent_detector = IntentDetector(openai_client, model_name)
        
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
            
            # STEP 2: Dynamic Filter Construction
            search_filter = self.intent_detector.build_search_filter(intent, user_query)
            
            logger.info("Intent-based routing configured", 
                       intent=intent,
                       filter=search_filter)
            
            # STEP 3: Hybrid Search + Semantic Ranking
            search_results = await self._hybrid_search_with_ranking(
                query=user_query,
                filter_str=search_filter,
                top_k=10
            )
            
            # STEP 4: Answer Synthesis
            answer = await self._synthesize_answer(
                user_query=user_query,
                search_results=search_results,
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
                "select": ["content", "filename", "folder", "project_name", "chunk_id"],  # Only retrieve needed fields
                "include_total_count": True
            }
            
            # Add filter if provided (intent-based routing)
            if filter_str:
                search_params["filter"] = filter_str
                logger.info("Applying search filter", filter=filter_str)
            
            # Execute hybrid search
            search_results = self.search_client.search(**search_params)
            
            # Process results
            results = []
            for result in search_results:
                content = result.get('content', '')
                
                # Log if content is minimal (placeholder documents)
                if not content or len(content) < 100:
                    logger.warning("Search result has minimal content", 
                                 filename=result.get('filename', 'Unknown'),
                                 content_length=len(content))
                
                results.append({
                    'content': content,
                    'filename': result.get('filename', 'Unknown Document'),
                    'folder': result.get('folder', ''),
                    'project_name': result.get('project_name', ''),
                    'chunk_id': result.get('chunk_id', ''),
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
                return "I couldn't find any relevant information in the DTCE knowledge base to answer your question."
            
            context_chunks = []
            for i, result in enumerate(search_results[:5], 1):  # Use top 5 results
                filename = result.get('filename', 'Unknown')
                folder = result.get('folder', '')
                content = result.get('content', '')
                
                chunk = f"[Source {i}: {filename} from {folder}]\n{content}"
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
            system_prompt = """You are an expert DTCE Assistant. Your primary function is to answer the user's question ONLY using the provided context from the company's knowledge base.

Rules:
1. Synthesize: Combine information from the retrieved document chunks into a single, cohesive, and easy-to-read answer.
2. Citations: At the end of the answer, provide a list of sources using the filename and folder metadata. Do not mention file names in the body of your answer.
3. Constraints: If the context is insufficient or contradictory, state: "I cannot provide a complete answer based on the available DTCE knowledge."
4. Tone: Maintain a professional and helpful tone. Be conversational but not robotic - answer like a knowledgeable colleague.
5. Accuracy: NEVER make up information. Only use what's in the provided context.
6. Clarity: Be specific with names, numbers, and details when they're in the documents."""

            user_prompt = f"""Context from DTCE Knowledge Base:
{context}

{f"Previous Conversation:\n{conversation_context}\n" if conversation_context else ""}
User Query: "{user_query}"

Please answer the user's question using ONLY the information from the provided context."""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Slightly creative for natural language, but mostly factual
                max_tokens=1500
            )
            
            answer = response.choices[0].message.content
            
            logger.info("Answer synthesized", 
                       query=user_query,
                       sources_used=len(search_results[:5]),
                       answer_length=len(answer))
            
            return answer
            
        except Exception as e:
            logger.error("Answer synthesis failed", error=str(e))
            return f"I encountered an error generating an answer: {str(e)}"
    
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


class RAGOrchestrator:
    """
    Main RAG orchestrator for managing conversation sessions and processing questions.
    """
    
    def __init__(self, search_client: SearchClient, openai_client: AsyncAzureOpenAI, model_name: str):
        """
        Initialize orchestrator with Azure clients.
        
        Args:
            search_client: Azure AI Search client
            openai_client: Azure OpenAI async client
            model_name: GPT model name
        """
        self.rag_service = AzureRAGService(search_client, openai_client, model_name)
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
