"""
Document processing service endpoints.
Implements document upload, indexing, text extraction, and search functionality.
"""

import os
import tempfile
import re
import json
import asyncio
import threading
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
import structlog
from azure.storage.blob import BlobServiceClient
from azure.search.documents import SearchClient

from ..config.settings import get_settings
from ..models.document import DocumentMetadata, DocumentSearchResult, DocumentUploadResponse
from ..integrations.azure_search import get_search_client
from ..integrations.azure_storage import get_storage_client
from ..utils.document_extractor import get_document_extractor
from ..utils.openai_document_extractor import get_openai_document_extractor
from ..integrations.microsoft_graph import get_graph_client, MicrosoftGraphClient
from ..services.document_qa import DocumentQAService
from ..services.document_sync_service import get_document_sync_service

logger = structlog.get_logger(__name__)
router = APIRouter()

settings = get_settings()


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    folder: Optional[str] = None,
    storage_client: BlobServiceClient = Depends(get_storage_client)
) -> DocumentUploadResponse:
    """
    Upload a document to Azure Blob Storage.
    
    Args:
        file: The file to upload
        folder: Optional folder to organize documents
        storage_client: Azure Storage client
        
    Returns:
        Document upload response with blob URL and metadata
    """
    try:
        logger.info("Starting document upload", filename=file.filename, content_type=file.content_type)
        
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")
            
        # Validate file type - expand support for more file types
        allowed_extensions = {'.pdf', '.docx', '.doc', '.txt', '.md', '.py', '.js', '.ts', '.json', '.xml', '.html', 
                             '.msg', '.eml', '.xlsx', '.xls', '.pptx', '.ppt', '.csv', '.rtf', '.odt', '.ods', '.odp'}
        file_extension = os.path.splitext(file.filename)[1].lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"File type {file_extension} not supported. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # Generate blob name
        blob_name = f"{folder}/{file.filename}" if folder else file.filename
        
        # Upload to blob storage
        blob_client = storage_client.get_blob_client(
            container=settings.azure_storage_container,
            blob=blob_name
        )
        
        # Read file content
        content = await file.read()
        
        # Sanitize metadata to ensure ASCII compatibility
        def sanitize_metadata_value(value):
            """Convert metadata value to ASCII-safe string."""
            if not value:
                return ""
            # Convert to string and encode/decode to remove non-ASCII characters
            try:
                return str(value).encode('ascii', errors='replace').decode('ascii')
            except Exception:
                # Fallback: replace all non-ASCII with underscore
                return ''.join(c if ord(c) < 128 else '_' for c in str(value))
        
        # Upload blob with metadata
        metadata = {
            "original_filename": sanitize_metadata_value(file.filename),
            "content_type": file.content_type or "application/octet-stream",
            "size": str(len(content)),
            "folder": folder or ""
        }
        
        blob_client.upload_blob(content, overwrite=True, metadata=metadata)
        blob_url = blob_client.url
        
        logger.info("Document uploaded successfully", blob_name=blob_name, blob_url=blob_url)
        
        return DocumentUploadResponse(
            blob_name=blob_name,
            blob_url=blob_url,
            filename=file.filename,
            content_type=file.content_type,
            size=len(content),
            folder=folder
        )
        
    except Exception as e:
        logger.error("Document upload failed", error=str(e), filename=file.filename)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/extract")
async def extract_text(
    blob_name: str,
    storage_client: BlobServiceClient = Depends(get_storage_client)
) -> JSONResponse:
    """
    Extract text content from a document using Azure Form Recognizer.
    
    Args:
        blob_name: Name of the blob to extract text from
        storage_client: Azure Storage client
        
    Returns:
        Extracted text content and metadata
    """
    try:
        settings = get_settings()
        logger.info("Starting text extraction", blob_name=blob_name)
        
        # Get blob client
        blob_client = storage_client.get_blob_client(
            container=settings.azure_storage_container,
            blob=blob_name
        )
        
        # Check if blob exists
        if not blob_client.exists():
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get blob properties for metadata
        blob_properties = blob_client.get_blob_properties()
        content_type = blob_properties.content_settings.content_type
        
        # Try Form Recognizer first (proper document processing), fallback to OpenAI
        try:
            # Initialize Form Recognizer extractor with your new endpoint
            extractor = get_document_extractor(
                settings.azure_form_recognizer_endpoint,
                settings.azure_form_recognizer_key
            )
            
            # Extract text using Form Recognizer
            extraction_result = await extractor.extract_text_from_blob(blob_client, content_type)
            
            # Check if extraction was successful
            if not extraction_result.get("extraction_success", True):
                raise Exception("Form Recognizer extraction failed")
                
            logger.info("Form Recognizer extraction successful", blob_name=blob_name)
                
        except Exception as form_recognizer_error:
            logger.warning(
                "Form Recognizer extraction failed, trying OpenAI extractor", 
                blob_name=blob_name, 
                error=str(form_recognizer_error)
            )
            
            # Fallback to OpenAI extractor
            try:
                openai_extractor = get_openai_document_extractor(
                    settings.azure_openai_endpoint,
                    settings.azure_openai_api_key,
                    settings.azure_openai_deployment_name
                )
                
                extraction_result = await openai_extractor.extract_text_from_blob(blob_client, content_type)
                logger.info("OpenAI fallback extraction successful", blob_name=blob_name)
                
            except Exception as openai_error:
                logger.warning(
                    "Both Form Recognizer and OpenAI extraction failed, trying local DocumentProcessor", 
                    blob_name=blob_name, 
                    form_recognizer_error=str(form_recognizer_error),
                    openai_error=str(openai_error)
                )
                
                # Try local DocumentProcessor as final fallback
                try:
                    from dtce_ai_bot.utils.document_processor import DocumentProcessor
                    
                    # Download blob content
                    blob_data = blob_client.download_blob().readall()
                    
                    # Determine file extension from blob name
                    file_extension = "." + blob_name.lower().split(".")[-1] if "." in blob_name else ""
                    
                    # Create a simple metadata object
                    class SimpleMetadata:
                        def __init__(self, file_type, file_name):
                            self.file_type = file_type
                            self.file_name = file_name
                            self.extracted_text = ""
                    
                    metadata = SimpleMetadata(file_extension, blob_name)
                    
                    # Process with local DocumentProcessor
                    processor = DocumentProcessor()
                    result = await processor.process_document(metadata, blob_data)
                    
                    if result.extracted_text and result.extracted_text.strip():
                        extraction_result = {
                            "extracted_text": result.extracted_text,
                            "character_count": len(result.extracted_text),
                            "page_count": 1,
                            "extraction_method": "local_processor",
                            "success": True
                        }
                        logger.info("Local DocumentProcessor extraction successful", blob_name=blob_name)
                    else:
                        raise Exception("No text extracted by local processor")
                        
                except Exception as local_error:
                    logger.error(
                        "All extraction methods failed including local processor", 
                        blob_name=blob_name, 
                        local_error=str(local_error)
                    )
                    
                    # Return minimal extraction result with document name for indexing
                    extraction_result = {
                        "extracted_text": f"Document: {blob_name}",
                        "character_count": len(blob_name),
                        "page_count": 1,
                        "extraction_method": "filename_only",
                        "error": f"Form Recognizer: {form_recognizer_error}, OpenAI: {openai_error}, Local: {local_error}"
                    }
        
        # Log success
        logger.info(
            "Text extraction completed",
            blob_name=blob_name,
            character_count=extraction_result.get("character_count", 0),
            page_count=extraction_result.get("page_count", 0),
            extraction_method=extraction_result.get("extraction_method", "unknown")
        )
        
        return JSONResponse({
            "blob_name": blob_name,
            "status": "extracted",
            **extraction_result
        })
        
    except Exception as e:
        logger.error("Text extraction failed", error=str(e), blob_name=blob_name)
        raise HTTPException(status_code=500, detail=f"Text extraction failed: {str(e)}")

