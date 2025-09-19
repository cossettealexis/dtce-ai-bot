"""
RAG Configuration Management

Centralized configuration for all RAG components.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import os


@dataclass
class AzureConfig:
    """Azure service configuration"""
    search_service_name: str = field(default_factory=lambda: os.getenv("AZURE_SEARCH_SERVICE_NAME", ""))
    search_admin_key: str = field(default_factory=lambda: os.getenv("AZURE_SEARCH_ADMIN_KEY", ""))
    search_index_name: str = field(default_factory=lambda: os.getenv("AZURE_SEARCH_INDEX_NAME", "dtce-docs"))
    openai_endpoint: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_ENDPOINT", ""))
    openai_api_key: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_API_KEY", ""))
    openai_api_version: str = "2024-02-15-preview"
    
    @property
    def search_endpoint(self) -> str:
        return f"https://{self.search_service_name}.search.windows.net"


@dataclass
class ModelConfig:
    """Model configuration for embeddings and generation"""
    embedding_model: str = "text-embedding-ada-002"
    embedding_dimensions: int = 1536
    chat_model: str = "gpt-4"
    max_tokens: int = 4000
    temperature: float = 0.1
    top_p: float = 0.9


@dataclass
class ChunkingConfig:
    """Document chunking configuration"""
    chunk_size: int = 1000
    overlap_size: int = 200
    min_chunk_size: int = 100
    max_chunk_size: int = 2000
    respect_sentence_boundaries: bool = True
    respect_paragraph_boundaries: bool = True


@dataclass
class RetrievalConfig:
    """Retrieval configuration"""
    top_k: int = 10
    semantic_top_k: int = 5
    keyword_top_k: int = 5
    hybrid_weight: float = 0.6  # Weight for vector search vs keyword
    enable_semantic_ranking: bool = True
    enable_multi_query: bool = True
    query_expansion_count: int = 3


@dataclass
class RAGConfig:
    """Main RAG system configuration"""
    azure: AzureConfig = field(default_factory=AzureConfig)
    models: ModelConfig = field(default_factory=ModelConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    
    # Generation settings
    max_context_length: int = 16000
    response_max_tokens: int = 1000
    include_sources: bool = True
    min_relevance_score: float = 0.7
    
    def validate(self) -> bool:
        """Validate configuration"""
        required_azure_fields = [
            self.azure.search_service_name,
            self.azure.search_admin_key,
            self.azure.openai_endpoint,
            self.azure.openai_api_key
        ]
        
        if not all(required_azure_fields):
            raise ValueError("Missing required Azure configuration")
        
        if self.chunking.chunk_size <= self.chunking.overlap_size:
            raise ValueError("Chunk size must be larger than overlap size")
        
        if self.retrieval.top_k <= 0:
            raise ValueError("top_k must be positive")
        
        return True
    
    @classmethod
    def from_env(cls) -> 'RAGConfig':
        """Create configuration from environment variables"""
        config = cls()
        config.validate()
        return config
