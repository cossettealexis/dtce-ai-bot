"""
Advanced RAG Handler with Comprehensive Retrieval-Augmented Generation
Implements advanced techniques for improved accuracy and multi-source retrieval
"""

import re
import asyncio
from typing import List, Dict, Any, Optional, Tuple, Union
import structlog
from azure.search.documents import SearchClient
from openai import AsyncAzureOpenAI
import json

logger = structlog.get_logger(__name__)


class QueryRewriter:
    """Advanced query rewriting for complex queries."""
    
    def __init__(self, openai_client: AsyncAzureOpenAI, model_name: str):
        self.openai_client = openai_client
        self.model_name = model_name
    
    async def decompose_complex_query(self, query: str) -> List[str]:
        """Break down complex queries into multiple specific sub-queries."""
        
        decomposition_prompt = f"""
        You are a query decomposition expert for a construction engineering document search system.
        
        Analyze this complex query and break it down into 2-4 specific, focused sub-queries that would help find comprehensive information.
        
        Original Query: "{query}"
        
        Guidelines:
        - Each sub-query should target a specific aspect of the original question
        - Make sub-queries specific enough to find precise information
        - Include technical terminology and project-specific keywords
        - Focus on actionable, searchable terms
        
        Return ONLY a JSON array of sub-queries, nothing else:
        ["sub-query 1", "sub-query 2", "sub-query 3"]
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a query decomposition expert. Return only valid JSON."},
                    {"role": "user", "content": decomposition_prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            result = response.choices[0].message.content.strip()
            
            # Parse JSON response
            if result.startswith('```json'):
                result = result.replace('```json', '').replace('```', '').strip()
            
            sub_queries = json.loads(result)
            
            # Validate that we got a list of strings
            if isinstance(sub_queries, list) and all(isinstance(q, str) for q in sub_queries):
                logger.info("Query decomposition successful", 
                           original_query=query, 
                           sub_queries=sub_queries)
                return sub_queries
            else:
                logger.warning("Invalid decomposition format, using original query")
                return [query]
                
        except Exception as e:
            logger.error("Query decomposition failed", error=str(e), query=query)
            return [query]


class SemanticChunker:
    """Advanced semantic-based chunking for better document processing."""
    
    def __init__(self, openai_client: AsyncAzureOpenAI, model_name: str):
        self.openai_client = openai_client
        self.model_name = model_name
        self.max_chunk_size = 1000
        self.overlap_size = 150
    
    async def create_semantic_chunks(self, content: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create semantically coherent chunks from document content."""
        
        # First, try to identify natural break points
        natural_chunks = self._identify_natural_breaks(content)
        
        # Then, ensure chunks are appropriately sized
        final_chunks = []
        for chunk_text in natural_chunks:
            if len(chunk_text) <= self.max_chunk_size:
                final_chunks.append({
                    'content': chunk_text,
                    'metadata': metadata,
                    'chunk_type': 'semantic_section'
                })
            else:
                # Split large semantic chunks into smaller ones with overlap
                sub_chunks = self._split_with_overlap(chunk_text)
                for i, sub_chunk in enumerate(sub_chunks):
                    final_chunks.append({
                        'content': sub_chunk,
                        'metadata': {**metadata, 'sub_chunk_index': i},
                        'chunk_type': 'semantic_sub_section'
                    })
        
        return final_chunks
    
    def _identify_natural_breaks(self, content: str) -> List[str]:
        """Identify natural break points in the document."""
        
        # Common section headers in engineering documents
        section_patterns = [
            r'^\d+\.\s+[A-Z][^.]*$',  # Numbered sections like "1. INTRODUCTION"
            r'^[A-Z\s]{3,}:?\s*$',     # ALL CAPS headings
            r'^Summary\s*$', r'^Conclusion\s*$', r'^Introduction\s*$',
            r'^Scope\s*$', r'^Method\s*$', r'^Results\s*$',
            r'^Recommendations\s*$', r'^Background\s*$'
        ]
        
        lines = content.split('\n')
        chunks = []
        current_chunk = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if this line is a section header
            is_header = any(re.match(pattern, line, re.IGNORECASE) for pattern in section_patterns)
            
            if is_header and current_chunk:
                # Save the current chunk and start a new one
                chunk_text = '\n'.join(current_chunk).strip()
                if chunk_text:
                    chunks.append(chunk_text)
                current_chunk = [line]
            else:
                current_chunk.append(line)
        
        # Add the final chunk
        if current_chunk:
            chunk_text = '\n'.join(current_chunk).strip()
            if chunk_text:
                chunks.append(chunk_text)
        
        return chunks if chunks else [content]
    
    def _split_with_overlap(self, text: str) -> List[str]:
        """Split large text with overlap to maintain context."""
        
        if len(text) <= self.max_chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.max_chunk_size
            
            if end >= len(text):
                chunks.append(text[start:])
                break
            
            # Try to break at sentence boundary
            sentence_end = text.rfind('.', start, end)
            if sentence_end > start + self.max_chunk_size // 2:
                end = sentence_end + 1
            
            chunks.append(text[start:end])
            start = end - self.overlap_size
        
        return chunks