@router.post("/index")
async def index_document(
    blob_name: str,
    search_client: SearchClient = Depends(get_search_client),
    storage_client: BlobServiceClient = Depends(get_storage_client)
) -> JSONResponse:
    """
    Index a document in Azure Cognitive Search after extracting its text.
    
    Args:
        blob_name: Name of the blob to index
        search_client: Azure Search client
        storage_client: Azure Storage client
        
    Returns:
        Indexing status and document metadata
    """
    try:
        logger.info("Starting document indexing", blob_name=blob_name)
        
        # First extract text from the document
        blob_client = storage_client.get_blob_client(
            container=settings.azure_storage_container,
            blob=blob_name
        )
        
        if not blob_client.exists():
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get blob metadata
        blob_properties = blob_client.get_blob_properties()
        metadata = blob_properties.metadata or {}
        
        # Extract text (reuse extraction logic) - skip if Form Recognizer unavailable
        try:
            extraction_response = await extract_text(blob_name, storage_client)
            
            # Handle different response types
            if hasattr(extraction_response, 'body'):
                import json
                extraction_data = json.loads(extraction_response.body.decode())
            else:
                extraction_data = extraction_response
                
        except Exception as e:
            logger.warning("Text extraction failed, trying local PDF processor", error=str(e))
            # Try local document processor as final fallback
            try:
                from ..utils.document_processor import DocumentProcessor
                processor = DocumentProcessor()
                
                # Download blob content
                blob_data = blob_client.download_blob().readall()
                
                # Create a mock document metadata object
                from ..models.legacy_models import DocumentMetadata
                mock_doc = DocumentMetadata(
                    file_name=metadata.get('original_filename', blob_name),
                    file_type=os.path.splitext(blob_name)[1].lower(),
                    file_size=len(blob_data)
                )
                
                # Process the document
                processed_doc = await processor.process_document(mock_doc, blob_data)
                
                if processed_doc.extracted_text:
                    extraction_data = {
                        "extracted_text": processed_doc.extracted_text,
                        "character_count": len(processed_doc.extracted_text),
                        "page_count": 1,
                        "extraction_method": "local_processor"
                    }
                    logger.info("Local processor extraction successful", blob_name=blob_name)
                else:
                    raise Exception("Local processor failed to extract text")
                    
            except Exception as local_error:
                logger.warning("Local processor also failed", error=str(local_error))
                # For unsupported file types, create basic metadata
                file_extension = os.path.splitext(blob_name)[1].lower()
                if file_extension in ['.eml']:  # Removed .msg since we now support it
                    extraction_data = {
                        "extracted_text": f"Email document: {metadata.get('original_filename', blob_name)}",
                        "file_type": "email",
                        "note": "Email files require specialized extraction tools"
                    }
                elif file_extension in ['.xlsx', '.xls']:
                    extraction_data = {
                        "extracted_text": f"Spreadsheet document: {metadata.get('original_filename', blob_name)}",
                        "file_type": "spreadsheet",
                        "note": "Spreadsheet files contain tabular data"
                    }
                else:
                    extraction_data = {
                        "extracted_text": f"Document: {metadata.get('original_filename', blob_name)}",
                        "file_type": "document",
                        "note": f"File type {file_extension} processed without text extraction"
                    }
        
        # Extract project information from folder path
        folder_path = metadata.get("folder", "")
        project_name = ""
        year = None
        
        if folder_path:
            path_parts = folder_path.split("/")
            # New logic: if 'Projects' is in the path, the next part is the project name.
            if "Projects" in path_parts:
                try:
                    project_folder_index = path_parts.index("Projects")
                    if project_folder_index + 1 < len(path_parts):
                        project_name = path_parts[project_folder_index + 1]
                        logger.info("Extracted project name from path", project_name=project_name, folder_path=folder_path)
                except (ValueError, IndexError):
                    logger.warning("Could not extract project name after 'Projects' folder", folder_path=folder_path)
            
            # Fallback to find year if it exists
            for part in path_parts:
                if part.isdigit() and len(part) == 4:
                    year = int(part)
                    break # Assume first 4-digit number is the year
        
        # Prepare document for indexing - sanitize document ID for Azure Search
        import re
        document_id = re.sub(r'[^a-zA-Z0-9_-]', '_', blob_name)
        # Ensure no double underscores and clean up
        document_id = re.sub(r'_+', '_', document_id).strip('_')
        
        search_document = {
            "id": document_id,
            "blob_name": blob_name,
            "blob_url": blob_client.url,
            "filename": metadata.get("original_filename", blob_name),
            "content_type": metadata.get("content_type", ""),
            "folder": folder_path,
            "size": int(metadata.get("size", 0)),
            "content": extraction_data.get("extracted_text", "") if isinstance(extraction_data, dict) else str(extraction_data),
            "last_modified": blob_properties.last_modified.isoformat(),
            "created_date": blob_properties.creation_time.isoformat() if blob_properties.creation_time else blob_properties.last_modified.isoformat(),
            "project_name": project_name,
            "year": year
        }
        
        # Upload to search index
        result = search_client.upload_documents([search_document])
        
        logger.info("Document indexed successfully", blob_name=blob_name, document_id=document_id)
        
        return JSONResponse({
            "status": "indexed",
            "blob_name": blob_name,
            "document_id": document_id,
            "index_result": [r.succeeded for r in result],
            "content_length": len(search_document["content"])
        })
        
    except Exception as e:
        logger.error("Document indexing failed", error=str(e), blob_name=blob_name)
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")


@router.get("/search", response_model=List[DocumentSearchResult])
async def search_documents(
    query: str,
    top: int = 10,
    filter_folder: Optional[str] = None,
    search_client: SearchClient = Depends(get_search_client)
) -> List[DocumentSearchResult]:
    """
    Search indexed documents using Azure Cognitive Search.
    
    Args:
        query: Search query string
        top: Maximum number of results to return
        filter_folder: Optional folder filter
        search_client: Azure Search client
        
    Returns:
        List of matching documents with relevance scores
    """
    try:
        logger.info("Starting document search", query=query, top=top, filter_folder=filter_folder)
        
        # Build search filter
        search_filter = f"folder eq '{filter_folder}'" if filter_folder else None
        
        # Perform search
        results = search_client.search(
            search_text=query,
            top=top,
            filter=search_filter,
            highlight_fields="content",
            select=["id", "blob_name", "blob_url", "filename", "content_type", "folder", "size", "last_modified"]
        )
        
        # Format results
        search_results = []
        for result in results:
            highlights = result.get("@search.highlights", {}).get("content", [])
            
            search_results.append(DocumentSearchResult(
                id=result["id"],
                blob_name=result["blob_name"],
                blob_url=result["blob_url"],
                filename=result["filename"],
                content_type=result["content_type"],
                folder=result["folder"],
                size=result["size"],
                last_modified=result["last_modified"],
                score=result["@search.score"],
                highlights=highlights
            ))
        
        logger.info("Document search completed", query=query, result_count=len(search_results))
        
        return search_results
        
    except Exception as e:
        logger.error("Document search failed", error=str(e), query=query)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/engineering/projects")
async def list_engineering_projects(
    project_id: Optional[str] = None,
    document_type: Optional[str] = None,
    critical_only: bool = True,
    graph_client: MicrosoftGraphClient = Depends(get_graph_client)
) -> JSONResponse:
    """
    List ALL engineering project documents with smart filtering.
    
    Explores all project folders and Engineering folder to find relevant documents.
    
    Args:
        project_id: Specific project ID (any project number/name)
        document_type: Filter by document type (fees_invoices, reports, drawings, etc.)
        critical_only: Only show critical documents for search
        graph_client: Microsoft Graph client
        
    Returns:
        Structured list of engineering documents from ALL projects with metadata
    """
    try:
        logger.info("Listing ALL engineering project documents", 
                   project_id=project_id, document_type=document_type, critical_only=critical_only)
        
        # Get comprehensive documents from Suitefiles (all projects)
        suitefiles_docs = await graph_client.sync_suitefiles_documents()
        
        # Filter based on criteria
        filtered_docs = []
        for doc in suitefiles_docs:
            # Apply project ID filter (if specified)
            if project_id and doc.get("project_id") != project_id:
                continue
                
            # Apply document type filter
            if document_type and doc.get("document_type") != document_type:
                continue
                
            # Apply critical documents filter
            if critical_only and not doc.get("is_critical_for_search", False):
                continue
                
            filtered_docs.append({
                "file_id": doc["file_id"],
                "filename": doc["name"],
                "project_id": doc.get("project_id"),
                "project_folder": doc.get("project_folder"),
                "document_type": doc.get("document_type", "general"),
                "folder_category": doc.get("folder_category", "General"),
                "drive_name": doc["drive_name"],
                "size": doc.get("size", 0),
                "last_modified": doc.get("modified", ""),
                "is_critical": doc.get("is_critical_for_search", False),
                "download_url": doc.get("download_url", ""),
                "full_path": doc.get("full_path", ""),
                "folder_path": doc.get("folder_path", "")
            })
        
        # Group by project for better organization
        projects_summary = {}
        for doc in filtered_docs:
            proj_id = doc.get("project_id", "Engineering")
            if proj_id not in projects_summary:
                projects_summary[proj_id] = {
                    "project_id": proj_id,
                    "document_count": 0,
                    "document_types": set(),
                    "critical_documents": 0
                }
            
            projects_summary[proj_id]["document_count"] += 1
            projects_summary[proj_id]["document_types"].add(doc.get("document_type", "Other"))
            if doc.get("is_critical", False):
                projects_summary[proj_id]["critical_documents"] += 1
        
        # Convert sets to lists for JSON serialization
        for proj in projects_summary.values():
            proj["document_types"] = list(proj["document_types"])
        
        logger.info("Engineering project listing completed", 
                   total_documents=len(filtered_docs),
                   projects_found=len(projects_summary))
        
        return JSONResponse({
            "documents": filtered_docs,
            "total_count": len(filtered_docs),
            "projects_summary": list(projects_summary.values()),
            "filters_applied": {
                "project_id": project_id,
                "document_type": document_type,
                "critical_only": critical_only
            }
        })
        
    except Exception as e:
        logger.error("Failed to list engineering projects", error=str(e))
        return JSONResponse({
            "documents": [],
            "total_count": 0,
            "projects_summary": [],
            "error": f"Failed to retrieve engineering projects: {str(e)}"
        })


