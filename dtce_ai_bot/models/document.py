"""
Document data models.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class DocumentMetadata(BaseModel):
    """Document metadata model."""
    blob_name: str
    filename: str
    content_type: str
    size: int
    folder: Optional[str] = None
    last_modified: datetime
    created_date: Optional[datetime] = None


class DocumentUploadResponse(BaseModel):
    """Response model for document upload."""
    blob_name: str
    blob_url: str
    filename: str
    content_type: Optional[str]
    size: int
    folder: Optional[str] = None


class DocumentSearchResult(BaseModel):
    """Search result model for documents."""
    id: str
    blob_name: str
    blob_url: str
    filename: str
    content_type: str
    folder: str
    size: int
    last_modified: str
    score: float
    highlights: List[str] = []


class DocumentIndexRequest(BaseModel):
    """Request model for document indexing."""
    blob_name: str
    force_reindex: bool = False


class TextExtractionRequest(BaseModel):
    """Request model for text extraction."""
    blob_name: str


class DocumentSearchRequest(BaseModel):
    """Request model for document search."""
    query: str
    top: int = 10
    filter_folder: Optional[str] = None
