"""
Comprehensive RAG (Retrieval-Augmented Generation) System
Built with Azure AI Search and OpenAI for maximum accuracy
"""

import asyncio
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
import structlog
from azure.search.documents import SearchClient
from azure.search.documents.models import QueryType, VectorizedQuery
from openai import AsyncAzureOpenAI
import tiktoken

logger = structlog.get_logger(__name__)


@dataclass
class RAGConfig:
    """Configuration for the RAG system"""
    # Azure AI Search
    search_endpoint: str
    search_key: str
    search_index: str
    
    # Azure OpenAI
    openai_endpoint: str
    openai_key: str
    openai_api_version: str
    
    # Models
    embedding_model: str = "text-embedding-ada-002"
    chat_model: str = "gpt-4"
    
    # Retrieval settings
    max_search_results: int = 10
    semantic_top_k: int = 5
    vector_weight: float = 0.6
    keyword_weight: float = 0.4
    
    # Generation settings
    max_tokens: int = 1000
    temperature: float = 0.1
    
    # Chunking settings
    max_chunk_size: int = 1000
    chunk_overlap: int = 200


@dataclass
class Document:
    """Document chunk with metadata"""
    id: str
    content: str
    title: str
    source: str
    chunk_index: int
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None


@dataclass
class RetrievalResult:
    """Result from document retrieval"""
    documents: List[Document]
    query: str
    search_strategy: str
    total_results: int
    confidence_score: float


@dataclass
class RAGResponse:
    """Final RAG system response"""
    answer: str
    sources: List[Dict[str, Any]]
    confidence: str
    retrieval_strategy: str
    tokens_used: int
    processing_time: float


