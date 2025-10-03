"""
Azure RAG (Retrieval-Augmented Generation) Service
Implementation using Azure AI Search with hybrid search, semantic ranking, and document chunking
"""

import json
import structlog
from typing import List, Dict, Any, Optional, Tuple
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from openai import AsyncAzureOpenAI

logger = structlog.get_logger(__name__)


class AzureRAGService:
    """
    RAG implementation using Azure AI Search best practices:
    1. Hybrid Search (Vector + Keyword)
    2. Semantic Ranking
    3. Query Rewriting
    4. Context-aware Generation
    """
    
    def __init__(self, search_client: SearchClient, openai_client: AsyncAzureOpenAI, model_name: str):
        self.search_client = search_client
        self.openai_client = openai_client
        self.model_name = model_name
        self.embedding_model = "text-embedding-3-small"  # Use existing Azure deployment
        
    async def process_query(self, user_query: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """
        Main RAG pipeline:
        1. Query rewriting and decomposition
        2. Hybrid search with semantic ranking
        3. Context-aware generation
        """
        try:
            logger.info("Starting RAG pipeline", query=user_query)
            
            # Step 1: Query Enhancement and Rewriting
            enhanced_queries = await self._enhance_query(user_query, conversation_history)
            
            # Step 2: Hybrid Search for each query
            all_results = []
            for query in enhanced_queries:
                results = await self._hybrid_search(query)
                all_results.extend(results)
            
            # Step 3: Semantic Re-ranking
            ranked_results = await self._semantic_rerank(user_query, all_results)
            
            # Step 4: Context-aware Generation
            answer = await self._generate_answer(user_query, ranked_results, conversation_history)
            
            return {
                'answer': answer,
                'sources': [self._format_source(r) for r in ranked_results[:5]],
                'enhanced_queries': enhanced_queries,
                'total_documents_searched': len(all_results),
                'final_documents_used': len(ranked_results),
                'search_type': 'hybrid_rag'
            }
            
        except Exception as e:
            logger.error("RAG pipeline failed", error=str(e))
            return {
                'answer': f"I encountered an error processing your question: {str(e)}",
                'sources': [],
                'enhanced_queries': [user_query],
                'total_documents_searched': 0,
                'final_documents_used': 0,
                'search_type': 'error'
            }
    
    async def _enhance_query(self, user_query: str, conversation_history: List[Dict] = None) -> List[str]:
        """
        Query Enhancement and Decomposition:
        - Break complex queries into sub-queries
        - Add context from conversation history
        - Generate synonyms and related terms
        """
        try:
            context = ""
            if conversation_history:
                # Extract relevant context from conversation
                recent_turns = conversation_history[-3:]  # Last 3 turns
                context = "\n".join([f"{turn['role']}: {turn['content']}" for turn in recent_turns])
            
            enhancement_prompt = f"""You are a query enhancement expert. Your job is to take a user's question and create 1-3 optimized search queries that will find the most relevant information.

Original Question: "{user_query}"

Conversation Context:
{context}

Tasks:
1. If the question references previous conversation ("it", "that project", "the policy"), resolve these references using context
2. Break complex questions into focused sub-queries
3. Generate synonyms and alternative phrasings
4. Keep technical terms and specific codes/standards intact

Return 1-3 enhanced queries as JSON array:
["enhanced query 1", "enhanced query 2", "enhanced query 3"]

Example:
User: "What are the wind load requirements for that?"
Context shows previous discussion about NZS 3604
Enhanced: ["NZS 3604 wind load requirements", "wind load calculations timber framing", "structural wind load specifications"]"""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You enhance search queries for better document retrieval. Always return valid JSON array."},
                    {"role": "user", "content": enhancement_prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )
            
            try:
                response_content = response.choices[0].message.content
                if not response_content or response_content.strip() == "":
                    enhanced_queries = [user_query]
                else:
                    # Try to extract JSON from response if it has extra text
                    import re
                    json_match = re.search(r'\[.*\]', response_content, re.DOTALL)
                    if json_match:
                        json_text = json_match.group()
                        enhanced_queries = json.loads(json_text)
                    else:
                        # If no JSON array found, treat as single query
                        enhanced_queries = [response_content.strip().strip('"')]
                
                # Ensure we have valid queries
                if not enhanced_queries or not isinstance(enhanced_queries, list):
                    enhanced_queries = [user_query]
                
                # Clean up queries - remove empty strings
                enhanced_queries = [q for q in enhanced_queries if q and q.strip()]
                if not enhanced_queries:
                    enhanced_queries = [user_query]
                    
            except (json.JSONDecodeError, ValueError, AttributeError, IndexError):
                enhanced_queries = [user_query]
            
            logger.info("Query enhanced", original=user_query, enhanced=enhanced_queries)
            return enhanced_queries
            
        except Exception as e:
            logger.error("Query enhancement failed", error=str(e))
            return [user_query]  # Fallback to original
    
    async def _hybrid_search(self, query: str, top_k: int = 10) -> List[Dict]:
        """
        TRUE Hybrid Search: Keyword + Vector Search with semantic ranking
        """
        try:
            # Generate query embedding for vector search
            query_vector = await self._get_query_embedding(query)
            
            # Create vectorized query for semantic search
            vector_query = VectorizedQuery(
                vector=query_vector,
                k_nearest_neighbors=top_k,
                fields="content_vector"  # Make sure this matches your index field name
            )
            
            # Perform hybrid search: keyword + vector + semantic ranking
            search_results = self.search_client.search(
                search_text=query,  # Keyword search
                vector_queries=[vector_query],  # Vector search
                query_type="semantic",  # Enable semantic ranking
                semantic_configuration_name="default",  # Use default semantic config
                top=top_k,
                include_total_count=True
            )
            
            results = []
            for result in search_results:
                results.append({
                    'content': result.get('content', ''),
                    'title': result.get('title', ''),
                    'source': result.get('source', ''),
                    'chunk_id': result.get('chunk_id', ''),
                    'search_score': result.get('@search.score', 0),
                    'reranker_score': result.get('@search.reranker_score', 0),
                    'captions': result.get('@search.captions', []),
                    'answers': result.get('@search.answers', []),
                    'metadata': {
                        'document_type': result.get('document_type', ''),
                        'category': result.get('category', ''),
                        'project_id': result.get('project_id', ''),
                        'date_created': result.get('date_created', '')
                    }
                })
            
            logger.info("Hybrid search completed", query=query, results_count=len(results))
            return results
            
        except Exception as e:
            logger.error("Hybrid search failed", error=str(e), query=query)
            return []
    
    async def _get_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for the query using Azure OpenAI embedding model."""
        try:
            response = await self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=query
            )
            return response.data[0].embedding
            
        except Exception as e:
            logger.error("Embedding generation failed", error=str(e))
            return []
    
    async def _semantic_rerank(self, original_query: str, search_results: List[Dict], top_k: int = 10) -> List[Dict]:
        """
        Semantic re-ranking using a dedicated model to score relevance
        """
        try:
            if not search_results:
                return []
            
            # Remove duplicates based on content similarity
            unique_results = self._deduplicate_results(search_results)
            
            # Re-rank based on semantic relevance
            rerank_prompt = f"""You are a document relevance scorer. Score how well each document chunk answers the user's question.

User Question: "{original_query}"

Score each document from 0.0 to 1.0 based on:
- Direct relevance to the question
- Quality of information
- Completeness of answer

Documents to score:"""

            documents_to_score = []
            for i, result in enumerate(unique_results[:20]):  # Limit to top 20 for reranking
                doc_text = result['content'][:500]  # Truncate for efficiency
                documents_to_score.append(f"\nDocument {i+1}:\n{doc_text}")
            
            full_prompt = rerank_prompt + "".join(documents_to_score) + f"""

Return JSON array with scores:
[{{"doc_id": 1, "score": 0.95, "reason": "directly answers question"}}, ...]"""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are an expert at scoring document relevance. Always return valid JSON array."},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            try:
                response_content = response.choices[0].message.content
                if not response_content or response_content.strip() == "":
                    raise json.JSONDecodeError("Empty response", "", 0)
                
                # Try to extract JSON from response if it has extra text
                import re
                json_match = re.search(r'\[.*\]', response_content, re.DOTALL)
                if json_match:
                    json_text = json_match.group()
                else:
                    json_text = response_content.strip()
                
                scores = json.loads(json_text)
                
                # Validate the structure
                if not isinstance(scores, list) or not scores:
                    raise ValueError("Invalid scores structure")
                    
                # Ensure all scores have required fields
                for score in scores:
                    if not isinstance(score, dict) or 'doc_id' not in score or 'score' not in score:
                        raise ValueError("Invalid score item structure")
                        
            except (json.JSONDecodeError, ValueError, AttributeError, IndexError) as e:
                # Fallback to simple scoring if JSON parsing fails
                logger.warning("JSON parsing failed, using fallback scoring", error=str(e), response_preview=response.choices[0].message.content[:100] if response.choices else "No response")
                scores = [{"doc_id": i+1, "score": 0.5, "reason": "fallback"} for i in range(len(unique_results[:20]))]
            
            # Apply scores and sort
            scored_results = []
            for score_info in scores:
                doc_idx = score_info['doc_id'] - 1
                if 0 <= doc_idx < len(unique_results):
                    result = unique_results[doc_idx].copy()
                    result['relevance_score'] = score_info['score']
                    result['relevance_reason'] = score_info.get('reason', '')
                    scored_results.append(result)
            
            # Sort by relevance score
            scored_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
            
            logger.info("Semantic reranking completed", 
                       original_count=len(search_results),
                       reranked_count=len(scored_results))
            
            return scored_results[:top_k]
            
        except Exception as e:
            logger.error("Semantic reranking failed", error=str(e))
            # Fallback to original search scores
            return sorted(search_results, key=lambda x: x.get('reranker_score', x.get('search_score', 0)), reverse=True)[:top_k]
    
    def _deduplicate_results(self, results: List[Dict]) -> List[Dict]:
        """Remove duplicate results based on content similarity"""
        unique_results = []
        seen_content = set()
        
        for result in results:
            content = result.get('content', '')
            # Simple deduplication based on first 200 characters
            content_signature = content[:200].lower().strip()
            
            if content_signature not in seen_content:
                seen_content.add(content_signature)
                unique_results.append(result)
        
        return unique_results
    
    async def _generate_answer(self, user_query: str, ranked_results: List[Dict], 
                             conversation_history: List[Dict] = None) -> str:
        """
        Generate contextual answer using retrieved documents
        """
        try:
            # Build context from retrieved documents
            context_chunks = []
            sources_used = []
            
            for i, result in enumerate(ranked_results[:5]):  # Use top 5 results
                chunk = f"[Source {i+1}: {result.get('title', 'Unknown')}]\n{result.get('content', '')}"
                context_chunks.append(chunk)
                sources_used.append(result.get('source', 'Unknown'))
            
            context = "\n\n".join(context_chunks)
            
            # Add conversation history for context
            conversation_context = ""
            if conversation_history:
                recent_turns = conversation_history[-3:]
                conversation_context = "\n".join([f"{turn['role']}: {turn['content']}" for turn in recent_turns])
            
            # Generate answer with proper RAG prompt
            rag_prompt = f"""You are DTCE AI Assistant, an expert engineering AI that provides accurate answers based on retrieved documents.

User Question: "{user_query}"

Conversation History:
{conversation_context}

Retrieved Context:
{context}

Instructions:
1. Answer the question using ONLY the information provided in the retrieved context
2. If the context doesn't contain enough information, say so clearly
3. Quote specific sections when making technical claims
4. Include relevant document sources in your answer
5. If you need to make assumptions, state them clearly
6. For engineering questions, be precise with numbers, codes, and specifications

Provide a clear, accurate, and helpful answer:"""

            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are an expert engineering assistant that provides accurate answers based on retrieved documents. Never make up information not in the context."},
                    {"role": "user", "content": rag_prompt}
                ],
                temperature=0.1,  # Low temperature for factual accuracy
                max_tokens=1500
            )
            
            answer = response.choices[0].message.content
            
            logger.info("Answer generated", 
                       query=user_query,
                       sources_count=len(sources_used),
                       answer_length=len(answer))
            
            return answer
            
        except Exception as e:
            logger.error("Answer generation failed", error=str(e))
            return f"I encountered an error generating an answer: {str(e)}"
    
    def _format_source(self, result: Dict) -> Dict:
        """Format search result as a source reference"""
        return {
            'title': result.get('title', 'Unknown Document'),
            'source': result.get('source', 'Unknown Source'),
            'relevance_score': result.get('relevance_score', result.get('reranker_score', 0)),
            'excerpt': result.get('content', '')[:200] + '...' if len(result.get('content', '')) > 200 else result.get('content', ''),
            'metadata': result.get('metadata', {})
        }


class RAGOrchestrator:
    """
    Main RAG orchestrator for processing questions with Azure AI Search
    """
    
    def __init__(self, search_client: SearchClient, openai_client: AsyncAzureOpenAI, model_name: str):
        self.rag_service = AzureRAGService(search_client, openai_client, model_name)
        self.conversation_history = {}  # Store by session_id
        
    async def process_question(self, question: str, session_id: str = "default") -> Dict[str, Any]:
        """
        Main entry point for question processing using Azure RAG
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
            logger.error("RAG orchestrator failed", error=str(e))
            return {
                'answer': f"I encountered an error: {str(e)}",
                'sources': [],
                'enhanced_queries': [question],
                'total_documents_searched': 0,
                'final_documents_used': 0,
                'search_type': 'error'
            }
    
    def _update_conversation_history(self, session_id: str, question: str, answer: str):
        """Update conversation history for the session"""
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