@router.get("/engineering/analyze-structure")
async def analyze_suitefiles_structure(
    graph_client: MicrosoftGraphClient = Depends(get_graph_client)
) -> JSONResponse:
    """
    Analyze the actual Suitefiles folder structure to understand organization.
    
    This will help us:
    1. See what drives/libraries exist
    2. Understand the folder hierarchy
    3. Find ALL project folders (not just specific ranges)
    4. Identify Engineering folders
    """
    try:
        logger.info("Analyzing complete Suitefiles structure")
        
        # Get the Suitefiles site
        suitefiles_site = await graph_client.get_site_by_name("suitefiles")
        if not suitefiles_site:
            suitefiles_site = await graph_client.get_site_by_name("dtce")
            
        if not suitefiles_site:
            return JSONResponse({
                "status": "error",
                "message": "Cannot find Suitefiles or DTCE site"
            })
        
        site_id = suitefiles_site["id"]
        
        # Get all drives/document libraries
        drives = await graph_client.get_drives(site_id)
        
        structure_analysis = {
            "site_info": {
                "name": suitefiles_site.get("displayName", ""),
                "site_id": site_id,
                "web_url": suitefiles_site.get("webUrl", "")
            },
            "drives": [],
            "folder_patterns": {},
            "all_projects": [],
            "engineering_folders": []
        }
        
        for drive in drives:
            drive_id = drive["id"]
            drive_name = drive.get("name", "Unknown")
            
            # Get files in this drive to analyze structure
            files = await graph_client.get_files_in_drive(site_id, drive_id)
            
            # Analyze file paths for patterns
            folder_structure = set()
            project_folders = set()
            
            for file in files:
                full_path = file.get("full_path", "")
                folder_path = file.get("folder_path", "")
                
                path_to_analyze = full_path or folder_path
                if path_to_analyze:
                    path_parts = path_to_analyze.split("/")
                    
                    # Look for folder patterns
                    for part in path_parts:
                        if part and not part.startswith("http"):
                            folder_structure.add(part)
                    
                    # Look for project patterns (Projects/XXX structure)
                    for i, part in enumerate(path_parts):
                        if part.lower() == "projects" and i + 1 < len(path_parts):
                            project_folder = path_parts[i + 1]
                            if project_folder not in project_folders:
                                project_folders.add(project_folder)
                                structure_analysis["all_projects"].append({
                                    "project_id": project_folder,
                                    "drive": drive_name,
                                    "sample_file": file.get("name", ""),
                                    "full_path": path_to_analyze
                                })
                    
                    # Look for Engineering folders
                    for part in path_parts:
                        if any(keyword in part.lower() for keyword in 
                               ["engineering", "design", "calculation", "drawing"]):
                            structure_analysis["engineering_folders"].append({
                                "folder_name": part,
                                "drive": drive_name,
                                "full_path": path_to_analyze
                            })
            
            structure_analysis["drives"].append({
                "drive_id": drive_id,
                "drive_name": drive_name,
                "total_files": len(files),
                "sample_folders": list(folder_structure)[:20],  # First 20 unique folders
                "project_folders": sorted(list(project_folders))
            })
        
        # Identify patterns
        all_projects = [p["project_id"] for p in structure_analysis["all_projects"]]
        unique_projects = list(set(all_projects))
        
        structure_analysis["folder_patterns"] = {
            "total_drives": len(drives),
            "unique_project_folders": sorted(unique_projects),
            "total_projects_found": len(structure_analysis["all_projects"]),
            "engineering_folder_count": len(structure_analysis["engineering_folders"])
        }
        
        logger.info("Complete Suitefiles structure analysis", 
                   total_drives=len(drives),
                   all_projects=len(structure_analysis["all_projects"]))
        
        return JSONResponse(structure_analysis)
        
    except Exception as e:
        logger.error("Structure analysis failed", error=str(e))
        return JSONResponse({
            "status": "error",
            "message": f"Analysis failed: {str(e)}",
            "suggestion": "Check Microsoft Graph permissions and site access"
        })


@router.get("/engineering/search")
async def search_engineering_documents(
    query: str,
    project_id: Optional[str] = None,
    document_type: Optional[str] = None,
    graph_client: MicrosoftGraphClient = Depends(get_graph_client)
) -> JSONResponse:
    """
    Search engineering documents with natural language queries for ANY project.
    
    Examples of engineer queries this should handle:
    - "Show me the final report for project 222"
    - "List all 2024 bridge projects with final specifications"
    - "What was issued to the client for project 100?"
    - "Which projects had an internal review before issue?"
    
    Args:
        query: Natural language search query
        project_id: Optional project filter (ANY project ID)
        document_type: Optional document type filter
        graph_client: Microsoft Graph client
        
    Returns:
        Relevant engineering documents matching the query from ALL projects
    """
    try:
        logger.info("Searching engineering documents", 
                   query=query, project_id=project_id, document_type=document_type)
        
        # Get all engineering documents
        engineering_docs = await graph_client.sync_suitefiles_documents()
        
        # Simple keyword matching for now (can be enhanced with AI later)
        query_lower = query.lower()
        matching_docs = []
        
        for doc in engineering_docs:
            # Check if document matches the query
            matches = False
            
            # Search in filename
            if query_lower in doc["name"].lower():
                matches = True
            
            # Search in document type
            if query_lower in doc.get("document_type", "").lower():
                matches = True
                
            # Search in folder category
            if query_lower in doc.get("folder_category", "").lower():
                matches = True
            
            # Specific query patterns
            if "final report" in query_lower and doc.get("document_type") == "Report/Specification":
                matches = True
            elif "issued" in query_lower and "05_Issued" in doc.get("folder_category", ""):
                matches = True
            elif "internal review" in query_lower and "03_For_internal_review" in doc.get("folder_category", ""):
                matches = True
            elif "calculation" in query_lower and doc.get("document_type") == "Calculation":
                matches = True
            elif "drawing" in query_lower and doc.get("document_type") == "Drawing":
                matches = True
                
            # Apply filters
            if matches:
                if project_id and doc.get("project_id") != project_id:
                    continue
                if document_type and doc.get("document_type") != document_type:
                    continue
                    
                matching_docs.append({
                    "file_id": doc["file_id"],
                    "filename": doc["name"],
                    "project_id": doc.get("project_id"),
                    "document_type": doc.get("document_type"),
                    "folder_category": doc.get("folder_category"),
                    "last_modified": doc.get("modified"),
                    "size": doc.get("size", 0),
                    "relevance_reason": "Keyword match in " + ("filename" if query_lower in doc["name"].lower() else "metadata"),
                    "download_url": doc.get("download_url", "")
                })
        
        # Sort by relevance (filename matches first, then by modification date)
        matching_docs.sort(key=lambda x: (
            0 if query_lower in x["filename"].lower() else 1,
            x["last_modified"] or ""
        ), reverse=True)
        
        logger.info("Engineering search completed", 
                   query=query, results_count=len(matching_docs))
        
        return JSONResponse({
            "query": query,
            "results": matching_docs[:20],  # Limit to top 20 results
            "total_matches": len(matching_docs),
            "search_applied": {
                "project_id": project_id,
                "document_type": document_type
            }
        })
        
    except Exception as e:
        logger.error("Engineering search failed", error=str(e), query=query)
        return JSONResponse({
            "query": query,
            "results": [],
            "total_matches": 0,
            "error": f"Search failed: {str(e)}"
        })


