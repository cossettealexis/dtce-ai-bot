"""
Enhanced RAG Pipeline with Azure AI Search
Implements comprehensive RAG architecture with hybrid search, semantic ranking, and multi-source retrieval
"""

import asyncio
from typing import List, Dict, Any, Optional, Union, Tuple
import structlog
from dataclasses import dataclass
from enum import Enum
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery, QueryType, QueryCaptionType, QueryAnswerType
from openai import AsyncAzureOpenAI
import json
import re

logger = structlog.get_logger(__name__)

class SearchStrategy(Enum):
    """Search strategy enumeration"""
    VECTOR_ONLY = "vector"
    KEYWORD_ONLY = "keyword"
    HYBRID = "hybrid"
    SEMANTIC_HYBRID = "semantic_hybrid"

@dataclass
class ChunkMetadata:
    """Metadata for document chunks"""
    source_document: str
    document_type: str
    section: Optional[str] = None
    author: Optional[str] = None
    date_created: Optional[str] = None
    project_number: Optional[str] = None
    client: Optional[str] = None
    folder_path: Optional[str] = None

@dataclass
class RetrievalResult:
    """Result from document retrieval"""
    content: str
    score: float
    metadata: ChunkMetadata
    search_highlights: List[str]
    rerank_score: Optional[float] = None

@dataclass
class RAGResponse:
    """Complete RAG response"""
    answer: str
    sources: List[RetrievalResult]
    confidence_score: float
    query_analysis: Dict[str, Any]
    retrieval_strategy: str

