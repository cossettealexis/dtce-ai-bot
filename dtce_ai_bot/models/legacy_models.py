from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class DocumentType(str, Enum):
    """Document type enumeration based on folder structure."""
    FEES_INVOICES = "01_Fees_and_Invoices"
    EMAILS = "02_Emails"
    INTERNAL_REVIEW = "03_For_internal_review"
    RECEIVED = "04_Received"
    ISSUED = "05_Issued"
    CALCULATIONS = "06_Calculations"
    DRAWINGS = "07_Drawings"
    REPORTS_SPECS = "08_Reports_and_Specifications"
    PHOTOS = "09_Photos"
    SITE_NOTES = "10_Site_meeting_and_phone_notes"
    ENGINEERING = "Engineering"
    OTHER = "Other"


class ProjectStatus(str, Enum):
    """Project status based on folder analysis."""
    ACTIVE = "active"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    UNKNOWN = "unknown"


class DocumentMetadata(BaseModel):
    """Metadata for a document in the DTCE system."""
    
    # Basic file information
    file_id: str = Field(..., description="Unique identifier for the file")
    file_name: str = Field(..., description="Original filename")
    file_path: str = Field(..., description="Full path in SharePoint")
    file_size: int = Field(..., description="File size in bytes")
    file_type: str = Field(..., description="File extension")
    modified_date: datetime = Field(..., description="Last modified date")
    created_date: Optional[datetime] = Field(None, description="Creation date")
    
    # SharePoint specific
    sharepoint_url: str = Field(..., description="SharePoint URL for the file")
    download_url: Optional[str] = Field(None, description="Direct download URL")
    
    # DTCE specific metadata
    project_id: Optional[str] = Field(None, description="Project number (e.g., 219, 220)")
    document_type: DocumentType = Field(DocumentType.OTHER, description="Document category")
    folder_path: str = Field(..., description="Folder structure path")
    
    # Content metadata (to be filled during processing)
    content_preview: Optional[str] = Field(None, description="First 500 chars of content")
    extracted_text: Optional[str] = Field(None, description="Full extracted text")
    
    # Derived metadata
    client_name: Optional[str] = Field(None, description="Client name if extractable")
    project_title: Optional[str] = Field(None, description="Project title if extractable")
    project_status: ProjectStatus = Field(ProjectStatus.UNKNOWN, description="Project status")
    keywords: List[str] = Field(default_factory=list, description="Extracted keywords")
    
    # Azure indexing
    blob_url: Optional[str] = Field(None, description="Azure Blob Storage URL")
    indexed_date: Optional[datetime] = Field(None, description="Date indexed in search")


class SearchQuery(BaseModel):
    """Search query model for the AI assistant."""
    
    query: str = Field(..., description="Natural language query")
    filters: Optional[Dict[str, Any]] = Field(None, description="Additional filters")
    max_results: int = Field(20, description="Maximum number of results")
    include_content: bool = Field(True, description="Include document content in results")


class SearchResult(BaseModel):
    """Search result model."""
    
    document: DocumentMetadata
    score: float = Field(..., description="Search relevance score")
    highlights: List[str] = Field(default_factory=list, description="Highlighted text snippets")


class SearchResponse(BaseModel):
    """Complete search response."""
    
    query: str = Field(..., description="Original query")
    total_results: int = Field(..., description="Total number of matching documents")
    results: List[SearchResult] = Field(..., description="Search results")
    ai_summary: Optional[str] = Field(None, description="AI-generated summary of results")
    processing_time: float = Field(..., description="Query processing time in seconds")


class ProcessingStatus(BaseModel):
    """Status of document processing operations."""
    
    operation_id: str = Field(..., description="Unique operation identifier")
    status: str = Field(..., description="Current status")
    total_files: int = Field(0, description="Total files to process")
    processed_files: int = Field(0, description="Files processed so far")
    failed_files: int = Field(0, description="Files that failed processing")
    start_time: datetime = Field(..., description="Operation start time")
    end_time: Optional[datetime] = Field(None, description="Operation end time")
    error_message: Optional[str] = Field(None, description="Error message if failed")


class HealthCheck(BaseModel):
    """Health check response model."""
    
    status: str = Field(..., description="Overall system status")
    services: Dict[str, str] = Field(..., description="Individual service statuses")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(..., description="Application version")
