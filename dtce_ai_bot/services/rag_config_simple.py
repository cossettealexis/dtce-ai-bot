"""
Simple RAG Configuration Service
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class SearchMode(Enum):
    """Search modes for different query types."""
    HYBRID = "hybrid"
    VECTOR_ONLY = "vector"
    KEYWORD_ONLY = "keyword"
    SEMANTIC = "semantic"


@dataclass
class RAGConfig:
    """Configuration settings for RAG operations."""
    max_sources: int = 5
    chunk_overlap: int = 150
    temperature: float = 0.2
    search_mode: SearchMode = SearchMode.HYBRID


class RAGConfigService:
    """
    Manages configuration settings for the enhanced RAG system.
    """
    
    def __init__(self):
        self.default_config = RAGConfig()
        self.query_type_configs = {
            'factual': RAGConfig(max_sources=3, temperature=0.1),
            'comparative': RAGConfig(max_sources=5, temperature=0.2),
            'analytical': RAGConfig(max_sources=7, temperature=0.3)
        }
        logger.info("RAG Config Service initialized")
    
    def get_config_for_query(self, query_type: str = "general") -> RAGConfig:
        """Get configuration for a specific query type."""
        return self.query_type_configs.get(query_type, self.default_config)
    
    def update_config(self, query_type: str, **kwargs) -> None:
        """Update configuration for a query type."""
        if query_type not in self.query_type_configs:
            self.query_type_configs[query_type] = RAGConfig()
        
        config = self.query_type_configs[query_type]
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
    
    def get_search_mode(self, query_complexity: str = "medium") -> SearchMode:
        """Determine search mode based on query complexity."""
        complexity_mapping = {
            "simple": SearchMode.KEYWORD_ONLY,
            "medium": SearchMode.HYBRID,
            "complex": SearchMode.SEMANTIC
        }
        return complexity_mapping.get(query_complexity, SearchMode.HYBRID)


# Global config service instance
config_service = RAGConfigService()