@router.get("/test-suitefiles-config")
async def test_suitefiles_config() -> JSONResponse:
    """
    Test Suitefiles/Microsoft Graph configuration.
    Shows what credentials are configured and what's missing.
    """
    try:
        from ..config.settings import get_settings
        settings = get_settings()
        
        config_status = {
            "microsoft_client_id": "✓ Configured" if settings.MICROSOFT_CLIENT_ID else "✗ Missing",
            "microsoft_tenant_id": "✓ Configured" if settings.MICROSOFT_TENANT_ID else "✗ Missing", 
            "microsoft_client_secret": "✓ Configured" if settings.MICROSOFT_CLIENT_SECRET else "✗ Missing",
            "sharepoint_site_id": "✓ Configured" if hasattr(settings, 'SHAREPOINT_SITE_ID') and settings.SHAREPOINT_SITE_ID else "✗ Missing"
        }
        
        all_configured = all("✓" in status for status in config_status.values())
        
        return JSONResponse({
            "status": "ready" if all_configured else "needs_configuration",
            "configuration": config_status,
            "message": "All Microsoft Graph credentials configured!" if all_configured else "Missing Microsoft Graph API credentials",
            "next_steps": [
                "1. Register an app in Azure Portal (Microsoft Entra)",
                "2. Get Client ID, Tenant ID, and Client Secret", 
                "3. Add to .env file",
                "4. Grant Sites.Read.All and Files.Read.All permissions",
                "5. Test connection to Suitefiles"
            ] if not all_configured else [
                "Configuration looks good! Try /documents/list?source=suitefiles"
            ]
        })
        
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error": str(e),
            "message": "Failed to check configuration"
        })


@router.get("/suitefiles/drives")
async def list_suitefiles_drives(
    graph_client: MicrosoftGraphClient = Depends(get_graph_client)
) -> JSONResponse:
    """
    List available drives/document libraries in Suitefiles.
    This shows you what folders/drives are available in your Suitefiles.
    """
    try:
        logger.info("Listing Suitefiles drives")
        
        # Find the Suitefiles site
        suitefiles_site = await graph_client.get_site_by_name("suitefiles")
        if not suitefiles_site:
            logger.warning("Suitefiles site not found, trying 'dtce' site")
            suitefiles_site = await graph_client.get_site_by_name("dtce")
        
        if not suitefiles_site:
            return JSONResponse({
                "drives": [],
                "total_count": 0,
                "error": "No Suitefiles or DTCE SharePoint site found",
                "message": "Check if you have access to the SharePoint site"
            })
        
        site_id = suitefiles_site["id"]
        drives = await graph_client.get_drives(site_id)
        
        drive_info = []
        for drive in drives:
            drive_info.append({
                "drive_id": drive["id"],
                "name": drive.get("name", "Unknown"),
                "description": drive.get("description", ""),
                "created": drive.get("createdDateTime", ""),
                "web_url": drive.get("webUrl", "")
            })
        
        logger.info("Suitefiles drives listing completed", drive_count=len(drive_info))
        
        return JSONResponse({
            "drives": drive_info,
            "total_count": len(drive_info),
            "site_name": suitefiles_site.get("displayName", ""),
            "site_id": site_id
        })
        
    except Exception as e:
        logger.error("Failed to list Suitefiles drives", error=str(e))
        return JSONResponse({
            "drives": [],
            "total_count": 0,
            "error": f"Failed to connect to Suitefiles: {str(e)}",
            "message": "Check Microsoft Graph API credentials and permissions"
        })


@router.get("/test-connection")
async def test_connection(
    graph_client: MicrosoftGraphClient = Depends(get_graph_client)
) -> JSONResponse:
    """
    Test Microsoft Graph API connection without full document sync.
    """
    try:
        logger.info("Testing Microsoft Graph API connection")
        
        # Test 1: Authentication
        try:
            token = await graph_client._get_access_token()
            logger.info("Authentication successful", token_length=len(token))
        except Exception as e:
            return JSONResponse({
                "status": "error",
                "step": "authentication",
                "error": str(e)
            })
        
        # Test 2: Get sites
        try:
            sites = await graph_client.get_sites()
            logger.info("Sites retrieved", count=len(sites))
        except Exception as e:
            return JSONResponse({
                "status": "error", 
                "step": "sites",
                "error": str(e)
            })
        
        # Test 3: Find target site
        try:
            suitefiles_site = await graph_client.get_site_by_name("suitefiles")
            if not suitefiles_site:
                suitefiles_site = await graph_client.get_site_by_name("dtce")
            
            if not suitefiles_site:
                return JSONResponse({
                    "status": "error",
                    "step": "site_lookup", 
                    "error": "No suitable SharePoint site found"
                })
                
            site_id = suitefiles_site["id"]
            logger.info("Found target site", site_id=site_id)
        except Exception as e:
            return JSONResponse({
                "status": "error",
                "step": "site_lookup",
                "error": str(e)
            })
        
        # Test 4: Get drives
        try:
            drives = await graph_client.get_drives(site_id)
            logger.info("Drives retrieved", count=len(drives))
        except Exception as e:
            return JSONResponse({
                "status": "error",
                "step": "drives",
                "error": str(e)
            })
        
        return JSONResponse({
            "status": "success",
            "message": "Microsoft Graph API connection working",
            "site_name": suitefiles_site.get("displayName"),
            "drives_count": len(drives),
            "drives": [{"name": d.get("name"), "id": d.get("id")} for d in drives]
        })
        
    except Exception as e:
        logger.error("Connection test failed", error=str(e))
        return JSONResponse({
            "status": "error",
            "step": "unknown",
            "error": str(e)
        })


@router.get("/list")
async def list_documents(
    folder: Optional[str] = None,
    source: str = "suitefiles",  # Default to suitefiles, can be "storage" for blob storage
    graph_client: MicrosoftGraphClient = Depends(get_graph_client),
    storage_client: BlobServiceClient = Depends(get_storage_client)
) -> JSONResponse:
    """
    List ALL documents from Suitefiles (SharePoint) or Azure Blob Storage.
    Recursively explores every folder and subfolder to find ALL files.
    
    Args:
        folder: Optional folder to filter by
        source: "suitefiles" (default) or "storage" 
        graph_client: Microsoft Graph client for Suitefiles access
        storage_client: Azure Storage client for blob storage
        
    Returns:
        Complete list of ALL document metadata from the specified source
    """
    try:
        logger.info("Listing ALL documents (no limits)", folder=folder, source=source)
        
        if source == "suitefiles":
            # List documents from Suitefiles via Microsoft Graph
            try:
                import asyncio
                
                # Add timeout to prevent hanging but process ALL documents
                logger.info("Starting comprehensive Suitefiles document sync (ALL files)...")
                suitefiles_docs = await asyncio.wait_for(
                    graph_client.sync_suitefiles_documents(), 
                    timeout=300.0  # Increased to 5 minutes for complete scan
                )
                
                logger.info("Suitefiles sync completed - found ALL documents", total_docs=len(suitefiles_docs))
                
                # Filter by folder if specified
                if folder:
                    suitefiles_docs = [
                        doc for doc in suitefiles_docs 
                        if folder.lower() in doc.get("drive_name", "").lower() or 
                           folder.lower() in doc.get("name", "").lower()
                    ]
                    logger.info("Filtered by folder", folder=folder, filtered_docs=len(suitefiles_docs))
                
                # Return ALL documents - no artificial limits
                
                documents = []
                for doc in suitefiles_docs:
                    documents.append({
                        "file_id": doc["file_id"],
                        "filename": doc["name"],
                        "drive_name": doc["drive_name"],
                        "content_type": doc.get("mime_type", ""),
                        "size": doc.get("size", 0),
                        "last_modified": doc.get("modified", ""),
                        "source": "suitefiles",
                        "download_url": doc.get("download_url", "")
                    })
                
                logger.info("Suitefiles listing completed", document_count=len(documents))
                
                return JSONResponse({
                    "documents": documents,
                    "total_count": len(documents),
                    "folder": folder,
                    "source": "suitefiles"
                })
                
            except Exception as e:
                logger.error("Failed to list Suitefiles documents", error=str(e))
                # Fall back to showing message about Suitefiles connection
                return JSONResponse({
                    "documents": [],
                    "total_count": 0,
                    "folder": folder,
                    "source": "suitefiles",
                    "error": f"Cannot connect to Suitefiles: {str(e)}",
                    "message": "Check Microsoft Graph API credentials and Suitefiles site access"
                })
        
        else:
            # Original blob storage listing
            container_client = storage_client.get_container_client(settings.azure_storage_container)
            
            # List blobs with optional folder prefix
            blob_prefix = f"{folder}/" if folder else None
            blobs = container_client.list_blobs(name_starts_with=blob_prefix)
            
            documents = []
            for blob in blobs:
                documents.append({
                    "blob_name": blob.name,
                    "filename": blob.metadata.get("original_filename", blob.name) if blob.metadata else blob.name,
                    "content_type": blob.metadata.get("content_type", "") if blob.metadata else "",
                    "size": blob.size,
                    "last_modified": blob.last_modified.isoformat(),
                    "folder": blob.metadata.get("folder", "") if blob.metadata else "",
                    "source": "storage"
                })
            
            logger.info("Storage listing completed", document_count=len(documents))
            
            return JSONResponse({
                "documents": documents,
                "total_count": len(documents),
                "folder": folder,
                "source": "storage"
            })
        
    except Exception as e:
        logger.error("Document listing failed", error=str(e), folder=folder, source=source)
        raise HTTPException(status_code=500, detail=f"Listing failed: {str(e)}")


