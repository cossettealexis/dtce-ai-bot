# Models Module
"""
Pydantic models for request/response validation.
Following SOLID principles with proper model separation.
"""

from .document import (
    DocumentMetadata,
    DocumentSearchResult,
    DocumentUploadResponse
)

from .project import (
    ProjectRequestModel,
    ProjectAnalysisResponse,
    ProjectCharacteristics,
    SimilarProject
)

from .sync_job import (
    SyncJob,
    SyncJobStatus,
    SyncJobRequest,
    SyncJobProgress,
    SyncJobResult,
    SyncJobSummary
)

__all__ = [
    # Document models
    "DocumentMetadata",
    "DocumentSearchResult", 
    "DocumentUploadResponse",
    
    # Project models
    "ProjectRequestModel",
    "ProjectAnalysisResponse", 
    "ProjectCharacteristics",
    "SimilarProject",
    
    # Sync job models
    "SyncJob",
    "SyncJobStatus",
    "SyncJobRequest",
    "SyncJobProgress",
    "SyncJobResult",
    "SyncJobSummary"
]