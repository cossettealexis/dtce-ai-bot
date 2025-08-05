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
        blob_name: Name of the blob in Azure Storage
        storage_client: Azure Storage client
        
    Returns:
        Extracted text content and metadata
    """
    try:
        logger.info("Starting text extraction", blob_name=blob_name)
        
        # Get blob client
        blob_client = storage_client.get_blob_client(
            container=settings.azure_storage_container,
            blob=blob_name
        )
        
        # Check if blob exists
        if not blob_client.exists():
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Download blob content
        blob_data = blob_client.download_blob().readall()
        
        # Initialize Form Recognizer client
        form_recognizer_client = DocumentAnalysisClient(
            endpoint=settings.azure_form_recognizer_endpoint,
            credential=AzureKeyCredential(settings.azure_form_recognizer_key)
        )
        
        # Analyze document
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(blob_data)
            temp_file.flush()
            
            with open(temp_file.name, "rb") as f:
                poller = form_recognizer_client.begin_analyze_document("prebuilt-read", f)
                result = poller.result()
        
        # Clean up temp file
        os.unlink(temp_file.name)
        
        # Extract text content
        extracted_text = ""
        for page in result.pages:
            for line in page.lines:
                extracted_text += line.content + "\n"
        
        # Extract tables if any
        tables = []
        for table in result.tables:
            table_data = []
            for cell in table.cells:
                table_data.append({
                    "row": cell.row_index,
                    "column": cell.column_index,
                    "content": cell.content
                })
            tables.append(table_data)
        
        logger.info("Text extraction completed", blob_name=blob_name, text_length=len(extracted_text))
        
        return JSONResponse({
            "blob_name": blob_name,
            "extracted_text": extracted_text,
            "tables": tables,
            "page_count": len(result.pages),
            "extraction_timestamp": result.created_date_time.isoformat() if result.created_date_time else None
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


@router.get("/list")
async def list_documents(
    folder: Optional[str] = None,
    storage_client: BlobServiceClient = Depends(get_storage_client)
) -> JSONResponse:
    """
    List all documents in storage, optionally filtered by folder.
    
    Args:
        folder: Optional folder to filter by
        storage_client: Azure Storage client
        
    Returns:
        List of document metadata
    """
    try:
        logger.info("Listing documents", folder=folder)
        
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
                "folder": blob.metadata.get("folder", "") if blob.metadata else ""
            })
        
        logger.info("Document listing completed", document_count=len(documents))
        
        return JSONResponse({
            "documents": documents,
            "total_count": len(documents),
            "folder": folder
        })
        
    except Exception as e:
        logger.error("Document listing failed", error=str(e), folder=folder)
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
