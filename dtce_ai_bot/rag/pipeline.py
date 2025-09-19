"""
RAG Pipeline Orchestration

Main pipeline that orchestrates the complete RAG workflow.
"""

from typing import List, Dict, Any, Optional, Union
import logging
from pathlib import Path
import json

from .config import RAGConfig
from .chunker import DocumentChunker, Chunk
from .embedder import EmbeddingGenerator
from .retriever import HybridRetriever, SearchResult
from .generator import AnswerGenerator
from .indexer import SearchIndexer

logger = logging.getLogger(__name__)


class DocumentIngestionPipeline:
    """Pipeline for ingesting documents into the RAG system"""
    
    def __init__(self, config: RAGConfig):
        self.config = config
        self.chunker = DocumentChunker(config.chunking)
        self.embedder = EmbeddingGenerator(config)
        self.indexer = SearchIndexer(config)
    
    def ingest_document(self, content: str, metadata: Dict[str, Any]) -> bool:
        """
        Ingest a single document
        
        Args:
            content: Document content
            metadata: Document metadata
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Chunk the document
            chunks = self.chunker.chunk_document(content, metadata)
            if not chunks:
                logger.warning("No chunks generated from document")
                return False
            
            # Generate embeddings
            chunks_with_embeddings = self.embedder.embed_chunks(chunks)
            
            # Index chunks
            success = self.indexer.index_chunks(chunks_with_embeddings)
            
            if success:
                logger.info(f"Successfully ingested document with {len(chunks)} chunks")
            
            return success
            
        except Exception as e:
            logger.error(f"Error ingesting document: {e}")
            return False
    
    def ingest_documents(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Ingest multiple documents
        
        Args:
            documents: List of documents with 'content' and 'metadata' keys
            
        Returns:
            Ingestion results summary
        """
        total_docs = len(documents)
        successful = 0
        failed = 0
        total_chunks = 0
        
        for i, doc in enumerate(documents):
            content = doc.get('content', '')
            metadata = doc.get('metadata', {})
            
            logger.info(f"Processing document {i+1}/{total_docs}: {metadata.get('title', 'Unknown')}")
            
            # Add document index to metadata
            metadata['ingestion_batch_index'] = i
            
            if self.ingest_document(content, metadata):
                successful += 1
                # Count chunks for this document
                chunks = self.chunker.chunk_document(content, metadata)
                total_chunks += len(chunks)
            else:
                failed += 1
        
        return {
            "total_documents": total_docs,
            "successful": successful,
            "failed": failed,
            "total_chunks": total_chunks,
            "success_rate": successful / total_docs if total_docs > 0 else 0
        }


class RAGPipeline:
    """
    Main RAG pipeline that orchestrates question answering
    """
    
    def __init__(self, config: Optional[RAGConfig] = None):
        self.config = config or RAGConfig.from_env()
        
        # Initialize components
        self.chunker = DocumentChunker(self.config.chunking)
        self.embedder = EmbeddingGenerator(self.config)
        self.retriever = HybridRetriever(self.config, self.embedder)
        self.generator = AnswerGenerator(self.config)
        self.indexer = SearchIndexer(self.config)
        
        # Document ingestion pipeline
        self.ingestion_pipeline = DocumentIngestionPipeline(self.config)
    
    def initialize(self, recreate_index: bool = False) -> bool:
        """
        Initialize the RAG system
        
        Args:
            recreate_index: Whether to recreate the search index
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate configuration
            self.config.validate()
            
            # Create search index
            if not self.indexer.create_index(recreate=recreate_index):
                logger.error("Failed to create search index")
                return False
            
            logger.info("RAG pipeline initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing RAG pipeline: {e}")
            return False
    
    def answer_question(self, question: str, 
                       conversation_history: Optional[List[Dict[str, str]]] = None,
                       filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Answer a question using the RAG pipeline
        
        Args:
            question: User's question
            conversation_history: Previous conversation turns
            filters: Optional metadata filters for retrieval
            
        Returns:
            Answer with sources and metadata
        """
        try:
            # Retrieve relevant documents
            if filters:
                # Use metadata filtering if filters provided
                search_results = self.retriever.retrieve_by_metadata(filters)
                # Also do semantic search and combine
                semantic_results = self.retriever.retrieve(question)
                search_results.extend(semantic_results)
                
                # Deduplicate and re-rank
                search_results = self._deduplicate_results(search_results)
            else:
                search_results = self.retriever.retrieve(question)
            
            # Generate answer
            response = self.generator.generate_answer(
                question, 
                search_results, 
                conversation_history
            )
            
            # Add pipeline metadata
            response.update({
                "pipeline_version": "1.0",
                "retrieval_method": "hybrid",
                "filters_applied": filters is not None
            })
            
            return response
            
        except Exception as e:
            logger.error(f"Error answering question: {e}")
            return {
                "answer": "I encountered an error while processing your question. Please try again.",
                "error": str(e),
                "question": question,
                "sources": [],
                "confidence": "low"
            }
    
    def ingest_document(self, content: str, metadata: Dict[str, Any]) -> bool:
        """Ingest a single document"""
        return self.ingestion_pipeline.ingest_document(content, metadata)
    
    def ingest_documents(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Ingest multiple documents"""
        return self.ingestion_pipeline.ingest_documents(documents)
    
    def ingest_from_file(self, file_path: Union[str, Path], 
                        metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Ingest document from file
        
        Args:
            file_path: Path to the document file
            metadata: Optional metadata (will be supplemented with file info)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return False
            
            # Read file content
            content = file_path.read_text(encoding='utf-8')
            
            # Build metadata
            doc_metadata = metadata or {}
            doc_metadata.update({
                "document_name": file_path.name,
                "file_path": str(file_path),
                "file_extension": file_path.suffix,
                "file_size": file_path.stat().st_size
            })
            
            return self.ingest_document(content, doc_metadata)
            
        except Exception as e:
            logger.error(f"Error ingesting file {file_path}: {e}")
            return False
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system status and statistics"""
        try:
            index_stats = self.indexer.get_index_stats()
            
            return {
                "config_valid": True,
                "index_stats": index_stats,
                "components": {
                    "chunker": "ready",
                    "embedder": "ready", 
                    "retriever": "ready",
                    "generator": "ready",
                    "indexer": "ready"
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                "error": str(e),
                "config_valid": False
            }
    
    def search_documents(self, query: str = "*", 
                        filters: Optional[Dict[str, Any]] = None,
                        top: int = 10) -> List[Dict[str, Any]]:
        """Search documents in the index"""
        return self.indexer.search_documents(query, filters, top)
    
    def delete_document(self, document_id: str) -> bool:
        """Delete a document and all its chunks"""
        return self.indexer.delete_document(document_id)
    
    def _deduplicate_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """Remove duplicate results based on content similarity"""
        if len(results) <= 1:
            return results
        
        unique_results = []
        seen_content = set()
        
        for result in sorted(results, key=lambda x: x.score, reverse=True):
            # Use first 100 characters as similarity key
            content_key = result.content[:100].strip().lower()
            
            if content_key not in seen_content:
                unique_results.append(result)
                seen_content.add(content_key)
        
        return unique_results


# Convenience function for simple usage
def create_rag_pipeline(config: Optional[RAGConfig] = None) -> RAGPipeline:
    """Create and initialize a RAG pipeline"""
    pipeline = RAGPipeline(config)
    pipeline.initialize()
    return pipeline
