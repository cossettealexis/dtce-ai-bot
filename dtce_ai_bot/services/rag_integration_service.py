"""
RAG Integration Layer
Integrates the Enhanced RAG Pipeline with existing DTCE AI Bot infrastructure
"""

from typing import Dict, Any, List, Optional
import structlog
from azure.search.documents import SearchClient
from openai import AsyncAzureOpenAI

from .enhanced_rag_pipeline import (
    EnhancedRAGPipeline, 
    ChunkMetadata, 
    RAGResponse,
    SearchStrategy
)
from ..config.settings import Settings

logger = structlog.get_logger(__name__)

class RAGIntegrationService:
    """Service to integrate Enhanced RAG Pipeline with existing bot architecture"""
    
    def __init__(self, search_client: SearchClient, openai_client: AsyncAzureOpenAI, 
                 model_name: str, settings: Settings):
        
        self.settings = settings
        
        # Initialize multiple search clients for different document types
        self.search_clients = {
            "main": search_client,  # Main index for general documents
            # Add additional indices as needed
            # "policies": policy_search_client,
            # "procedures": procedure_search_client,
            # "standards": standards_search_client,
            # "projects": projects_search_client
        }
        
        # Initialize enhanced RAG pipeline
        self.rag_pipeline = EnhancedRAGPipeline(
            self.search_clients, 
            openai_client, 
            model_name
        )
        
        logger.info("RAG Integration Service initialized")
    
    async def process_query(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a query through the enhanced RAG pipeline
        
        Args:
            query: User query string
            context: Optional context including conversation history, user info, etc.
            
        Returns:
            Formatted response dictionary compatible with existing bot interface
        """
        
        try:
            # Process through enhanced RAG pipeline
            rag_response = await self.rag_pipeline.process_query(
                query,
                search_strategy="semantic_hybrid",
                top_k=10
            )
            
            # Format response for bot interface
            formatted_response = self._format_response(rag_response, query)
            
            return formatted_response
            
        except Exception as e:
            logger.error("RAG integration query processing failed", 
                        error=str(e), query=query)
            
            return self._error_response("I encountered an error processing your request.")
    
    def _format_response(self, rag_response: RAGResponse, original_query: str) -> Dict[str, Any]:
        """Format RAG response for bot interface compatibility"""
        
        # Format sources for display
        formatted_sources = []
        for source in rag_response.sources[:5]:  # Limit to top 5 sources
            formatted_source = {
                "title": source.metadata.source_document,
                "content_preview": source.content[:200] + "..." if len(source.content) > 200 else source.content,
                "score": round(source.score, 3),
                "metadata": {
                    "document_type": source.metadata.document_type,
                    "section": source.metadata.section,
                    "project_number": source.metadata.project_number,
                    "folder_path": source.metadata.folder_path
                }
            }
            
            # Add highlights if available
            if source.search_highlights:
                formatted_source["highlights"] = source.search_highlights[:3]
            
            formatted_sources.append(formatted_source)
        
        # Determine response type based on query analysis
        intent = rag_response.query_analysis.get("intent", "general")
        response_type = self._map_intent_to_type(intent)
        
        return {
            "response": rag_response.answer,
            "response_type": response_type,
            "confidence": rag_response.confidence_score,
            "sources": formatted_sources,
            "query_analysis": {
                "intent": intent,
                "complexity": rag_response.query_analysis.get("complexity", "unknown"),
                "entities": rag_response.query_analysis.get("key_entities", [])
            },
            "retrieval_info": {
                "strategy": rag_response.retrieval_strategy,
                "sources_found": len(rag_response.sources),
                "search_quality": "high" if rag_response.confidence_score > 0.7 else "medium" if rag_response.confidence_score > 0.4 else "low"
            },
            "follow_up_suggestions": self._generate_follow_up_suggestions(rag_response, original_query)
        }
    
    def _map_intent_to_type(self, intent: str) -> str:
        """Map query intent to response type"""
        mapping = {
            "policy": "policy_response",
            "procedure": "procedure_response", 
            "standard": "standard_response",
            "project": "project_response",
            "client": "client_response",
            "technical": "technical_response",
            "general": "general_response"
        }
        return mapping.get(intent, "general_response")
    
    def _generate_follow_up_suggestions(self, rag_response: RAGResponse, 
                                      original_query: str) -> List[str]:
        """Generate contextual follow-up suggestions"""
        
        suggestions = []
        intent = rag_response.query_analysis.get("intent", "general")
        
        # Intent-specific suggestions
        if intent == "policy":
            suggestions.extend([
                "Would you like me to explain any specific section in more detail?",
                "Do you need information about related procedures?",
                "Are there compliance requirements you'd like to know about?"
            ])
        elif intent == "project":
            suggestions.extend([
                "Would you like to see related project documentation?",
                "Do you need contact information for this project?",
                "Are there similar projects you'd like me to find?"
            ])
        elif intent == "technical":
            suggestions.extend([
                "Would you like me to find relevant NZ standards?",
                "Do you need calculation examples or templates?",
                "Are there related technical procedures?"
            ])
        
        # Add project-specific suggestions if project mentioned
        if rag_response.query_analysis.get("project_reference"):
            suggestions.append("Would you like to see other documents from this project?")
        
        return suggestions[:3]  # Limit to 3 suggestions
    
    def _error_response(self, message: str) -> Dict[str, Any]:
        """Generate error response in expected format"""
        return {
            "response": message,
            "response_type": "error_response",
            "confidence": 0.0,
            "sources": [],
            "query_analysis": {"intent": "error", "complexity": "unknown", "entities": []},
            "retrieval_info": {"strategy": "none", "sources_found": 0, "search_quality": "none"},
            "follow_up_suggestions": [
                "Please try rephrasing your question",
                "You can ask about policies, procedures, or project information",
                "Try being more specific about what you're looking for"
            ]
        }
    
    async def add_search_index(self, index_name: str, search_client: SearchClient):
        """Add additional search index to the system"""
        self.search_clients[index_name] = search_client
        
        # Reinitialize RAG pipeline with updated indices
        self.rag_pipeline = EnhancedRAGPipeline(
            self.search_clients, 
            self.rag_pipeline.generator.openai_client,
            self.rag_pipeline.generator.model_name
        )
        
        logger.info("Added search index to RAG system", index_name=index_name)
    
    async def index_document(self, content: str, source_document: str, 
                           document_type: str, metadata: Dict[str, Any] = None) -> bool:
        """Index a new document through the enhanced RAG pipeline"""
        
        chunk_metadata = ChunkMetadata(
            source_document=source_document,
            document_type=document_type,
            section=metadata.get("section") if metadata else None,
            author=metadata.get("author") if metadata else None,
            date_created=metadata.get("date_created") if metadata else None,
            project_number=metadata.get("project_number") if metadata else None,
            client=metadata.get("client") if metadata else None,
            folder_path=metadata.get("folder_path") if metadata else None
        )
        
        # Determine target index based on document type
        target_index = self._select_target_index(document_type)
        
        success = await self.rag_pipeline.index_document(
            content, chunk_metadata, target_index
        )
        
        if success:
            logger.info("Document indexed successfully", 
                       source=source_document, 
                       type=document_type,
                       target_index=target_index)
        
        return success
    
    def _select_target_index(self, document_type: str) -> str:
        """Select appropriate index based on document type"""
        
        type_mapping = {
            "policy": "policies",
            "procedure": "procedures", 
            "standard": "standards",
            "project": "projects",
            "calculation": "projects",
            "correspondence": "projects",
            "template": "procedures"
        }
        
        target = type_mapping.get(document_type, "main")
        
        # Fall back to main if specific index doesn't exist
        if target not in self.search_clients:
            target = "main"
            
        return target
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get status information about the RAG system"""
        
        return {
            "pipeline_status": "active",
            "available_indices": list(self.search_clients.keys()),
            "supported_document_types": [
                "policy", "procedure", "standard", "project", 
                "calculation", "correspondence", "template"
            ],
            "search_strategies": [
                "vector", "keyword", "hybrid", "semantic_hybrid"
            ],
            "features": [
                "multi_source_search",
                "semantic_chunking", 
                "query_analysis",
                "confidence_scoring",
                "source_attribution"
            ]
        }
