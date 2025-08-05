"""
Document processing service endpoints.
Implements document upload, indexing, text extraction, and search functionality.
"""

import os
import tempfile
from typing import List, Optional
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from fastapi.responses import JSONResponse
import structlog
from azure.storage.blob import BlobServiceClient
from azure.search.documents import SearchClient
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential

from ..config.settings import get_settings
from ..models.document import DocumentMetadata, DocumentSearchResult, DocumentUploadResponse
from ..integrations.azure_search import get_search_client
from ..integrations.azure_storage import get_storage_client
from ..utils.document_extractor import get_document_extractor
from ..integrations.microsoft_graph import get_graph_client, MicrosoftGraphClient

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
            
        # Validate file type
        allowed_extensions = {'.pdf', '.docx', '.doc', '.txt', '.md', '.py', '.js', '.ts', '.json', '.xml', '.html'}
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
        
        # Upload blob with metadata
        metadata = {
            "original_filename": file.filename,
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
        
        # Initialize document extractor
        extractor = get_document_extractor(
            settings.azure_form_recognizer_endpoint,
            settings.azure_form_recognizer_key
        )
        
        # Extract text using the enhanced extractor
        extraction_result = await extractor.extract_text_from_blob(blob_client, content_type)
        
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
        
        # Extract text (reuse extraction logic)
        try:
            extraction_response = await extract_text(blob_name, storage_client)
            
            # Handle different response types
            if hasattr(extraction_response, 'body'):
                import json
                extraction_data = json.loads(extraction_response.body.decode())
            else:
                extraction_data = extraction_response
                
        except Exception as e:
            logger.warning("Text extraction failed, indexing without content", error=str(e))
            extraction_data = {"extracted_text": ""}
        
        # Extract project information from folder path
        folder_path = metadata.get("folder", "")
        project_name = ""
        year = None
        
        if folder_path:
            path_parts = folder_path.split("/")
            # Try to extract project info from path structure
            for part in path_parts:
                if part.isdigit() and len(part) == 4:  # Year
                    year = int(part)
                elif part and not part.startswith("."):  # Potential project name
                    project_name = part
        
        # Prepare document for indexing
        document_id = blob_name.replace("/", "_").replace(".", "_").replace("-", "_")
        
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


@router.get("/engineering/project-225-test")
async def test_project_225(
    graph_client: MicrosoftGraphClient = Depends(get_graph_client)
) -> JSONResponse:
    """
    Test endpoint for Project 225 validation as mentioned in development plan.
    
    This will help validate:
    - We can extract meaningful metadata from project folder structure
    - Search returns the correct files for a specific project
    - Document categorization works correctly
    """
    try:
        logger.info("Testing Project 225 metadata extraction and search")
        
        # Get all documents and filter for project 225
        all_docs = await graph_client.sync_suitefiles_documents()
        project_225_docs = [doc for doc in all_docs if doc.get("project_id") == 225]
        
        if not project_225_docs:
            return JSONResponse({
                "status": "no_project_225_found",
                "message": "No documents found for Project 225. Check if project folder exists.",
                "total_documents_scanned": len(all_docs),
                "suggested_projects": list(set([doc.get("project_id") for doc in all_docs if doc.get("project_id")]))
            })
        
        # Categorize documents by folder type
        categorized = {}
        for doc in project_225_docs:
            folder_cat = doc.get("folder_category", "Uncategorized")
            if folder_cat not in categorized:
                categorized[folder_cat] = []
            categorized[folder_cat].append({
                "filename": doc["name"],
                "document_type": doc.get("document_type"),
                "size": doc.get("size", 0),
                "last_modified": doc.get("modified"),
                "is_critical": doc.get("is_critical_for_search", False)
            })
        
        # Count critical vs non-critical
        critical_count = sum(1 for doc in project_225_docs if doc.get("is_critical_for_search", False))
        
        # Sample searches to test
        sample_searches = []
        
        # Test: "final report for project 225"
        final_reports = [doc for doc in project_225_docs 
                        if doc.get("document_type") == "Report/Specification"]
        sample_searches.append({
            "query": "final report for project 225",
            "matches": len(final_reports),
            "sample_files": [doc["name"] for doc in final_reports[:3]]
        })
        
        # Test: "calculations for project 225"
        calculations = [doc for doc in project_225_docs 
                      if doc.get("document_type") == "Calculation"]
        sample_searches.append({
            "query": "calculations for project 225", 
            "matches": len(calculations),
            "sample_files": [doc["name"] for doc in calculations[:3]]
        })
        
        # Test: "what was issued to client for project 225"
        issued_docs = [doc for doc in project_225_docs 
                      if "05_Issued" in doc.get("folder_category", "")]
        sample_searches.append({
            "query": "what was issued to client for project 225",
            "matches": len(issued_docs),
            "sample_files": [doc["name"] for doc in issued_docs[:3]]
        })
        
        logger.info("Project 225 test completed", 
                   total_docs=len(project_225_docs),
                   critical_docs=critical_count)
        
        return JSONResponse({
            "status": "success",
            "project_id": 225,
            "summary": {
                "total_documents": len(project_225_docs),
                "critical_documents": critical_count,
                "folder_categories": list(categorized.keys()),
                "document_types": list(set([doc.get("document_type") for doc in project_225_docs]))
            },
            "categorized_documents": categorized,
            "sample_search_tests": sample_searches,
            "validation_results": {
                "metadata_extraction": "✅ Working" if project_225_docs else "❌ Failed",
                "folder_categorization": "✅ Working" if len(categorized) > 1 else "⚠️ Limited",
                "critical_document_flagging": "✅ Working" if critical_count > 0 else "⚠️ No critical docs found",
                "search_ready": "✅ Ready" if any(search["matches"] > 0 for search in sample_searches) else "⚠️ Needs content"
            }
        })
        
    except Exception as e:
        logger.error("Project 225 test failed", error=str(e))
        return JSONResponse({
            "status": "error",
            "message": f"Test failed: {str(e)}",
            "suggestions": [
                "Check if Project 225 folder exists in Suitefiles",
                "Verify folder structure matches expected pattern",
                "Ensure Microsoft Graph permissions are correct"
            ]
        })


@router.get("/engineering/search")
async def search_engineering_documents(
    query: str,
    project_id: Optional[int] = None,
    document_type: Optional[str] = None,
    graph_client: MicrosoftGraphClient = Depends(get_graph_client)
) -> JSONResponse:
    """
    Search engineering documents with natural language queries.
    
    Examples of engineer queries this should handle:
    - "Show me the final report for project 222"
    - "List all 2024 bridge projects with final specifications"
    - "What was issued to the client for project 225?"
    - "Which projects had an internal review before issue?"
    
    Args:
        query: Natural language search query
        project_id: Optional project filter (219-225)
        document_type: Optional document type filter
        graph_client: Microsoft Graph client
        
    Returns:
        Relevant engineering documents matching the query
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


@router.get("/list")
async def list_documents(
    folder: Optional[str] = None,
    source: str = "suitefiles",  # Default to suitefiles, can be "storage" for blob storage
    graph_client: MicrosoftGraphClient = Depends(get_graph_client),
    storage_client: BlobServiceClient = Depends(get_storage_client)
) -> JSONResponse:
    """
    List documents from Suitefiles (SharePoint) or Azure Blob Storage.
    
    Args:
        folder: Optional folder to filter by
        source: "suitefiles" (default) or "storage" 
        graph_client: Microsoft Graph client for Suitefiles access
        storage_client: Azure Storage client for blob storage
        
    Returns:
        List of document metadata from the specified source
    """
    try:
        logger.info("Listing documents", folder=folder, source=source)
        
        if source == "suitefiles":
            # List documents from Suitefiles via Microsoft Graph
            try:
                suitefiles_docs = await graph_client.sync_suitefiles_documents()
                
                # Filter by folder if specified
                if folder:
                    suitefiles_docs = [
                        doc for doc in suitefiles_docs 
                        if folder.lower() in doc.get("drive_name", "").lower() or 
                           folder.lower() in doc.get("name", "").lower()
                    ]
                
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


@router.post("/sync-suitefiles")
async def sync_suitefiles_documents(
    graph_client: MicrosoftGraphClient = Depends(get_graph_client),
    storage_client: BlobServiceClient = Depends(get_storage_client)
) -> JSONResponse:
    """
    Sync documents from Suitefiles via Microsoft Graph API.
    This endpoint pulls files from SharePoint/Suitefiles and processes them.
    """
    try:
        logger.info("Starting Suitefiles document sync")
        
        # Get documents from Suitefiles via Microsoft Graph
        suitefiles_docs = await graph_client.sync_suitefiles_documents()
        
        if not suitefiles_docs:
            logger.warning("No documents found in Suitefiles")
            return JSONResponse({
                "status": "completed",
                "message": "No documents found in Suitefiles",
                "synced_count": 0,
                "processed_count": 0
            })
        
        synced_count = 0
        processed_count = 0
        
        # Process each document
        for doc in suitefiles_docs:
            try:
                # Download file content
                file_content = await graph_client.download_file(
                    doc["site_id"], 
                    doc["drive_id"], 
                    doc["file_id"]
                )
                
                # Upload to blob storage
                blob_name = f"suitefiles/{doc['drive_name']}/{doc['name']}"
                blob_client = storage_client.get_blob_client(
                    container=settings.AZURE_STORAGE_CONTAINER,
                    blob=blob_name
                )
                
                blob_client.upload_blob(file_content, overwrite=True)
                logger.info("Uploaded file to blob storage", blob_name=blob_name)
                synced_count += 1
                
                # Auto-extract and index the document
                try:
                    # Extract text
                    await extract_text(blob_name, storage_client)
                    
                    # Index for search
                    await index_document(blob_name, storage_client)
                    
                    processed_count += 1
                    logger.info("Document processed successfully", blob_name=blob_name)
                    
                except Exception as e:
                    logger.warning("Failed to process document", blob_name=blob_name, error=str(e))
                    
            except Exception as e:
                logger.error("Failed to sync document", doc_name=doc.get('name'), error=str(e))
                continue
        
        logger.info("Suitefiles sync completed", 
                   total_found=len(suitefiles_docs), 
                   synced=synced_count, 
                   processed=processed_count)
        
        return JSONResponse({
            "status": "completed",
            "message": f"Synced {synced_count} documents from Suitefiles",
            "total_found": len(suitefiles_docs),
            "synced_count": synced_count,
            "processed_count": processed_count
        })
        
    except Exception as e:
        logger.error("Suitefiles sync failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