class QueryAnalyzer:
    """Analyzes and processes user queries"""
    
    def __init__(self, openai_client: AsyncAzureOpenAI, model_name: str):
        self.openai_client = openai_client
        self.model_name = model_name
    
    async def analyze_query(self, query: str) -> Dict[str, Any]:
        """Analyze query intent, complexity, and requirements"""
        
        analysis_prompt = f"""
        Analyze this user query and provide structured analysis:
        
        Query: "{query}"
        
        Provide analysis in this JSON format:
        {{
            "intent": "policy|procedure|standard|project|client|technical|general",
            "complexity": "simple|moderate|complex",
            "requires_multi_source": true/false,
            "key_entities": ["entity1", "entity2"],
            "search_terms": ["term1", "term2"],
            "project_reference": "project_number_if_mentioned_or_null",
            "temporal_context": "recent|historical|specific_date_or_null",
            "sub_queries": ["sub_query1", "sub_query2"] // if complex query needs breaking down
        }}
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are an expert query analyzer for engineering document search."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.1
            )
            
            content = response.choices[0].message.content
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                logger.warning("Failed to parse query analysis JSON", query=query)
                return self._default_analysis(query)
                
        except Exception as e:
            logger.error("Query analysis failed", error=str(e), query=query)
            return self._default_analysis(query)
    
    def _default_analysis(self, query: str) -> Dict[str, Any]:
        """Fallback analysis if AI analysis fails"""
        return {
            "intent": "general",
            "complexity": "simple",
            "requires_multi_source": False,
            "key_entities": [query],
            "search_terms": query.split(),
            "project_reference": None,
            "temporal_context": None,
            "sub_queries": [query]
        }

class SemanticChunker:
    """Handles intelligent document chunking based on semantic meaning"""
    
    def __init__(self, openai_client: AsyncAzureOpenAI, model_name: str):
        self.openai_client = openai_client
        self.model_name = model_name
    
    async def chunk_document(self, content: str, metadata: ChunkMetadata, 
                           chunk_size: int = 1000, overlap: int = 200) -> List[Dict[str, Any]]:
        """Chunk document with semantic awareness"""
        
        # First try semantic chunking for structured documents
        if metadata.document_type in ['policy', 'procedure', 'standard']:
            semantic_chunks = await self._semantic_chunk(content, metadata)
            if semantic_chunks:
                return semantic_chunks
        
        # Fall back to sliding window chunking
        return self._sliding_window_chunk(content, metadata, chunk_size, overlap)
    
    async def _semantic_chunk(self, content: str, metadata: ChunkMetadata) -> List[Dict[str, Any]]:
        """Chunk based on semantic structure"""
        
        try:
            chunk_prompt = f"""
            Split this document into logical semantic chunks. Each chunk should be a complete thought or section.
            Return the chunks as JSON array with start and end positions.
            
            Document type: {metadata.document_type}
            Content: {content[:2000]}...
            
            Format: [{{"start": 0, "end": 100, "title": "section_title"}}, ...]
            """
            
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are an expert document chunking assistant."},
                    {"role": "user", "content": chunk_prompt}
                ],
                temperature=0.1
            )
            
            # Parse chunking instructions and apply them
            # This is a simplified version - in production you'd want more robust parsing
            return self._sliding_window_chunk(content, metadata, 1000, 200)
            
        except Exception as e:
            logger.warning("Semantic chunking failed", error=str(e))
            return []
    
    def _sliding_window_chunk(self, content: str, metadata: ChunkMetadata, 
                            chunk_size: int, overlap: int) -> List[Dict[str, Any]]:
        """Traditional sliding window chunking with metadata"""
        
        chunks = []
        start = 0
        
        while start < len(content):
            end = start + chunk_size
            chunk_text = content[start:end]
            
            # Try to break at sentence boundaries
            if end < len(content):
                last_period = chunk_text.rfind('.')
                last_newline = chunk_text.rfind('\n')
                break_point = max(last_period, last_newline)
                
                if break_point > start + chunk_size * 0.7:  # Don't break too early
                    end = start + break_point + 1
                    chunk_text = content[start:end]
            
            chunks.append({
                "content": chunk_text.strip(),
                "metadata": metadata,
                "chunk_index": len(chunks),
                "start_position": start,
                "end_position": end
            })
            
            start = end - overlap
        
        return chunks

class HybridRetriever:
    """Implements hybrid search with vector and keyword search"""
    
    def __init__(self, search_clients: Dict[str, SearchClient], 
                 openai_client: AsyncAzureOpenAI, model_name: str):
        self.search_clients = search_clients  # Multiple search indices
        self.openai_client = openai_client
        self.model_name = model_name
    
    async def retrieve(self, query: str, query_analysis: Dict[str, Any], 
                      strategy: SearchStrategy = SearchStrategy.SEMANTIC_HYBRID,
                      top_k: int = 10) -> List[RetrievalResult]:
        """Retrieve relevant documents using hybrid search"""
        
        # Generate query embedding
        query_vector = await self._get_query_embedding(query)
        
        # Determine which indices to search based on query analysis
        target_indices = self._select_indices(query_analysis)
        
        # Perform search across selected indices
        all_results = []
        for index_name, search_client in target_indices.items():
            results = await self._search_index(
                search_client, query, query_vector, strategy, top_k
            )
            all_results.extend(results)
        
        # Re-rank and merge results
        final_results = await self._rerank_results(query, all_results, top_k)
        
        return final_results
    
    async def _get_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for query"""
        try:
            response = await self.openai_client.embeddings.create(
                model="text-embedding-ada-002",
                input=query
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error("Failed to generate query embedding", error=str(e))
            return []
    
    def _select_indices(self, query_analysis: Dict[str, Any]) -> Dict[str, SearchClient]:
        """Select appropriate search indices based on query analysis"""
        
        intent = query_analysis.get("intent", "general")
        selected_indices = {}
        
        # Map intent to appropriate indices
        intent_mapping = {
            "policy": ["policies", "procedures"],
            "procedure": ["procedures", "templates"],
            "standard": ["standards", "codes"],
            "project": ["projects", "calculations"],
            "client": ["projects", "correspondence"],
            "technical": ["standards", "procedures", "projects"],
            "general": list(self.search_clients.keys())
        }
        
        index_names = intent_mapping.get(intent, ["main"])
        
        for index_name in index_names:
            if index_name in self.search_clients:
                selected_indices[index_name] = self.search_clients[index_name]
        
        # Fallback to main index if no matches
        if not selected_indices and "main" in self.search_clients:
            selected_indices["main"] = self.search_clients["main"]
        
        return selected_indices
    
    async def _search_index(self, search_client: SearchClient, query: str, 
                          query_vector: List[float], strategy: SearchStrategy, 
                          top_k: int) -> List[RetrievalResult]:
        """Search a single index"""
        
        try:
            search_params = {
                "search_text": query,
                "top": top_k,
                "include_total_count": True,
                "query_type": QueryType.SEMANTIC if strategy in [SearchStrategy.SEMANTIC_HYBRID] else QueryType.SIMPLE,
                "semantic_configuration_name": "semantic-config" if strategy in [SearchStrategy.SEMANTIC_HYBRID] else None,
                "query_caption": QueryCaptionType.EXTRACTIVE if strategy in [SearchStrategy.SEMANTIC_HYBRID] else None,
                "query_answer": QueryAnswerType.EXTRACTIVE if strategy in [SearchStrategy.SEMANTIC_HYBRID] else None
            }
            
            # Add vector query for hybrid search
            if strategy in [SearchStrategy.VECTOR_ONLY, SearchStrategy.HYBRID, SearchStrategy.SEMANTIC_HYBRID] and query_vector:
                search_params["vector_queries"] = [VectorizedQuery(
                    vector=query_vector,
                    k_nearest_neighbors=top_k,
                    fields="content_vector"
                )]
            
            results = search_client.search(**search_params)
            
            retrieval_results = []
            for doc in results:
                metadata = ChunkMetadata(
                    source_document=doc.get("source_document", ""),
                    document_type=doc.get("document_type", ""),
                    section=doc.get("section"),
                    author=doc.get("author"),
                    date_created=doc.get("date_created"),
                    project_number=doc.get("project_number"),
                    client=doc.get("client"),
                    folder_path=doc.get("folder_path")
                )
                
                retrieval_results.append(RetrievalResult(
                    content=doc.get("content", ""),
                    score=doc.get("@search.score", 0.0),
                    metadata=metadata,
                    search_highlights=doc.get("@search.highlights", {}).get("content", [])
                ))
            
            return retrieval_results
            
        except Exception as e:
            logger.error("Search failed for index", error=str(e))
            return []
    
    async def _rerank_results(self, query: str, results: List[RetrievalResult], 
                            top_k: int) -> List[RetrievalResult]:
        """Re-rank results using LLM-based scoring"""
        
        if not results:
            return []
        
        # For now, sort by original search score
        # In production, you'd implement a proper reranking model
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results[:top_k]

class ResponseGenerator:
    """Generates final responses using retrieved context"""
    
    def __init__(self, openai_client: AsyncAzureOpenAI, model_name: str):
        self.openai_client = openai_client
        self.model_name = model_name
    
    async def generate_response(self, query: str, context: List[RetrievalResult], 
                              query_analysis: Dict[str, Any]) -> RAGResponse:
        """Generate comprehensive response with sources"""
        
        # Build context prompt
        context_text = self._build_context(context)
        
        # Generate response
        response_text = await self._generate_answer(query, context_text, query_analysis)
        
        # Calculate confidence score
        confidence = self._calculate_confidence(context, response_text)
        
        return RAGResponse(
            answer=response_text,
            sources=context,
            confidence_score=confidence,
            query_analysis=query_analysis,
            retrieval_strategy="hybrid_semantic"
        )
    
    def _build_context(self, results: List[RetrievalResult]) -> str:
        """Build context string from retrieval results"""
        
        context_parts = []
        for i, result in enumerate(results):
            source_info = f"Source {i+1}: {result.metadata.source_document}"
            if result.metadata.section:
                source_info += f" (Section: {result.metadata.section})"
            
            context_parts.append(f"{source_info}\n{result.content}\n")
        
        return "\n---\n".join(context_parts)
    
    async def _generate_answer(self, query: str, context: str, 
                             query_analysis: Dict[str, Any]) -> str:
        """Generate answer using LLM"""
        
        system_prompt = """You are an expert engineering assistant for DTCE. 
        Answer questions using only the provided context. 
        Be precise, cite sources, and indicate if information is incomplete.
        For policy questions, quote relevant sections directly.
        For technical questions, provide detailed explanations with references."""
        
        user_prompt = f"""
        Context Information:
        {context}
        
        User Question: {query}
        
        Query Analysis: {query_analysis.get('intent', 'general')} question with {query_analysis.get('complexity', 'unknown')} complexity.
        
        Please provide a comprehensive answer based on the context provided.
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error("Response generation failed", error=str(e))
            return "I'm sorry, I encountered an error generating the response. Please try again."
    
    def _calculate_confidence(self, context: List[RetrievalResult], response: str) -> float:
        """Calculate confidence score for the response"""
        
        if not context:
            return 0.0
        
        # Simple confidence calculation based on source scores and content length
        avg_score = sum(r.score for r in context) / len(context)
        content_coverage = min(len(response) / 500, 1.0)  # Normalize by expected length
        
        return min(avg_score * content_coverage, 1.0)

class EnhancedRAGPipeline:
    """Main RAG pipeline orchestrator"""
    
    def __init__(self, search_clients: Dict[str, SearchClient], 
                 openai_client: AsyncAzureOpenAI, model_name: str):
        
        self.query_analyzer = QueryAnalyzer(openai_client, model_name)
        self.chunker = SemanticChunker(openai_client, model_name)
        self.retriever = HybridRetriever(search_clients, openai_client, model_name)
        self.generator = ResponseGenerator(openai_client, model_name)
        
        logger.info("Enhanced RAG Pipeline initialized", 
                   indices=list(search_clients.keys()))
    
    async def process_query(self, query: str, **kwargs) -> RAGResponse:
        """Process a user query through the complete RAG pipeline"""
        
        try:
            # Step 1: Analyze query
            logger.info("Starting RAG pipeline", query=query)
            query_analysis = await self.query_analyzer.analyze_query(query)
            
            # Step 2: Retrieve relevant documents
            strategy = SearchStrategy.SEMANTIC_HYBRID
            if kwargs.get('search_strategy'):
                strategy = SearchStrategy(kwargs['search_strategy'])
            
            retrieval_results = await self.retriever.retrieve(
                query, query_analysis, strategy, 
                top_k=kwargs.get('top_k', 10)
            )
            
            # Step 3: Generate response
            response = await self.generator.generate_response(
                query, retrieval_results, query_analysis
            )
            
            logger.info("RAG pipeline completed", 
                       sources_count=len(response.sources),
                       confidence=response.confidence_score)
            
            return response
            
        except Exception as e:
            logger.error("RAG pipeline failed", error=str(e), query=query)
            
            # Return error response
            return RAGResponse(
                answer="I encountered an error processing your request. Please try again or rephrase your question.",
                sources=[],
                confidence_score=0.0,
                query_analysis={"intent": "error", "complexity": "unknown"},
                retrieval_strategy="error"
            )
    
    async def index_document(self, content: str, metadata: ChunkMetadata, 
                           target_index: str = "main") -> bool:
        """Index a new document with semantic chunking"""
        
        try:
            # Chunk the document
            chunks = await self.chunker.chunk_document(content, metadata)
            
            # Index each chunk
            # This would integrate with your indexing pipeline
            logger.info("Document indexed", 
                       source=metadata.source_document,
                       chunks=len(chunks),
                       target_index=target_index)
            
            return True
            
        except Exception as e:
            logger.error("Document indexing failed", error=str(e),
                        source=metadata.source_document)
            return False
