"""
Project scoping data models.
Defines request and response models for project analysis and similarity matching.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class ProjectRequestModel(BaseModel):
    """Model for project request analysis."""
    request_text: str
    client_name: str = ""
    project_name: str = ""


class ProjectCharacteristics(BaseModel):
    """Model for extracted project characteristics."""
    project_type: Optional[str] = None
    dimensions: Optional[str] = None
    location: Optional[str] = None
    loads: Optional[str] = None
    compliance: Optional[str] = None
    materials: Optional[str] = None
    raw_analysis: Optional[str] = None


class SimilarProject(BaseModel):
    """Model for similar project match."""
    title: str
    content: str
    project: str
    file_path: str
    similarity_score: float


class ProjectAnalysisResponse(BaseModel):
    """Response model for project analysis."""
    project_characteristics: Dict[str, Any]
    similar_projects: List[Dict[str, Any]]
    analysis: str
    status: str
    file_analysis: Optional[Dict[str, Any]] = None


class ProjectAnalysisError(BaseModel):
    """Error response model for project analysis."""
    error: str
    status: str = "error"