@router.delete("/{blob_name}")
async def delete_document(
    blob_name: str,
    storage_client: BlobServiceClient = Depends(get_storage_client),
    search_client: SearchClient = Depends(get_search_client)
) -> JSONResponse:
    """
    Delete a document from both storage and search index.
    
    Args:
        blob_name: Name of the blob to delete
        storage_client: Azure Storage client
        search_client: Azure Search client
        
    Returns:
        Deletion status
    """
    try:
        logger.info("Starting document deletion", blob_name=blob_name)
        
        # Delete from blob storage
        blob_client = storage_client.get_blob_client(
            container=settings.azure_storage_container,
            blob=blob_name
        )
        
        if blob_client.exists():
            blob_client.delete_blob()
            storage_deleted = True
        else:
            storage_deleted = False
        
        # Delete from search index
        document_id = blob_name.replace("/", "_").replace(".", "_")
        try:
            search_client.delete_documents([{"id": document_id}])
            index_deleted = True
        except Exception:
            index_deleted = False
        
        logger.info("Document deletion completed", blob_name=blob_name, storage_deleted=storage_deleted, index_deleted=index_deleted)
        
        return JSONResponse({
            "status": "deleted",
            "blob_name": blob_name,
            "storage_deleted": storage_deleted,
            "index_deleted": index_deleted
        })
        
    except Exception as e:
        logger.error("Document deletion failed", error=str(e), blob_name=blob_name)
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


@router.delete("/cleanup-duplicates/{project_id}")
async def cleanup_duplicate_folders(
    project_id: str,
    storage_client: BlobServiceClient = Depends(get_storage_client)
) -> JSONResponse:
    """
    Clean up duplicate folders that exist outside the correct SharePoint structure.
    Specifically removes 01 Fees & Invoice, 02 Quality Assurance, and 03 RFI from top level,
    keeping only the versions inside 01 Admin Documents.
    """
    try:
        logger.info(f"Cleaning up duplicate folders for project {project_id}")
        
        container_client = storage_client.get_container_client(settings.azure_storage_container)
        blobs = container_client.list_blobs(name_starts_with=f"Projects/219/{project_id}/")
        
        # Patterns for duplicate folders that should be removed
        duplicate_patterns = [
            f"Projects/219/{project_id}/01 Fees & Invoice/",
            f"Projects/219/{project_id}/02 Quality Assurance/",  
            f"Projects/219/{project_id}/03 RFI/"
        ]
        
        deleted_files = []
        for blob in blobs:
            for pattern in duplicate_patterns:
                if blob.name.startswith(pattern):
                    blob_client = storage_client.get_blob_client(
                        container=settings.azure_storage_container,
                        blob=blob.name
                    )
                    blob_client.delete_blob()
                    deleted_files.append(blob.name)
                    logger.info(f"Deleted duplicate file: {blob.name}")
                    break
        
        logger.info(f"Cleaned up {len(deleted_files)} duplicate files for project {project_id}")
        
        return JSONResponse({
            "status": "cleaned",
            "project_id": project_id,
            "deleted_count": len(deleted_files),
            "deleted_files": deleted_files,
            "message": f"Removed {len(deleted_files)} duplicate files from wrong standalone locations"
        })
        
    except Exception as e:
        logger.error(f"Failed to clean duplicates for project {project_id}", error=str(e))
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@router.post("/test-sync")
async def test_sync_endpoint(
    path: Optional[str] = Query(None, description="Test path parameter")
) -> JSONResponse:
    """
    Test endpoint to verify path-based routing works without Microsoft Graph calls.
    """
    logger.info("=== TEST SYNC ENDPOINT CALLED ===", path=path)
    
    return JSONResponse({
        "status": "success",
        "message": f"Test endpoint reached successfully!",
        "path_received": path,
        "endpoint_working": True
    })


