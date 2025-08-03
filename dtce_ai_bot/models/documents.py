"""
Document and project models.
"""

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
    """Document metadata model."""
    file_path: str
    file_name: str
    file_size: int
    file_type: str
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    document_type: DocumentType
    project_name: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    indexed_date: Optional[datetime] = None


class ProcessingStatus(BaseModel):
    """Document processing status."""
    document_id: str
    status: str  # "pending", "processing", "completed", "failed"
    progress: float = Field(ge=0, le=100)
    message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_details: Optional[str] = None


class ProjectInfo(BaseModel):
    """Project information model."""
    project_name: str
    project_path: str
    status: ProjectStatus
    document_count: int
    total_size_mb: float
    last_activity: Optional[datetime] = None
    categories: Dict[DocumentType, int] = Field(default_factory=dict)
    description: Optional[str] = None