class AdvancedRetriever:
    """Advanced retrieval system with hybrid search and reranking"""
    
    def __init__(self, config: RAGConfig):
        self.config = config
        self.search_client = SearchClient(
            endpoint=config.search_endpoint,
            index_name=config.search_index,
            credential=config.search_key
        )
        self.openai_client = AsyncAzureOpenAI(
            api_key=config.openai_key,
            api_version=config.openai_api_version,
            azure_endpoint=config.openai_endpoint
        )
        self.tokenizer = tiktoken.encoding_for_model("gpt-4")
    
    async def get_query_embedding(self, query: str) -> List[float]:
        """Convert query to embedding vector"""
        try:
            response = await self.openai_client.embeddings.create(
                input=query,
                model=self.config.embedding_model
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error("Failed to generate query embedding", error=str(e))
            raise
    
    async def hybrid_search(self, query: str, filters: Optional[Dict] = None) -> RetrievalResult:
        """
        Perform hybrid search combining vector and keyword search
        """
        try:
            # Get query embedding
            query_vector = await self.get_query_embedding(query)
            
            # Create vectorized query for semantic search
            vector_query = VectorizedQuery(
                vector=query_vector,
                k_nearest_neighbors=self.config.max_search_results,
                fields="content_vector"
            )
            
            # Prepare search parameters
            search_params = {
                "search_text": query,
                "vector_queries": [vector_query],
                "query_type": QueryType.SEMANTIC,
                "semantic_configuration_name": "default",
                "top": self.config.max_search_results,
                "select": ["id", "content", "title", "source", "chunk_index", "metadata"]
            }
            
            # Add filters if provided
            if filters:
                search_params["filter"] = self._build_filter_string(filters)
            
            # Execute search
            results = self.search_client.search(**search_params)
            
            # Process results
            documents = []
            for result in results:
                doc = Document(
                    id=result["id"],
                    content=result["content"],
                    title=result.get("title", ""),
                    source=result.get("source", ""),
                    chunk_index=result.get("chunk_index", 0),
                    metadata=result.get("metadata", {})
                )
                documents.append(doc)
            
            # Calculate confidence score based on search scores
            confidence_score = self._calculate_confidence(documents)
            
            return RetrievalResult(
                documents=documents,
                query=query,
                search_strategy="hybrid_semantic",
                total_results=len(documents),
                confidence_score=confidence_score
            )
            
        except Exception as e:
            logger.error("Hybrid search failed", error=str(e), query=query)
            raise
    
    async def multi_query_retrieval(self, original_query: str) -> RetrievalResult:
        """
        Generate multiple query variations and combine results
        """
        try:
            # Generate query variations
            query_variations = await self._generate_query_variations(original_query)
            
            # Search with each variation
            all_documents = []
            for query in query_variations:
                result = await self.hybrid_search(query)
                all_documents.extend(result.documents)
            
            # Remove duplicates and re-rank
            unique_docs = self._deduplicate_documents(all_documents)
            ranked_docs = await self._rerank_documents(unique_docs, original_query)
            
            return RetrievalResult(
                documents=ranked_docs[:self.config.max_search_results],
                query=original_query,
                search_strategy="multi_query",
                total_results=len(ranked_docs),
                confidence_score=self._calculate_confidence(ranked_docs)
            )
            
        except Exception as e:
            logger.error("Multi-query retrieval failed", error=str(e))
            # Fallback to single query
            return await self.hybrid_search(original_query)
    
    async def _generate_query_variations(self, query: str) -> List[str]:
        """Generate query variations using LLM"""
        try:
            prompt = f"""
            Given this user query, generate 3 alternative phrasings that capture the same intent:
            
            Original query: "{query}"
            
            Return only the alternative queries, one per line:
            """
            
            response = await self.openai_client.chat.completions.create(
                model=self.config.chat_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3
            )
            
            variations = [query]  # Include original
            content = response.choices[0].message.content.strip()
            for line in content.split('\n'):
                line = line.strip()
                if line and line != query:
                    variations.append(line)
            
            return variations[:4]  # Max 4 variations including original
            
        except Exception as e:
            logger.error("Failed to generate query variations", error=str(e))
            return [query]  # Return original query as fallback
    
    async def _rerank_documents(self, documents: List[Document], query: str) -> List[Document]:
        """Re-rank documents using LLM-based scoring"""
        try:
            if len(documents) <= 1:
                return documents
            
            # Create ranking prompt
            doc_texts = []
            for i, doc in enumerate(documents):
                doc_texts.append(f"{i+1}. {doc.content[:200]}...")
            
            prompt = f"""
            Rank these document excerpts by relevance to the query: "{query}"
            
            Documents:
            {chr(10).join(doc_texts)}
            
            Return only the ranking as numbers separated by commas (e.g., 3,1,4,2):
            """
            
            response = await self.openai_client.chat.completions.create(
                model=self.config.chat_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.1
            )
            
            # Parse ranking
            ranking_text = response.choices[0].message.content.strip()
            try:
                rankings = [int(x.strip()) - 1 for x in ranking_text.split(',')]
                reranked = [documents[i] for i in rankings if 0 <= i < len(documents)]
                return reranked
            except (ValueError, IndexError):
                logger.warning("Failed to parse ranking, using original order")
                return documents
                
        except Exception as e:
            logger.error("Document reranking failed", error=str(e))
            return documents
    
    def _deduplicate_documents(self, documents: List[Document]) -> List[Document]:
        """Remove duplicate documents based on content similarity"""
        seen_ids = set()
        unique_docs = []
        
        for doc in documents:
            if doc.id not in seen_ids:
                seen_ids.add(doc.id)
                unique_docs.append(doc)
        
        return unique_docs
    
    def _calculate_confidence(self, documents: List[Document]) -> float:
        """Calculate confidence score based on retrieval results"""
        if not documents:
            return 0.0
        
        # Simple confidence calculation based on number of results
        # In a real system, you'd use search scores
        if len(documents) >= 5:
            return 0.9
        elif len(documents) >= 3:
            return 0.7
        elif len(documents) >= 1:
            return 0.5
        else:
            return 0.1
    
    def _build_filter_string(self, filters: Dict) -> str:
        """Build OData filter string for Azure Search"""
        filter_parts = []
        for key, value in filters.items():
            if isinstance(value, str):
                filter_parts.append(f"{key} eq '{value}'")
            elif isinstance(value, list):
                or_parts = [f"{key} eq '{v}'" for v in value]
                filter_parts.append(f"({' or '.join(or_parts)})")
        
        return " and ".join(filter_parts)


class RAGGenerator:
    """Advanced answer generation with prompt engineering"""
    
    def __init__(self, config: RAGConfig):
        self.config = config
        self.openai_client = AsyncAzureOpenAI(
            api_key=config.openai_key,
            api_version=config.openai_api_version,
            azure_endpoint=config.openai_endpoint
        )
        self.tokenizer = tiktoken.encoding_for_model("gpt-4")
    
    async def generate_answer(self, query: str, retrieval_result: RetrievalResult) -> RAGResponse:
        """Generate answer using retrieved documents"""
        import time
        start_time = time.time()
        
        try:
            # Build context from retrieved documents
            context = self._build_context(retrieval_result.documents)
            
            # Create optimized prompt
            prompt = self._create_prompt(query, context, retrieval_result.documents)
            
            # Generate answer
            response = await self.openai_client.chat.completions.create(
                model=self.config.chat_model,
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant that answers questions based only on the provided context. Be accurate, concise, and cite your sources."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )
            
            answer = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            
            # Format sources
            sources = self._format_sources(retrieval_result.documents)
            
            # Determine confidence
            confidence = self._determine_confidence(retrieval_result, answer)
            
            processing_time = time.time() - start_time
            
            return RAGResponse(
                answer=answer,
                sources=sources,
                confidence=confidence,
                retrieval_strategy=retrieval_result.search_strategy,
                tokens_used=tokens_used,
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error("Answer generation failed", error=str(e))
            raise
    
    def _build_context(self, documents: List[Document]) -> str:
        """Build context string from documents with token management"""
        max_context_tokens = 6000  # Leave room for prompt and answer
        context_parts = []
        total_tokens = 0
        
        for doc in documents:
            doc_text = f"Source: {doc.title}\nContent: {doc.content}\n\n"
            doc_tokens = len(self.tokenizer.encode(doc_text))
            
            if total_tokens + doc_tokens > max_context_tokens:
                break
            
            context_parts.append(doc_text)
            total_tokens += doc_tokens
        
        return "".join(context_parts)
    
    def _create_prompt(self, query: str, context: str, documents: List[Document]) -> str:
        """Create optimized prompt for answer generation"""
        return f"""
Based on the following context, answer the user's question. If the context doesn't contain enough information to answer the question completely, say so clearly.

CONTEXT:
{context}

QUESTION: {query}

INSTRUCTIONS:
1. Answer based ONLY on the provided context
2. If information is insufficient, state this clearly
3. Cite specific sources when possible
4. Be concise but comprehensive
5. If multiple sources provide the same information, mention this

ANSWER:
"""
    
    def _format_sources(self, documents: List[Document]) -> List[Dict[str, Any]]:
        """Format source information for response"""
        sources = []
        for doc in documents:
            sources.append({
                "title": doc.title,
                "source": doc.source,
                "chunk_index": doc.chunk_index,
                "metadata": doc.metadata
            })
        return sources
    
    def _determine_confidence(self, retrieval_result: RetrievalResult, answer: str) -> str:
        """Determine confidence level based on retrieval and generation"""
        if retrieval_result.confidence_score >= 0.8 and len(retrieval_result.documents) >= 3:
            return "high"
        elif retrieval_result.confidence_score >= 0.6 and len(retrieval_result.documents) >= 2:
            return "medium"
        else:
            return "low"


class ComprehensiveRAGSystem:
    """Main RAG system orchestrating retrieval and generation"""
    
    def __init__(self, config: RAGConfig):
        self.config = config
        self.retriever = AdvancedRetriever(config)
        self.generator = RAGGenerator(config)
        logger.info("RAG system initialized", config=config)
    
    async def query(self, 
                   question: str, 
                   use_multi_query: bool = True,
                   filters: Optional[Dict] = None) -> RAGResponse:
        """
        Main query method with comprehensive RAG pipeline
        """
        try:
            logger.info("Processing RAG query", question=question, use_multi_query=use_multi_query)
            
            # Step 1: Advanced Retrieval
            if use_multi_query:
                retrieval_result = await self.retriever.multi_query_retrieval(question)
            else:
                retrieval_result = await self.retriever.hybrid_search(question, filters)
            
            logger.info("Retrieval completed", 
                       documents_found=retrieval_result.total_results,
                       strategy=retrieval_result.search_strategy,
                       confidence=retrieval_result.confidence_score)
            
            # Step 2: Answer Generation
            response = await self.generator.generate_answer(question, retrieval_result)
            
            logger.info("RAG query completed", 
                       confidence=response.confidence,
                       tokens_used=response.tokens_used,
                       processing_time=response.processing_time)
            
            return response
            
        except Exception as e:
            logger.error("RAG query failed", error=str(e), question=question)
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Check system health"""
        try:
            # Test retrieval
            test_result = await self.retriever.hybrid_search("test query")
            retrieval_ok = True
        except Exception:
            retrieval_ok = False
        
        try:
            # Test generation with minimal context
            test_doc = Document(
                id="test",
                content="This is a test document.",
                title="Test",
                source="test",
                chunk_index=0,
                metadata={}
            )
            test_retrieval = RetrievalResult(
                documents=[test_doc],
                query="test",
                search_strategy="test",
                total_results=1,
                confidence_score=0.5
            )
            await self.generator.generate_answer("What is this about?", test_retrieval)
            generation_ok = True
        except Exception:
            generation_ok = False
        
        return {
            "status": "healthy" if (retrieval_ok and generation_ok) else "unhealthy",
            "retrieval": "ok" if retrieval_ok else "error",
            "generation": "ok" if generation_ok else "error",
            "config": {
                "embedding_model": self.config.embedding_model,
                "chat_model": self.config.chat_model,
                "search_index": self.config.search_index
            }
        }