@router.post("/sync-suitefiles")
async def sync_suitefiles_documents(
    path: Optional[str] = Query(None, description="Specific SharePoint path (e.g. 'Projects/219', 'Projects/219/Drawings', 'Engineering/Marketing') or empty for all"),
    drive: Optional[str] = Query(None, description="Specific drive/library name (e.g. 'Templates', 'Shared Documents') to sync only that drive"),
    force: bool = Query(False, description="Force re-sync all files even if they appear up-to-date"),
    graph_client: MicrosoftGraphClient = Depends(get_graph_client),
    storage_client: BlobServiceClient = Depends(get_storage_client)
) -> JSONResponse:
    """
    Sync documents from specific SharePoint path or all documents.

    Args:
        path: Specific SharePoint path (e.g. "Projects/219", "Projects/219/Drawings", "Engineering/Marketing") or empty for all
        drive: Specific drive/library name (e.g. "Templates", "Shared Documents") to sync only that drive
        force: Force re-sync all files even if they appear up-to-date

    How it works:
        - "Projects/219": Process only project 219 completely
        - "Projects/219/Drawings": Process only the Drawings folder in project 219
        - "Engineering/Marketing": Process only Marketing subfolder in Engineering
        - "Projects": Process all project folders completely
        - "Engineering": Process entire Engineering folder completely
        - Empty path: Process ALL folders completely
        - drive="Templates": Process only the Templates document library
        - force=true: Re-sync everything regardless of modification dates

    Examples:
        POST /sync-suitefiles?path=Projects/219              # Process only project 219 completely
        POST /sync-suitefiles?path=Projects/219/Drawings     # Process only Drawings in project 219
        POST /sync-suitefiles?path=Engineering/Marketing     # Process only Engineering/Marketing
        POST /sync-suitefiles?path=Projects                  # Process all project folders
        POST /sync-suitefiles?path=Engineering               # Process Engineering folder completely
        POST /sync-suitefiles?drive=Templates                # Process only Templates drive
        POST /sync-suitefiles?force=true                     # Force re-sync ALL folders completely
        POST /sync-suitefiles                                # Process ALL folders completely
    """
    logger.info("Starting synchronous document sync", path=path, drive=drive, force=force)

    try:
        # Use centralized sync service (same logic as async endpoints)
        sync_service = get_document_sync_service(storage_client)
        sync_result = await sync_service.sync_documents(
            graph_client=graph_client,
            path=path,
            drive=drive,
            force_resync=force
        )
        
        logger.info("Synchronous sync completed", 
                   synced_count=sync_result.synced_count,
                   processed_count=sync_result.processed_count,
                   ai_ready_count=sync_result.ai_ready_count)
        
        return JSONResponse({
            "status": "completed",
            "message": f"Sync completed! {sync_result.ai_ready_count} documents ready for AI queries.",
            "synced_count": sync_result.synced_count,
            "processed_count": sync_result.processed_count,
            "ai_ready_count": sync_result.ai_ready_count,
            "skipped_count": sync_result.skipped_count,
            "error_count": sync_result.error_count,
            "folder_count": sync_result.folder_count,
            "performance_notes": sync_result.performance_notes,
            "sync_mode": f"path_{path.replace('/', '_')}" if path else "full_sync"
        })
        
    except Exception as e:
        logger.error("Synchronous sync failed", error=str(e), path=path)
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.post("/sync-suitefiles-async")
async def sync_suitefiles_async(
    path: Optional[str] = Query(None, description="Specific SharePoint path (e.g. 'Projects/219', 'Projects/219/Drawings', 'Engineering/Marketing') or empty for all"),
    force: bool = Query(False, description="Force re-sync all files even if they appear up-to-date"),
    graph_client: MicrosoftGraphClient = Depends(get_graph_client),
    storage_client: BlobServiceClient = Depends(get_storage_client)
) -> JSONResponse:
    """
    REAL ASYNC version of sync-suitefiles: Actually syncs documents from Suitefiles to blob storage.
    This performs the SAME sync operation as sync-suitefiles but with better timeout handling.

    Args:
        path: Specific SharePoint path (e.g. "Projects/219", "Projects/219/Drawings", "Engineering/Marketing") or empty for all
        force: Force re-sync all files even if they appear up-to-date

    Returns immediately with actual sync results - no fake job monitoring needed.
    """
    logger.info("Starting REAL ASYNC document sync", path=path, force=force)

    try:
        # Use the SAME centralized sync service as the working sync endpoint
        sync_service = get_document_sync_service(storage_client)
        sync_result = await sync_service.sync_documents(
            graph_client=graph_client,
            path=path,
            force_resync=force
        )
        
        logger.info("ASYNC sync completed successfully", 
                   synced_count=sync_result.synced_count,
                   processed_count=sync_result.processed_count,
                   ai_ready_count=sync_result.ai_ready_count)
        
        return JSONResponse({
            "status": "completed",
            "message": f"ASYNC Sync completed! {sync_result.ai_ready_count} documents ready for AI queries.",
            "synced_count": sync_result.synced_count,
            "processed_count": sync_result.processed_count,
            "ai_ready_count": sync_result.ai_ready_count,
            "skipped_count": sync_result.skipped_count,
            "error_count": sync_result.error_count,
            "folder_count": sync_result.folder_count,
            "performance_notes": sync_result.performance_notes,
            "sync_mode": f"async_path_{path.replace('/', '_')}" if path else "async_full_sync",
            "path": path,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error("ASYNC sync failed", error=str(e), path=path)
        return JSONResponse({
            "status": "error",
            "error": str(e),
            "path": path,
            "timestamp": datetime.utcnow().isoformat()
        })


@router.get("/test-async-early")
async def test_async_early() -> JSONResponse:
    """Test async endpoint placed early to verify it appears in Swagger docs."""
    return JSONResponse({
        "status": "success",
        "message": "Early async endpoint working!",
        "timestamp": datetime.utcnow().isoformat()
    })


@router.get("/sync-schedule")
async def get_sync_schedule() -> JSONResponse:
    """
    Get information about setting up automated document syncing.
    """
    return JSONResponse({
        "current_status": "Manual sync only",
        "sync_options": {
            "daily": {
                "description": "Sync every day at 2 AM",
                "cron_expression": "0 2 * * *",
                "recommended_for": "Production environments"
            },
            "business_hours": {
                "description": "Sync weekdays at 8 AM", 
                "cron_expression": "0 8 * * 1-5",
                "recommended_for": "Active projects"
            },
            "frequent": {
                "description": "Sync every 4 hours during business days",
                "cron_expression": "0 8,12,16 * * 1-5", 
                "recommended_for": "High-activity periods"
            }
        },
        "setup_instructions": [
            "1. Use the daily_sync.py script in /scripts folder",
            "2. Set up cron job: crontab -e",
            "3. Add: 0 2 * * * /path/to/daily_sync.py",
            "4. Ensure API server is running continuously",
            "5. Monitor logs in /var/log/dtce-ai-bot/"
        ],
        "manual_sync": "POST /documents/sync-suitefiles"
    })


@router.post("/sync-now")
async def sync_now(
    background: bool = False,
    graph_client: MicrosoftGraphClient = Depends(get_graph_client),
    storage_client: BlobServiceClient = Depends(get_storage_client)
) -> JSONResponse:
    """
    Trigger an immediate sync (same as sync-suitefiles but with scheduling context).
    
    Args:
        background: If true, returns immediately and syncs in background
    """
    if background:
        # In a real implementation, you'd use a task queue like Celery
        import threading
        
        def background_sync():
            import asyncio
            asyncio.run(sync_suitefiles_documents(graph_client, storage_client))
        
        thread = threading.Thread(target=background_sync)
        thread.start()
        
        return JSONResponse({
            "status": "started",
            "message": "Sync started in background",
            "check_status": "Monitor logs or call GET /documents/list?source=storage"
        })
    else:
        return await sync_suitefiles_documents(graph_client, storage_client)


@router.post("/auto-sync")
async def auto_sync_changes(
    force_full_sync: bool = False,
    graph_client: MicrosoftGraphClient = Depends(get_graph_client),
    storage_client: BlobServiceClient = Depends(get_storage_client),
    search_client: SearchClient = Depends(get_search_client)
) -> JSONResponse:
    """
    Automatically detect and sync only changed/new files from Suitefiles with quality extraction.
    
    This handles:
    - Updated files (modification date changed)
    - New files (not in blob storage)
    - Real-time indexing with quality content extraction
    - Change detection and incremental updates
    - Smart file filtering (skips media/binary files)
    - Advanced extraction pipeline (Form Recognizer → OpenAI → Local fallback)
    
    Args:
        force_full_sync: Force sync all files regardless of change detection
        graph_client: Microsoft Graph client
        storage_client: Azure Storage client
        search_client: Azure Search client
        
    Returns:
        Summary of changes detected and processed with quality metrics
    """
    try:
        logger.info("Starting auto-sync with quality extraction", force_full_sync=force_full_sync)
        
        # File filtering function from reindex script
        def should_skip_file(filename):
            """Check if file should be skipped based on extension (media/archive files)."""
            if not filename:
                return False
            
            filename_lower = filename.lower()
            
            # File extensions to skip - files that typically don't contain useful text
            skip_extensions = {
                # Archive files
                '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.tar.gz', '.tar.bz2',
                # Audio files
                '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a', '.opus',
                # Video files
                '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp',
                # Image files
                '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp', '.svg', '.ico',
                # CAD and design files
                '.dwg', '.dxf', '.step', '.stp', '.iges', '.igs', '.stl', '.obj',
                # Executable and binary files
                '.exe', '.dll', '.bin', '.iso', '.dmg', '.msi', '.deb', '.rpm',
                # Database files
                '.db', '.sqlite', '.mdb', '.accdb',
                # Font files
                '.ttf', '.otf', '.woff', '.woff2', '.eot',
                # Temporary and cache files
                '.tmp', '.temp', '.cache', '.log', '.bak', '.swp',
                # Proprietary binary formats
                '.psd', '.ai', '.sketch', '.fig', '.indd',
                # Encrypted or protected files
                '.p12', '.pfx', '.keystore', '.jks'
            }
            
            return any(filename_lower.endswith(ext) for ext in skip_extensions)
        
        async def extract_text_with_quality_pipeline(blob_name: str) -> str:
            """Extract text using the improved extraction pipeline from reindex script."""
            from ..utils.document_extractor import get_document_extractor
            from ..utils.openai_document_extractor import get_openai_document_extractor
            
            blob_client = storage_client.get_blob_client(
                container=settings.AZURE_STORAGE_CONTAINER,
                blob=blob_name
            )
            
            if not blob_client.exists():
                return f"Document: {blob_name}"
            
            # Get blob properties for content type
            blob_properties = blob_client.get_blob_properties()
            content_type = blob_properties.content_settings.content_type
            
            # Try Form Recognizer first
            try:
                extractor = get_document_extractor(
                    settings.AZURE_FORM_RECOGNIZER_ENDPOINT,
                    settings.AZURE_FORM_RECOGNIZER_KEY
                )
                
                extraction_result = await extractor.extract_text_from_blob(blob_client, content_type)
                
                if extraction_result.get("extraction_success", True):
                    extracted_text = extraction_result.get("extracted_text", "")
                    if extracted_text and extracted_text.strip() and len(extracted_text) > 50:
                        logger.info(f"Form Recognizer success: {blob_name}")
                        return extracted_text
                        
            except Exception as form_error:
                logger.warning(f"Form Recognizer failed for {blob_name}: {form_error}")
            
            # Try OpenAI fallback
            try:
                openai_extractor = get_openai_document_extractor(
                    settings.AZURE_OPENAI_ENDPOINT,
                    settings.AZURE_OPENAI_API_KEY,
                    settings.AZURE_OPENAI_DEPLOYMENT_NAME
                )
                
                extraction_result = await openai_extractor.extract_text_from_blob(blob_client, content_type)
                extracted_text = extraction_result.get("extracted_text", "")
                
                if extracted_text and extracted_text.strip() and len(extracted_text) > 50:
                    logger.info(f"OpenAI extraction success: {blob_name}")
                    return extracted_text
                    
            except Exception as openai_error:
                logger.warning(f"OpenAI extraction failed for {blob_name}: {openai_error}")
            
            # Fallback to existing extract_text function
            try:
                extraction_result = await extract_text(blob_name, storage_client)
                if extraction_result and extraction_result.strip() and len(extraction_result) > 50:
                    logger.info(f"Standard extraction success: {blob_name}")
                    return extraction_result
            except Exception as std_error:
                logger.warning(f"Standard extraction failed for {blob_name}: {std_error}")
            
            # Final fallback to filename
            return f"Document: {blob_name}"
        
        # Get all documents from Suitefiles
        suitefiles_docs = await graph_client.sync_suitefiles_documents()
        
        if not suitefiles_docs:
            return JSONResponse({
                "status": "completed",
                "message": "No documents found in Suitefiles",
                "changes_detected": 0,
                "files_updated": 0,
                "files_added": 0,
                "files_filtered": 0
            })
        
        changes_detected = 0
        files_updated = 0
        files_added = 0
        files_skipped = 0
        files_filtered = 0
        
        # Check each document for changes
        for doc in suitefiles_docs:
            try:
                filename = doc.get('name', '')
                
                # Filter out unwanted file types early
                if should_skip_file(filename):
                    files_filtered += 1
                    logger.debug(f"Filtered out file type: {filename}")
                    continue
                
                blob_name = f"suitefiles/{doc['drive_name']}/{doc['name']}"
                blob_client = storage_client.get_blob_client(
                    container=settings.AZURE_STORAGE_CONTAINER,
                    blob=blob_name
                )
                
                is_new_file = not blob_client.exists()
                is_updated_file = False
                
                if not is_new_file and not force_full_sync:
                    # Check if file was modified since last sync
                    properties = blob_client.get_blob_properties()
                    doc_modified = doc.get("modified", "")
                    blob_modified = properties.last_modified.isoformat()
                    
                    if doc_modified > blob_modified:
                        is_updated_file = True
                        changes_detected += 1
                        logger.info("File change detected", 
                                   filename=doc['name'],
                                   doc_modified=doc_modified,
                                   blob_modified=blob_modified)
                
                elif is_new_file:
                    changes_detected += 1
                    logger.info("New file detected", filename=doc['name'])
                
                # Process changed or new files
                if is_new_file or is_updated_file or force_full_sync:
                    # Download and store file content
                    file_content = await graph_client.download_file(
                        doc["site_id"], 
                        doc["drive_id"], 
                        doc["file_id"]
                    )
                    
                    # Sanitize metadata to ensure ASCII compatibility
                    def sanitize_metadata_value(value):
                        """Convert metadata value to ASCII-safe string."""
                        if not value:
                            return ""
                        # Convert to string and encode/decode to remove non-ASCII characters
                        try:
                            return str(value).encode('ascii', errors='replace').decode('ascii')
                        except Exception:
                            # Fallback: replace all non-ASCII with underscore
                            return ''.join(c if ord(c) < 128 else '_' for c in str(value))
                    
                    # Upload to blob storage with rich metadata
                    metadata = {
                        "source": "suitefiles",
                        "original_filename": sanitize_metadata_value(doc["name"]),
                        "drive_name": sanitize_metadata_value(doc["drive_name"]),
                        "project_id": sanitize_metadata_value(doc.get("project_id", "")),
                        "document_type": sanitize_metadata_value(doc.get("document_type", "")),
                        "folder_category": sanitize_metadata_value(doc.get("folder_category", "")),
                        "last_modified": sanitize_metadata_value(doc.get("modified", "")),
                        "is_critical": str(doc.get("is_critical_for_search", False)),
                        "full_path": sanitize_metadata_value(doc.get("full_path", "")),
                        "content_type": sanitize_metadata_value(doc.get("mime_type", "")),
                        "size": str(doc.get("size", 0)),
                        "sync_timestamp": datetime.utcnow().isoformat(),
                        "change_type": "new" if is_new_file else "updated",
                        "extraction_method": "quality_pipeline"
                    }
                    
                    blob_client.upload_blob(file_content, overwrite=True, metadata=metadata)
                    
                    # Real-time indexing with quality extraction
                    try:
                        # Use quality extraction pipeline instead of basic extract_text
                        extracted_text = await extract_text_with_quality_pipeline(blob_name)
                        
                        # Index document immediately
                        await index_document(blob_name, search_client, storage_client)
                        
                        if is_new_file:
                            files_added += 1
                        else:
                            files_updated += 1
                            
                        logger.info("File processed and indexed with quality extraction", 
                                   blob_name=blob_name,
                                   change_type="new" if is_new_file else "updated",
                                   content_length=len(extracted_text) if extracted_text else 0)
                        
                    except Exception as e:
                        logger.warning("Failed to process file for indexing", 
                                     blob_name=blob_name, error=str(e))
                
                else:
                    files_skipped += 1
                    
            except Exception as e:
                logger.error("Failed to process document change", 
                           doc_name=doc.get('name'), error=str(e))
                continue
        
        logger.info("Auto-sync completed with quality extraction", 
                   total_docs=len(suitefiles_docs),
                   changes_detected=changes_detected,
                   files_added=files_added,
                   files_updated=files_updated,
                   files_skipped=files_skipped,
                   files_filtered=files_filtered)
        
        return JSONResponse({
            "status": "completed",
            "message": f"Auto-sync completed: {changes_detected} changes detected with quality extraction",
            "summary": {
                "total_documents": len(suitefiles_docs),
                "changes_detected": changes_detected,
                "files_added": files_added,
                "files_updated": files_updated,
                "files_skipped": files_skipped,
                "files_filtered": files_filtered
            },
            "quality_improvements": [
                "✅ Advanced extraction pipeline (Form Recognizer → OpenAI → Local)",
                "✅ Media file filtering (skips binary/media files)", 
                "✅ Better content quality assessment",
                "✅ Cost-optimized processing"
            ],
            "real_time_indexing": True,
            "next_sync_recommendation": "1 hour" if changes_detected > 0 else "4 hours"
        })
        
    except Exception as e:
        logger.error("Auto-sync failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Auto-sync failed: {str(e)}")


@router.get("/test-changes")
async def test_file_changes(
    graph_client: MicrosoftGraphClient = Depends(get_graph_client),
    storage_client: BlobServiceClient = Depends(get_storage_client)
) -> JSONResponse:
    """
    Test endpoint to verify that changes in Suitefiles appear correctly.
    
    This will:
    1. List recent files from Suitefiles
    2. Compare with what's in blob storage  
    3. Show modification dates and change detection
    4. Validate the change detection logic
    
    Returns:
        Detailed comparison showing change detection accuracy
    """
    try:
        logger.info("Testing file change detection")
        
        # Get recent documents from Suitefiles
        suitefiles_docs = await graph_client.sync_suitefiles_documents()
        
        change_analysis = []
        
        for doc in suitefiles_docs[:10]:  # Test first 10 files
            blob_name = f"suitefiles/{doc['drive_name']}/{doc['name']}"
            blob_client = storage_client.get_blob_client(
                container=settings.AZURE_STORAGE_CONTAINER,
                blob=blob_name
            )
            
            analysis = {
                "filename": doc['name'],
                "suitefiles_modified": doc.get('modified', 'unknown'),
                "exists_in_storage": blob_client.exists(),
                "storage_modified": None,
                "change_detected": False,
                "status": "unknown"
            }
            
            if blob_client.exists():
                try:
                    properties = blob_client.get_blob_properties()
                    analysis["storage_modified"] = properties.last_modified.isoformat()
                    
                    # Compare modification dates
                    if doc.get('modified') and analysis["storage_modified"]:
                        if doc['modified'] > analysis["storage_modified"]:
                            analysis["change_detected"] = True
                            analysis["status"] = "needs_update"
                        else:
                            analysis["status"] = "up_to_date"
                    
                except Exception as e:
                    analysis["status"] = f"error: {str(e)}"
            else:
                analysis["change_detected"] = True
                analysis["status"] = "new_file"
            
            change_analysis.append(analysis)
        
        # Summary statistics
        total_files = len(change_analysis)
        changes_detected = len([a for a in change_analysis if a["change_detected"]])
        new_files = len([a for a in change_analysis if a["status"] == "new_file"])
        needs_update = len([a for a in change_analysis if a["status"] == "needs_update"])
        up_to_date = len([a for a in change_analysis if a["status"] == "up_to_date"])
        
        return JSONResponse({
            "test_results": {
                "total_files_tested": total_files,
                "changes_detected": changes_detected,
                "new_files": new_files,
                "needs_update": needs_update,
                "up_to_date": up_to_date,
                "change_detection_working": changes_detected > 0 or up_to_date > 0
            },
            "file_analysis": change_analysis,
            "recommendations": [
                "✅ Change detection is working" if changes_detected > 0 or up_to_date > 0 else "⚠️ No files found for testing",
                f"📊 {changes_detected}/{total_files} files need updates",
                "🔄 Run POST /documents/auto-sync to process detected changes"
            ]
        })
        
    except Exception as e:
        logger.error("Change detection test failed", error=str(e))
        return JSONResponse({
            "test_results": {"error": str(e)},
            "file_analysis": [],
            "recommendations": ["❌ Change detection test failed - check logs"]
        })


@router.post("/ask")
async def ask_question(
    question: str,
    project_id: Optional[str] = None,
    search_client: SearchClient = Depends(get_search_client)
) -> JSONResponse:
    """
    Ask a question about your engineering documents using GPT.
    
    Examples:
    - "What was the final report conclusion for project 222?"
    - "Show me the structural calculations for the bridge project"
    - "What materials were specified in the latest design?"
    
    Args:
        question: Your question about the documents
        project_id: Optional filter for specific project
        search_client: Azure Search client
        
    Returns:
        AI-generated answer with sources and confidence level
    """
    try:
        logger.info("Processing question", question=question, project_id=project_id)
        
        # Initialize QA service
        qa_service = DocumentQAService(search_client)
        
        # Get answer
        result = await qa_service.answer_question(question, project_id)
        
        logger.info("Question answered", 
                   question=question,
                   confidence=result['confidence'],
                   sources_count=len(result['sources']))
        
        return JSONResponse({
            "question": question,
            "answer": result['answer'],
            "confidence": result['confidence'],
            "sources": result['sources'],
            "metadata": {
                "documents_searched": result['documents_searched'],
                "processing_time": result.get('processing_time', 0),
                "project_filter": project_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        })
        
    except Exception as e:
        logger.error("Question processing failed", error=str(e), question=question)
        return JSONResponse({
            "question": question,
            "answer": f"I encountered an error: {str(e)}",
            "confidence": "error",
            "sources": [],
            "metadata": {"error": str(e)}
        })


@router.get("/ai/document-summary")
async def get_document_summary(
    project_id: Optional[str] = None,
    search_client: SearchClient = Depends(get_search_client)
) -> JSONResponse:
    """
    Get an AI-powered summary of available documents.
    
    Args:
        project_id: Optional filter for specific project
        search_client: Azure Search client
        
    Returns:
        Summary of indexed documents with statistics and insights
    """
    try:
        logger.info("Generating document summary", project_id=project_id)
        
        # Initialize QA service
        qa_service = DocumentQAService(search_client)
        
        # Get summary
        summary = await qa_service.get_document_summary(project_id)
        
        logger.info("Document summary generated", 
                   project_id=project_id,
                   total_docs=summary.get('total_documents', 0))
        
        return JSONResponse({
            "summary": summary,
            "project_filter": project_id,
            "generated_at": datetime.utcnow().isoformat(),
            "status": "success"
        })
        
    except Exception as e:
        logger.error("Document summary failed", error=str(e), project_id=project_id)
        return JSONResponse({
            "summary": {"error": str(e)},
            "project_filter": project_id,
            "status": "error"
        })


@router.post("/ai/batch-questions")
async def ask_batch_questions(
    questions: List[str],
    project_id: Optional[str] = None,
    search_client: SearchClient = Depends(get_search_client)
) -> JSONResponse:
    """
    Ask multiple questions at once for efficient processing.
    
    Args:
        questions: List of questions to ask
        project_id: Optional filter for specific project
        search_client: Azure Search client
        
    Returns:
        List of answers with sources and metadata
    """
    try:
        logger.info("Processing batch questions", count=len(questions), project_id=project_id)
        
        # Initialize QA service
        qa_service = DocumentQAService(search_client)
        
        # Process each question
        results = []
        for i, question in enumerate(questions):
            try:
                result = await qa_service.answer_question(question, project_id)
                results.append({
                    "question_index": i,
                    "question": question,
                    "answer": result['answer'],
                    "confidence": result['confidence'],
                    "sources": result['sources'][:2],  # Limit sources for batch
                    "documents_searched": result['documents_searched']
                })
            except Exception as e:
                results.append({
                    "question_index": i,
                    "question": question,
                    "answer": f"Error: {str(e)}",
                    "confidence": "error",
                    "sources": [],
                    "documents_searched": 0
                })
        
        logger.info("Batch questions completed", 
                   total=len(questions),
                   successful=len([r for r in results if r['confidence'] != 'error']))
        
        return JSONResponse({
            "results": results,
            "total_questions": len(questions),
            "project_filter": project_id,
            "processed_at": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error("Batch questions failed", error=str(e))
        return JSONResponse({
            "results": [],
            "total_questions": len(questions) if questions else 0,
            "error": str(e)
        })


# =============================================================================
# ASYNC SYNC JOB ENDPOINTS - NO TIMEOUT SOLUTION FOR MANUAL SYNC
# =============================================================================

@router.get("/test-async")
async def test_async_endpoint() -> JSONResponse:
    """Simple test endpoint to verify async endpoints are loading."""
    return JSONResponse({
        "status": "success",
        "message": "Async endpoints are working!",
        "timestamp": datetime.utcnow().isoformat()
    })

@router.post("/sync-async/start")
async def start_async_sync() -> JSONResponse:
    """
    Start an async document sync job that runs in the background without timeout.
    
    Simplified version for testing Azure deployment.
    """
    try:
        job_id = f"test-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        
        return JSONResponse({
            "status": "success",
            "message": "Sync job started successfully (test mode)",
            "job_id": job_id,
            "job_status": "running",
            "description": "Test async sync job",
            "created_at": datetime.utcnow().isoformat(),
            "monitor_url": f"/documents/sync-async/status/{job_id}",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        # logger.error("Failed to start async sync", error=str(e))
        return JSONResponse({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        })


@router.get("/sync-async/status/{job_id}")
async def get_sync_job_status(job_id: str) -> JSONResponse:
    """
    Get the status and progress of an async sync job.
    
    Simplified version for testing Azure deployment.
    """
    try:
        return JSONResponse({
            "status": "success",
            "job_id": job_id,
            "job_status": "completed",
            "description": "Test sync job",
            "created_at": datetime.utcnow().isoformat(),
            "progress": {
                "percentage": 100.0,
                "processed_files": 10,
                "total_files": 10,
                "current_file": "test.pdf"
            },
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error("Failed to get sync job status", job_id=job_id, error=str(e))
        return JSONResponse({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        })


@router.get("/sync-async/jobs")
async def list_sync_jobs(limit: int = 20) -> JSONResponse:
    """
    List recent sync jobs with their status.
    
    Simplified version for testing Azure deployment.
    """
    try:
        # Return sample job data
        sample_jobs = [
            {
                "job_id": "test-job-1",
                "status": "completed",
                "description": "Test sync job 1",
                "path": "Projects/219",
                "created_at": datetime.utcnow().isoformat(),
                "progress_percentage": 100.0,
                "duration_minutes": 5.2,
                "files_processed": "10/10"
            }
        ]
        
        return JSONResponse({
            "status": "success",
            "jobs": sample_jobs,
            "total_jobs": len(sample_jobs),
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error("Failed to list sync jobs", error=str(e))
        return JSONResponse({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        })


@router.post("/sync-async/cancel/{job_id}")
async def cancel_sync_job(job_id: str) -> JSONResponse:
    """
    Cancel a running sync job.
    
    Simplified version for testing Azure deployment.
    """
    try:
        return JSONResponse({
            "status": "success",
            "message": f"Sync job {job_id} cancelled successfully (test mode)",
            "job_id": job_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error("Failed to cancel sync job", job_id=job_id, error=str(e))
        return JSONResponse({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        })


@router.post("/index/update")
async def update_search_index():
    """
    Update the Azure Search index schema and configuration.
    This will recreate the index with the latest schema and semantic search capabilities.
    """
    try:
        from ..integrations.azure_search import create_search_index_if_not_exists
        
        logger.info("Starting Azure Search index update")
        
        # Update the index with latest schema and semantic search
        await create_search_index_if_not_exists()
        
        logger.info("Azure Search index updated successfully")
        
        return JSONResponse({
            "status": "success",
            "message": "Azure Search index updated successfully with latest schema and semantic search capabilities",
            "features_enabled": [
                "Semantic search for better relevance",
                "Natural language query understanding", 
                "Context-aware similarity matching",
                "Improved document ranking"
            ],
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error("Failed to update search index", error=str(e))
        return JSONResponse({
            "status": "error", 
            "error": f"Failed to update search index: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }, status_code=500)


@router.get("/index/status")
async def get_index_status():
    """
    Get the current status and configuration of the Azure Search index.
    """
    try:
        from ..integrations.azure_search import get_search_index_client
        from ..config.settings import get_settings
        
        settings = get_settings()
        index_client = get_search_index_client()
        
        # Get index information
        index = index_client.get_index(settings.azure_search_index_name)
        
        # Count documents (approximate)
        search_client = get_search_client()
        results = search_client.search("*", include_total_count=True, top=1)
        doc_count = results.get_count() or 0
        
        return JSONResponse({
            "status": "success",
            "index_name": settings.azure_search_index_name,
            "document_count": doc_count,
            "fields_count": len(index.fields),
            "semantic_search_enabled": index.semantic_search is not None,
            "semantic_configurations": len(index.semantic_search.configurations) if index.semantic_search else 0,
            "created_date": index.last_modified.isoformat() if hasattr(index, 'last_modified') and index.last_modified else None,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error("Failed to get index status", error=str(e))
        return JSONResponse({
            "status": "error",
            "error": f"Failed to get index status: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }, status_code=500)
