"""
Search-related data models.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class SearchQuery(BaseModel):
    """Search query model."""
    query: str = Field(..., description="Search query text")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Search filters")
    limit: int = Field(default=10, ge=1, le=50, description="Number of results to return")
    include_content: bool = Field(default=True, description="Include document content in results")


class SearchResult(BaseModel):
    """Individual search result."""
    id: str
    title: str
    content: str
    file_path: str
    document_type: str
    project_name: Optional[str] = None
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Search response containing results."""
    query: str
    total_results: int
    results: List[SearchResult]
    execution_time_ms: float
    suggested_queries: List[str] = Field(default_factory=list)
