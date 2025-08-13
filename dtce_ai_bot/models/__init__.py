# Models Module
"""
Data models and schemas.
"""

from .document import DocumentMetadata, DocumentUploadResponse, DocumentSearchResult, DocumentIndexRequest
from .project import ProjectRequestModel, ProjectAnalysisResponse, ProjectCharacteristics, SimilarProject, ProjectAnalysisError

__all__ = [
    # Document models
    "DocumentMetadata",
    "DocumentUploadResponse", 
    "DocumentSearchResult",
    "DocumentIndexRequest",
    # Project models
    "ProjectRequestModel",
    "ProjectAnalysisResponse",
    "ProjectCharacteristics",
    "SimilarProject", 
    "ProjectAnalysisError"
]
