"""
Project scoping API endpoints.
Handles project analysis and similarity matching.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any
import structlog

from ..services.project_scoping import get_project_scoping_service, ProjectScopingService

logger = structlog.get_logger(__name__)
router = APIRouter()


class ProjectRequestModel(BaseModel):
    """Model for project request analysis."""
    request_text: str
    client_name: str = ""
    project_name: str = ""


class ProjectAnalysisResponse(BaseModel):
    """Response model for project analysis."""
    project_characteristics: Dict[str, Any]
    similar_projects: list
    analysis: str
    status: str


@router.post("/analyze", response_model=ProjectAnalysisResponse)
async def analyze_project_request(
    request: ProjectRequestModel,
    scoping_service: ProjectScopingService = Depends(get_project_scoping_service)
):
    """
    Analyze a project request and find similar past projects.
    
    This endpoint will:
    1. Extract key technical characteristics from the request
    2. Find similar past projects in our database
    3. Provide design philosophy and recommendations
    4. Warn about potential issues based on past experience
    """
    try:
        logger.info(
            "Analyzing project request", 
            client_name=request.client_name,
            project_name=request.project_name
        )
        
        result = await scoping_service.analyze_project_request(request.request_text)
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("error"))
        
        return ProjectAnalysisResponse(**result)
        
    except Exception as e:
        logger.error("Error in project analysis endpoint", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quick-analysis")
async def quick_project_analysis(
    request: ProjectRequestModel,
    scoping_service: ProjectScopingService = Depends(get_project_scoping_service)
):
    """
    Quick project analysis for immediate feedback.
    Returns just the key insights without full documentation.
    """
    try:
        result = await scoping_service.analyze_project_request(request.request_text)
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("error"))
        
        # Return simplified response for quick analysis
        return {
            "project_type": result["project_characteristics"].get("project_type"),
            "key_dimensions": result["project_characteristics"].get("dimensions"),
            "location": result["project_characteristics"].get("location"),
            "similar_projects_count": len(result["similar_projects"]),
            "quick_insights": result["analysis"][:500] + "..." if len(result["analysis"]) > 500 else result["analysis"],
            "status": "success"
        }
        
    except Exception as e:
        logger.error("Error in quick analysis endpoint", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check for project scoping service."""
    return {"status": "healthy", "service": "project_scoping"}