class HybridSearcher:
    """Advanced hybrid search combining vector and keyword search with re-ranking."""
    
    def __init__(self, search_client: SearchClient, openai_client: AsyncAzureOpenAI, model_name: str):
        self.search_client = search_client
        self.openai_client = openai_client
        self.model_name = model_name
    
    async def hybrid_search(self, query: str, filters: Optional[List[str]] = None, 
                           top_k: int = 20) -> List[Dict[str, Any]]:
        """Perform hybrid search with vector and keyword search."""
        
        # Generate query embedding for vector search
        query_embedding = await self._generate_embedding(query)
        
        search_params = {
            'search_text': query,
            'vector_queries': [{
                'vector': query_embedding,
                'k_nearest_neighbors': top_k,
                'fields': 'content_vector'
            }] if query_embedding else [],
            'select': [
                'id', 'filename', 'content', 'blob_url', 
                'project_name', 'folder', 'file_type',
                'created_date', 'modified_date'
            ],
            'top': top_k,
            'query_type': 'semantic',
            'semantic_configuration_name': 'default'
        }
        
        # Add filters if provided
        if filters:
            search_params['filter'] = ' and '.join(filters)
        
        try:
            # Execute hybrid search
            results = []
            search_results = self.search_client.search(**search_params)
            
            for result in search_results:
                doc = {
                    'id': result.get('id', ''),
                    'filename': result.get('filename', ''),
                    'content': result.get('content', ''),
                    'blob_url': result.get('blob_url', ''),
                    'project_name': result.get('project_name', ''),
                    'folder': result.get('folder', ''),
                    'file_type': result.get('file_type', ''),
                    'search_score': getattr(result, '@search.score', 0),
                    'search_highlights': getattr(result, '@search.highlights', {}),
                    'created_date': result.get('created_date'),
                    'modified_date': result.get('modified_date')
                }
                results.append(doc)
            
            logger.info("Hybrid search completed", 
                       query=query, 
                       results_count=len(results))
            
            return results
            
        except Exception as e:
            logger.error("Hybrid search failed", error=str(e), query=query)
            return []
    
    async def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text using Azure OpenAI."""
        
        try:
            response = await self.openai_client.embeddings.create(
                model="text-embedding-ada-002",
                input=text
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error("Embedding generation failed", error=str(e))
            return None
    
    async def re_rank_results(self, query: str, results: List[Dict[str, Any]], 
                             top_k: int = 10) -> List[Dict[str, Any]]:
        """Re-rank search results using advanced semantic scoring."""
        
        if len(results) <= top_k:
            return results
        
        # Use LLM to score relevance of each result
        scored_results = []
        
        for result in results[:20]:  # Re-rank top 20 only for efficiency
            relevance_score = await self._calculate_relevance_score(query, result)
            result['relevance_score'] = relevance_score
            scored_results.append(result)
        
        # Sort by combined score (search score + relevance score)
        scored_results.sort(key=lambda x: (
            x.get('relevance_score', 0) * 0.7 + 
            x.get('search_score', 0) * 0.3
        ), reverse=True)
        
        return scored_results[:top_k]
    
    async def _calculate_relevance_score(self, query: str, result: Dict[str, Any]) -> float:
        """Calculate relevance score for a search result."""
        
        content_preview = result.get('content', '')[:500]  # First 500 chars
        
        scoring_prompt = f"""
        Rate the relevance of this document excerpt to the user's query on a scale of 0-10.
        
        Query: "{query}"
        
        Document: {result.get('filename', 'Unknown')}
        Content Preview: "{content_preview}"
        
        Consider:
        - How directly the content answers the query
        - Relevance of technical details
        - Document type appropriateness
        
        Return ONLY a number between 0 and 10, nothing else.
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a relevance scoring expert. Return only a number."},
                    {"role": "user", "content": scoring_prompt}
                ],
                temperature=0.1,
                max_tokens=10
            )
            
            score_text = response.choices[0].message.content.strip()
            score = float(re.findall(r'\d+(?:\.\d+)?', score_text)[0])
            return min(10.0, max(0.0, score))
            
        except Exception as e:
            logger.warning("Relevance scoring failed", error=str(e))
            return 5.0  # Default neutral score


