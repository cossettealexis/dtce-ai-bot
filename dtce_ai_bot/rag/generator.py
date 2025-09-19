"""
Answer Generation Module

Generates contextual answers using retrieved documents.
"""

from typing import List, Dict, Any, Optional
import logging
from openai import AzureOpenAI

from .config import RAGConfig
from .retriever import SearchResult

logger = logging.getLogger(__name__)


class AnswerGenerator:
    """
    Generates answers using Azure OpenAI with retrieved context
    """
    
    def __init__(self, config: RAGConfig):
        self.config = config
        
        self.client = AzureOpenAI(
            api_key=config.azure.openai_api_key,
            api_version=config.azure.openai_api_version,
            azure_endpoint=config.azure.openai_endpoint
        )
        
        self.system_prompt = self._build_system_prompt()
    
    def generate_answer(self, question: str, search_results: List[SearchResult], 
                       conversation_history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        Generate answer based on question and retrieved context
        
        Args:
            question: User's question
            search_results: Retrieved documents/chunks
            conversation_history: Previous conversation turns
            
        Returns:
            Dictionary containing answer, sources, and metadata
        """
        if not search_results:
            return self._generate_fallback_answer(question)
        
        # Build context from search results
        context = self._build_context(search_results)
        
        # Build prompt
        prompt = self._build_prompt(question, context, conversation_history)
        
        # Generate answer
        try:
            response = self.client.chat.completions.create(
                model=self.config.models.chat_model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.config.response_max_tokens,
                temperature=self.config.models.temperature,
                top_p=self.config.models.top_p
            )
            
            answer = response.choices[0].message.content
            
            # Build response with metadata
            return self._build_response(answer, search_results, question)
            
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return self._generate_error_response(question, str(e))
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for the AI assistant"""
        return """You are a helpful AI assistant for DTCE (Design, Technology, Construction & Engineering) queries.

Your role is to:
1. Provide accurate, helpful answers based on the provided context
2. Focus on construction, engineering, and building standards
3. Cite specific sources when making claims
4. Acknowledge limitations when information is insufficient
5. Be concise but comprehensive

Guidelines:
- Use the provided context as your primary source of information
- If the context doesn't contain sufficient information, say so clearly
- Reference specific documents or standards when applicable
- Provide practical, actionable guidance when possible
- Use technical terminology appropriately but explain complex concepts
- If asked about regulations or standards, emphasize the importance of checking current versions

Do not:
- Make up information not supported by the context
- Provide advice that could be unsafe or non-compliant
- Claim certainty when the context is ambiguous
- Ignore relevant information from the provided context"""
    
    def _build_context(self, search_results: List[SearchResult]) -> str:
        """Build context string from search results"""
        if not search_results:
            return ""
        
        context_parts = []
        
        for i, result in enumerate(search_results[:10]):  # Limit context size
            # Add source information
            source_info = self._extract_source_info(result.metadata)
            
            context_part = f"[Source {i+1}] {source_info}\n{result.content}\n"
            context_parts.append(context_part)
        
        return "\n".join(context_parts)
    
    def _extract_source_info(self, metadata: Dict[str, Any]) -> str:
        """Extract source information from metadata"""
        source_parts = []
        
        # Document title/name
        if 'title' in metadata:
            source_parts.append(f"Title: {metadata['title']}")
        elif 'document_name' in metadata:
            source_parts.append(f"Document: {metadata['document_name']}")
        
        # Document type
        if 'document_type' in metadata:
            source_parts.append(f"Type: {metadata['document_type']}")
        
        # Standard/code reference
        if 'standard_code' in metadata:
            source_parts.append(f"Standard: {metadata['standard_code']}")
        
        # Section/page
        if 'section' in metadata:
            source_parts.append(f"Section: {metadata['section']}")
        elif 'page' in metadata:
            source_parts.append(f"Page: {metadata['page']}")
        
        return " | ".join(source_parts) if source_parts else "Unknown Source"
    
    def _build_prompt(self, question: str, context: str, 
                     conversation_history: Optional[List[Dict[str, str]]] = None) -> str:
        """Build the complete prompt for answer generation"""
        prompt_parts = []
        
        # Add conversation history if provided
        if conversation_history:
            prompt_parts.append("Previous conversation:")
            for turn in conversation_history[-3:]:  # Last 3 turns
                prompt_parts.append(f"Q: {turn.get('question', '')}")
                prompt_parts.append(f"A: {turn.get('answer', '')}")
            prompt_parts.append("")
        
        # Add context
        if context:
            prompt_parts.append("Context information:")
            prompt_parts.append(context)
            prompt_parts.append("")
        
        # Add current question
        prompt_parts.append("Question:")
        prompt_parts.append(question)
        prompt_parts.append("")
        
        # Add instructions
        if context:
            prompt_parts.append("Please provide a comprehensive answer based on the context above. Include relevant source references.")
        else:
            prompt_parts.append("Please provide the best answer you can. Note that no specific context was found for this query.")
        
        return "\n".join(prompt_parts)
    
    def _build_response(self, answer: str, search_results: List[SearchResult], 
                       question: str) -> Dict[str, Any]:
        """Build structured response with answer and metadata"""
        sources = []
        
        if self.config.include_sources:
            sources = self._extract_sources(search_results)
        
        return {
            "answer": answer,
            "sources": sources,
            "question": question,
            "confidence": self._calculate_confidence(search_results),
            "search_results_count": len(search_results),
            "model_used": self.config.models.chat_model
        }
    
    def _extract_sources(self, search_results: List[SearchResult]) -> List[Dict[str, Any]]:
        """Extract source information for citation"""
        sources = []
        seen_sources = set()
        
        for result in search_results[:5]:  # Top 5 sources
            metadata = result.metadata
            
            # Create source identifier
            source_id = metadata.get('document_id', '') + metadata.get('chunk_id', '')
            if source_id in seen_sources:
                continue
            seen_sources.add(source_id)
            
            source = {
                "content_preview": result.content[:200] + "..." if len(result.content) > 200 else result.content,
                "relevance_score": round(result.score, 3),
                "search_type": result.source
            }
            
            # Add available metadata
            for key in ['title', 'document_name', 'document_type', 'standard_code', 'section', 'page']:
                if key in metadata:
                    source[key] = metadata[key]
            
            sources.append(source)
        
        return sources
    
    def _calculate_confidence(self, search_results: List[SearchResult]) -> str:
        """Calculate confidence level based on search results"""
        if not search_results:
            return "low"
        
        avg_score = sum(r.score for r in search_results) / len(search_results)
        max_score = max(r.score for r in search_results) if search_results else 0
        
        if avg_score > 0.8 and max_score > 0.9:
            return "high"
        elif avg_score > 0.6 and max_score > 0.7:
            return "medium"
        else:
            return "low"
    
    def _generate_fallback_answer(self, question: str) -> Dict[str, Any]:
        """Generate answer when no context is available"""
        fallback_answer = """I couldn't find specific information in the knowledge base to answer your question comprehensively. 

For construction and engineering queries, I recommend:
1. Checking the latest building codes and standards
2. Consulting with qualified professionals
3. Reviewing official documentation from relevant authorities

If you can provide more specific details or rephrase your question, I might be able to help better."""
        
        return {
            "answer": fallback_answer,
            "sources": [],
            "question": question,
            "confidence": "low",
            "search_results_count": 0,
            "model_used": self.config.models.chat_model,
            "fallback": True
        }
    
    def _generate_error_response(self, question: str, error: str) -> Dict[str, Any]:
        """Generate response for error cases"""
        error_answer = "I encountered an error while processing your question. Please try again or rephrase your query."
        
        return {
            "answer": error_answer,
            "sources": [],
            "question": question,
            "confidence": "low",
            "search_results_count": 0,
            "error": error,
            "model_used": self.config.models.chat_model
        }
