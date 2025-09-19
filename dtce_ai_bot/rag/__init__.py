"""
RAG (Retrieval-Augmented Generation) System

A modular RAG implementation for DTCE AI Bot with:
- Hybrid search (vector + keyword)
- Semantic ranking
- Multi-query retrieval
- Strategic document chunking
- Azure AI Search integration
"""

from .config import RAGConfig
from .chunker import DocumentChunker
from .embedder import EmbeddingGenerator
from .retriever import HybridRetriever
from .generator import AnswerGenerator
from .indexer import SearchIndexer
from .pipeline import RAGPipeline

__all__ = [
    'RAGConfig',
    'DocumentChunker',
    'EmbeddingGenerator',
    'HybridRetriever',
    'AnswerGenerator',
    'SearchIndexer',
    'RAGPipeline'
]