class MultiSourceRetriever:
    """Retrieve information from multiple data sources."""
    
    def __init__(self, primary_search: HybridSearcher, 
                 secondary_sources: Optional[List[Any]] = None):
        self.primary_search = primary_search
        self.secondary_sources = secondary_sources or []
    
    async def multi_source_retrieve(self, query: str, sub_queries: List[str]) -> List[Dict[str, Any]]:
        """Retrieve from multiple sources and aggregate results."""
        
        all_results = []
        
        # Search primary source (Azure AI Search)
        for sub_query in sub_queries:
            results = await self.primary_search.hybrid_search(sub_query, top_k=15)
            for result in results:
                result['source'] = 'azure_search'
                result['sub_query'] = sub_query
                all_results.append(result)
        
        # TODO: Add secondary sources (other databases, APIs, etc.)
        # for source in self.secondary_sources:
        #     secondary_results = await source.search(query)
        #     all_results.extend(secondary_results)
        
        # Deduplicate and merge results
        unique_results = self._deduplicate_results(all_results)
        
        # Final re-ranking across all sources
        final_results = await self.primary_search.re_rank_results(query, unique_results)
        
        return final_results
    
    def _deduplicate_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate results based on content similarity."""
        
        seen_files = set()
        unique_results = []
        
        for result in results:
            file_id = f"{result.get('filename', '')}{result.get('project_name', '')}"
            
            if file_id not in seen_files:
                seen_files.add(file_id)
                unique_results.append(result)
        
        return unique_results


class AdvancedRAGHandler:
    """
    Advanced RAG Handler implementing comprehensive retrieval-augmented generation.
    
    Features:
    - Query decomposition for complex queries
    - Semantic chunking for better context
    - Hybrid search (vector + keyword + semantic ranking)
    - Multi-source retrieval
    - Advanced re-ranking
    - Improved prompt engineering
    """
    
    def __init__(self, search_client: SearchClient, openai_client: AsyncAzureOpenAI, 
                 model_name: str):
        self.search_client = search_client
        self.openai_client = openai_client
        self.model_name = model_name
        
        # Initialize advanced components
        self.query_rewriter = QueryRewriter(openai_client, model_name)
        self.semantic_chunker = SemanticChunker(openai_client, model_name)
        self.hybrid_searcher = HybridSearcher(search_client, openai_client, model_name)
        self.multi_source_retriever = MultiSourceRetriever(self.hybrid_searcher)
        
        logger.info("Advanced RAG Handler initialized with enhanced capabilities")
    
    async def process_question(self, question: str, 
                             context_history: Optional[List[Dict]] = None,
                             filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a question using advanced RAG techniques.
        
        Args:
            question: User's question
            context_history: Previous conversation context
            filters: Additional search filters
            
        Returns:
            Comprehensive response with enhanced accuracy
        """
        
        try:
            logger.info("Processing question with Advanced RAG", question=question)
            
            # Step 1: Query Enhancement and Decomposition
            if self._is_complex_query(question):
                sub_queries = await self.query_rewriter.decompose_complex_query(question)
                logger.info("Complex query decomposed", sub_queries=sub_queries)
            else:
                sub_queries = [question]
            
            # Step 2: Multi-Source Retrieval with Hybrid Search
            retrieved_documents = await self.multi_source_retriever.multi_source_retrieve(
                question, sub_queries
            )
            
            # Step 3: Context Preparation and Chunking
            processed_context = await self._prepare_enhanced_context(
                retrieved_documents, question
            )
            
            # Step 4: Advanced Prompt Engineering
            enhanced_prompt = await self._build_advanced_prompt(
                question, processed_context, context_history
            )
            
            # Step 5: Generate Response with Enhanced LLM Processing
            response = await self._generate_enhanced_response(enhanced_prompt, question)
            
            # Step 6: Post-processing and Quality Assurance
            final_response = await self._post_process_response(
                response, retrieved_documents, question
            )
            
            return {
                'answer': final_response,
                'sources': self._format_sources(retrieved_documents),
                'sub_queries_used': sub_queries,
                'total_sources': len(retrieved_documents),
                'confidence': self._calculate_confidence(retrieved_documents, final_response),
                'retrieval_method': 'advanced_rag'
            }
            
        except Exception as e:
            logger.error("Advanced RAG processing failed", error=str(e), question=question)
            return {
                'answer': "I apologize, but I encountered an error while processing your question. Please try rephrasing your question or contact support if the issue persists.",
                'sources': [],
                'error': str(e),
                'confidence': 'low'
            }
    
    def _is_complex_query(self, question: str) -> bool:
        """Determine if a query is complex and would benefit from decomposition."""
        
        complexity_indicators = [
            len(question.split()) > 15,  # Long queries
            ' and ' in question.lower() or ' or ' in question.lower(),  # Multiple conditions
            '?' in question[:-1],  # Multiple questions
            'compare' in question.lower() or 'difference' in question.lower(),
            'both' in question.lower() or 'either' in question.lower()
        ]
        
        return sum(complexity_indicators) >= 2
    
    async def _prepare_enhanced_context(self, documents: List[Dict[str, Any]], 
                                       question: str) -> str:
        """Prepare enhanced context from retrieved documents."""
        
        context_parts = []
        
        for i, doc in enumerate(documents[:10]):  # Use top 10 documents
            # Create semantic chunks for better context
            chunks = await self.semantic_chunker.create_semantic_chunks(
                doc.get('content', ''), 
                {
                    'filename': doc.get('filename'),
                    'project': doc.get('project_name'),
                    'source': doc.get('source', 'azure_search')
                }
            )
            
            # Select most relevant chunk
            best_chunk = self._select_most_relevant_chunk(chunks, question)
            
            if best_chunk:
                context_parts.append(
                    f"Source {i+1}: {doc.get('filename', 'Unknown Document')}\n"
                    f"Project: {doc.get('project_name', 'N/A')}\n"
                    f"Content: {best_chunk['content']}\n"
                    f"---"
                )
        
        return '\n\n'.join(context_parts)
    
    def _select_most_relevant_chunk(self, chunks: List[Dict[str, Any]], 
                                   question: str) -> Optional[Dict[str, Any]]:
        """Select the most relevant chunk for the question."""
        
        if not chunks:
            return None
        
        # Simple relevance scoring based on keyword overlap
        question_words = set(question.lower().split())
        
        best_chunk = None
        best_score = 0
        
        for chunk in chunks:
            chunk_words = set(chunk['content'].lower().split())
            overlap = len(question_words.intersection(chunk_words))
            score = overlap / len(question_words) if question_words else 0
            
            if score > best_score:
                best_score = score
                best_chunk = chunk
        
        return best_chunk or chunks[0]  # Return first chunk if no good match
    
    async def _build_advanced_prompt(self, question: str, context: str,
                                   history: Optional[List[Dict]] = None) -> str:
        """Build an advanced prompt with conversation history and enhanced instructions."""
        
        history_context = ""
        if history:
            recent_history = history[-3:]  # Last 3 exchanges
            history_parts = []
            for exchange in recent_history:
                if exchange.get('role') == 'user':
                    history_parts.append(f"Previous Question: {exchange.get('content', '')}")
                elif exchange.get('role') == 'assistant':
                    history_parts.append(f"Previous Answer: {exchange.get('content', '')[:200]}...")
            
            if history_parts:
                history_context = f"\n\nConversation History:\n{chr(10).join(history_parts)}\n"
        
        prompt = f"""You are DTCE AI Assistant, an expert construction engineering AI with access to comprehensive project documentation, NZ standards, and engineering best practices.

{history_context}

CURRENT QUESTION: {question}

RETRIEVED DOCUMENTATION:
{context}

RESPONSE GUIDELINES:

🔍 ACCURACY & VERIFICATION:
- Base answers ONLY on the provided documentation
- If information is not in the documents, clearly state "I don't have that information in the available documents"
- Quote specific document sections when possible
- Include document names and project references

🏗️ ENGINEERING CONTEXT:
- Provide technical details appropriate for construction engineers
- Reference relevant NZ Standards (NZS 3101, 3404, 1170, etc.) when applicable
- Include safety considerations and compliance requirements
- Explain engineering rationale behind recommendations

📊 STRUCTURED RESPONSES:
- Use clear headings and bullet points for complex information
- Prioritize most relevant information first
- Include specific values, tolerances, and requirements
- Provide actionable recommendations when appropriate

⚠️ PROFESSIONAL DISCLAIMERS:
- Add appropriate engineering disclaimers for critical decisions
- Recommend professional review for complex structural issues
- Clarify when additional site-specific analysis may be needed

📁 SOURCE ATTRIBUTION:
- Reference document names and project numbers
- Distinguish between different document types (reports, calculations, standards)
- Indicate document currency and version where available

Provide a comprehensive, accurate, and professionally structured response."""

        return prompt
    
    async def _generate_enhanced_response(self, prompt: str, question: str) -> str:
        """Generate response using enhanced LLM processing."""
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": question}
                ],
                temperature=0.2,  # Lower temperature for more consistent responses
                max_tokens=2000,
                top_p=0.95,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error("Enhanced response generation failed", error=str(e))
            raise
    
    async def _post_process_response(self, response: str, 
                                   documents: List[Dict[str, Any]], 
                                   question: str) -> str:
        """Post-process the response for quality and accuracy."""
        
        # Add source summary if not already included
        if documents and "Source" not in response and "Document" not in response:
            source_summary = self._create_source_summary(documents)
            response += f"\n\n📄 **Sources Referenced:**\n{source_summary}"
        
        # Add engineering disclaimer for safety-critical topics
        safety_keywords = ['structural', 'load', 'foundation', 'seismic', 'safety', 'collapse']
        if any(keyword in question.lower() for keyword in safety_keywords):
            if "disclaimer" not in response.lower():
                response += ("\n\n⚠️ **Engineering Note:** This information is for guidance only. "
                           "Always consult with a qualified structural engineer for specific design "
                           "decisions and ensure compliance with current NZ Building Code requirements.")
        
        return response
    
    def _create_source_summary(self, documents: List[Dict[str, Any]]) -> str:
        """Create a summary of source documents."""
        
        source_lines = []
        for i, doc in enumerate(documents[:5], 1):  # Top 5 sources
            filename = doc.get('filename', 'Unknown Document')
            project = doc.get('project_name', 'N/A')
            source_lines.append(f"{i}. {filename} (Project: {project})")
        
        return '\n'.join(source_lines)
    
    def _format_sources(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format source documents for response metadata."""
        
        formatted_sources = []
        for doc in documents[:10]:  # Return top 10 sources
            formatted_sources.append({
                'filename': doc.get('filename', ''),
                'project_name': doc.get('project_name', ''),
                'folder': doc.get('folder', ''),
                'relevance_score': doc.get('relevance_score', 0),
                'search_score': doc.get('search_score', 0),
                'url': doc.get('blob_url', ''),
                'sub_query': doc.get('sub_query', '')
            })
        
        return formatted_sources
    
    def _calculate_confidence(self, documents: List[Dict[str, Any]], 
                            response: str) -> str:
        """Calculate confidence level of the response."""
        
        if not documents:
            return 'low'
        
        # Factors affecting confidence
        factors = {
            'num_sources': len(documents),
            'avg_relevance': sum(doc.get('relevance_score', 0) for doc in documents) / len(documents),
            'response_length': len(response),
            'specific_references': response.count('Project') + response.count('Document')
        }
        
        # Simple scoring logic
        if factors['num_sources'] >= 5 and factors['avg_relevance'] >= 7:
            return 'high'
        elif factors['num_sources'] >= 3 and factors['avg_relevance'] >= 5:
            return 'medium'
        else:
            return 'low'
