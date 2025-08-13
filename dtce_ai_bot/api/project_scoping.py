"""
Project scoping API endpoints.
Handles project analysis and similarity matching.
"""

from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form
from typing import Optional
import structlog
import os

from ..models.project import ProjectRequestModel, ProjectAnalysisResponse
from ..services.project_scoping import get_project_scoping_service, ProjectScopingService
from ..utils.document_extractor import get_document_extractor
from ..utils.openai_document_extractor import get_openai_document_extractor
from ..config.settings import get_settings

logger = structlog.get_logger(__name__)
router = APIRouter()
settings = get_settings()


@router.post("/analyze", response_model=ProjectAnalysisResponse)
async def analyze_project(
    # Text input (optional)
    request_text: Optional[str] = Form(None),
    # File input (optional) 
    file: Optional[UploadFile] = File(None),
    # Metadata (optional)
    client_name: str = Form(""),
    project_name: str = Form(""),
    description: str = Form(""),
    # Response options
    detailed: bool = Form(True),
    scoping_service: ProjectScopingService = Depends(get_project_scoping_service)
):
    """
    Analyze a project request and find similar past projects.
    
    Accepts either text input OR file upload (or both). The AI will:
    1. Extract/process the project content 
    2. Analyze project characteristics and requirements
    3. Find similar past projects in our database
    4. Provide design philosophy and recommendations
    5. Warn about potential issues based on past experience
    
    Args:
        request_text: Direct text input of project requirements
        file: Upload a project document (PDF, Word, Excel, etc.)
        client_name: Client name for context
        project_name: Project name for context  
        description: Additional description/context
        detailed: If False, returns condensed analysis
    """
    try:
        logger.info(
            "Analyzing project request", 
            has_text=bool(request_text),
            has_file=bool(file),
            client_name=client_name,
            project_name=project_name
        )
        
        # Validate input - must have either text or file
        if not request_text and not file:
            raise HTTPException(
                status_code=400,
                detail="Must provide either request_text or upload a file"
            )
        
        # Build the full request text
        full_request_parts = []
        
        # Add metadata context
        if client_name:
            full_request_parts.append(f"Client: {client_name}")
        if project_name:
            full_request_parts.append(f"Project: {project_name}")
        if description:
            full_request_parts.append(f"Description: {description}")
        
        # Add direct text input
        if request_text:
            full_request_parts.append(f"Requirements:\n{request_text}")
        
        # Process uploaded file if provided
        file_metadata = None
        if file:
            # Validate file type
            allowed_extensions = {'.pdf', '.docx', '.doc', '.txt', '.rtf', 
                                 '.xlsx', '.xls', '.pptx', '.ppt'}
            file_extension = os.path.splitext(file.filename)[1].lower()
            
            if file_extension not in allowed_extensions:
                raise HTTPException(
                    status_code=400, 
                    detail=f"File type {file_extension} not supported. Allowed: {', '.join(allowed_extensions)}"
                )
            
            # Extract text from file
            content = await file.read()
            extracted_text = await _extract_text_from_file(content, file.filename, file.content_type)
            
            if not extracted_text:
                raise HTTPException(
                    status_code=400,
                    detail="Could not extract text from the uploaded file. Please ensure it contains readable text."
                )
            
            full_request_parts.append(f"Document Content ({file.filename}):\n{extracted_text}")
            
            file_metadata = {
                "filename": file.filename,
                "content_length": len(extracted_text),
                "extraction_method": "document_processing"
            }
        
        # Combine all parts into final request text
        full_request_text = "\n\n".join(full_request_parts)
        
        # Analyze the project using the service
        result = await scoping_service.analyze_project_request(full_request_text.strip())
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("error"))
        
        # Add file analysis metadata if file was processed
        if file_metadata:
            result["file_analysis"] = file_metadata
        
        # Return detailed or condensed response based on request
        if detailed:
            return ProjectAnalysisResponse(**result)
        else:
            # Return condensed response for quick analysis
            return {
                "project_type": result["project_characteristics"].get("project_type"),
                "key_dimensions": result["project_characteristics"].get("dimensions"), 
                "location": result["project_characteristics"].get("location"),
                "similar_projects_count": len(result["similar_projects"]),
                "quick_insights": result["analysis"][:500] + "..." if len(result["analysis"]) > 500 else result["analysis"],
                "status": "success",
                "file_analysis": file_metadata
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in project analysis endpoint", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-json", response_model=ProjectAnalysisResponse)
async def analyze_project_json(
    request: ProjectRequestModel,
    detailed: bool = True,
    scoping_service: ProjectScopingService = Depends(get_project_scoping_service)
):
    """
    JSON-based project analysis endpoint for programmatic access.
    
    This endpoint provides the same functionality as /analyze but accepts 
    JSON input instead of form data, making it easier for API integrations.
    """
    try:
        logger.info(
            "Analyzing project request via JSON API", 
            client_name=request.client_name,
            project_name=request.project_name
        )
        
        # Build request text with context
        full_request_parts = []
        
        if request.client_name:
            full_request_parts.append(f"Client: {request.client_name}")
        if request.project_name:
            full_request_parts.append(f"Project: {request.project_name}")
        
        full_request_parts.append(f"Requirements:\n{request.request_text}")
        full_request_text = "\n\n".join(full_request_parts)
        
        # Analyze the project
        result = await scoping_service.analyze_project_request(full_request_text)
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("error"))
        
        # Return detailed or condensed response
        if detailed:
            return ProjectAnalysisResponse(**result)
        else:
            return {
                "project_type": result["project_characteristics"].get("project_type"),
                "key_dimensions": result["project_characteristics"].get("dimensions"), 
                "location": result["project_characteristics"].get("location"),
                "similar_projects_count": len(result["similar_projects"]),
                "quick_insights": result["analysis"][:500] + "..." if len(result["analysis"]) > 500 else result["analysis"],
                "status": "success"
            }
        
    except Exception as e:
        logger.error("Error in JSON project analysis endpoint", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


async def _extract_text_from_file(content: bytes, filename: str, content_type: Optional[str]) -> Optional[str]:
    """
    Extract text from uploaded file using existing document extractors.
    This function implements the Single Responsibility Principle by focusing only on text extraction.
    """
    try:
        # Create a temporary blob-like object for our extractors
        class MockBlobClient:
            def __init__(self, content: bytes):
                self._content = content
                
            async def download_blob(self):
                class MockBlobData:
                    def readall(self):
                        return self._content
                return MockBlobData()
        
        mock_blob = MockBlobClient(content)
        
        # Try Form Recognizer first
        try:
            extractor = get_document_extractor(
                settings.azure_form_recognizer_endpoint,
                settings.azure_form_recognizer_key
            )
            result = await extractor.extract_text_from_blob(mock_blob, content_type)
            if result.get("extracted_text"):
                return result["extracted_text"]
        except Exception as e:
            logger.warning("Form Recognizer extraction failed, trying OpenAI", error=str(e))
        
        # Fallback to OpenAI extractor
        try:
            openai_extractor = get_openai_document_extractor(
                settings.azure_openai_endpoint,
                settings.azure_openai_api_key,
                settings.azure_openai_deployment_name
            )
            result = await openai_extractor.extract_text_from_blob(mock_blob, content_type)
            if result.get("extracted_text"):
                return result["extracted_text"]
        except Exception as e:
            logger.error("OpenAI extraction also failed", error=str(e))
        
        return None
        
    except Exception as e:
        logger.error("Text extraction failed completely", error=str(e))
        return None


@router.get("/health")
async def health_check():
    """Health check for project scoping service."""
    return {"status": "healthy", "service": "project_scoping"}
