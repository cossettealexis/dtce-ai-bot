"""
Centralized document sync service following SOLID principles.
Contains reusable sync logic used by both synchronous and asynchronous endpoints.
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Optional, Callable, Any
import structlog
from azure.storage.blob import BlobServiceClient

from ..config.settings import get_settings
from ..integrations.microsoft_graph import MicrosoftGraphClient

logger = structlog.get_logger(__name__)


class DocumentSyncResult:
    """Result container for document sync operations."""
    
    def __init__(self):
        self.synced_count = 0
        self.processed_count = 0
        self.ai_ready_count = 0
        self.skipped_count = 0
        self.error_count = 0
        self.folder_count = 0
        self.errors: List[str] = []
        self.performance_notes: List[str] = []


class DocumentSyncService:
    """
    Centralized service for document synchronization logic.
    Used by both sync and async sync endpoints to avoid code duplication.
    """
    
    def __init__(self, storage_client: BlobServiceClient):
        self.storage_client = storage_client
        self.settings = get_settings()
    
    async def sync_documents(
        self, 
        graph_client: MicrosoftGraphClient,
        path: Optional[str] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> DocumentSyncResult:
        """
        Core sync logic used by both sync endpoints.
        
        Args:
            graph_client: Microsoft Graph client for accessing SharePoint
            path: Optional path filter for targeted sync
            progress_callback: Optional callback for progress updates
            
        Returns:
            DocumentSyncResult with sync statistics and errors
        """
        logger.info("Starting document sync", path=path)
        
        # Get documents to sync
        if path:
            suitefiles_docs = await graph_client.sync_suitefiles_documents_by_path(path)
            sync_mode = f"path_{path.replace('/', '_')}"
        else:
            suitefiles_docs = await graph_client.sync_suitefiles_documents()
            sync_mode = "full_sync"
        
        logger.info("Found documents for sync", 
                   count=len(suitefiles_docs), 
                   sync_mode=sync_mode)
        
        # Notify progress if callback provided
        if progress_callback:
            progress_callback({
                "total_files": len(suitefiles_docs),
                "message": f"Found {len(suitefiles_docs)} documents to process"
            })
        
        # Return empty result if no documents
        if not suitefiles_docs:
            result = DocumentSyncResult()
            result.performance_notes.append("No documents found to sync")
            return result
        
        # Process documents
        return await self._process_documents(
            suitefiles_docs, 
            sync_mode, 
            graph_client,
            progress_callback
        )
    
    async def _process_documents(
        self, 
        suitefiles_docs: List[Dict], 
        sync_mode: str,
        graph_client: MicrosoftGraphClient,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> DocumentSyncResult:
        """Process documents with optional progress tracking."""
        result = DocumentSyncResult()
        start_time = datetime.utcnow()
        
        for i, doc in enumerate(suitefiles_docs):
            try:
                # Update progress
                if progress_callback:
                    progress_data = {
                        "processed_files": i + 1,
                        "total_files": len(suitefiles_docs),
                        "current_file": doc.get("name", "Unknown"),
                        "current_operation": "Processing document",
                        "percentage": (i / len(suitefiles_docs)) * 100
                    }
                    
                    # Add time estimates
                    if i > 0:
                        elapsed = (datetime.utcnow() - start_time).total_seconds() / 60
                        avg_time_per_file = elapsed / i
                        remaining_files = len(suitefiles_docs) - i
                        progress_data["estimated_remaining_minutes"] = remaining_files * avg_time_per_file
                    
                    progress_callback(progress_data)
                
                # Create blob name
                blob_name = self._create_blob_name(doc, sync_mode)
                blob_client = self.storage_client.get_blob_client(
                    container=self.settings.azure_storage_container,
                    blob=blob_name
                )
                
                # Check if already processed (optimization)
                if await self._should_skip_document(doc, blob_client):
                    result.skipped_count += 1
                    result.ai_ready_count += 1
                    continue
                
                # Process document based on type
                if doc.get("is_folder", False):
                    await self._process_folder_document(doc, blob_client, sync_mode)
                    result.folder_count += 1
                    result.ai_ready_count += 1
                else:
                    await self._process_file_document(doc, blob_client, sync_mode, graph_client)
                    result.processed_count += 1
                    result.ai_ready_count += 1
                
                result.synced_count += 1
                
                # Log progress periodically
                if (i + 1) % 50 == 0:
                    logger.info("Sync progress", 
                               processed=i + 1, 
                               total=len(suitefiles_docs))
                
            except Exception as e:
                result.error_count += 1
                error_msg = f"Failed to process {doc.get('name', 'unknown')}: {str(e)}"
                result.errors.append(error_msg)
                logger.warning("Document processing failed", 
                             file=doc.get("name"), 
                             error=str(e))
        
        # Generate performance notes
        result.performance_notes = [
            f"Synced {result.synced_count} files to blob storage",
            f"Processed {result.processed_count} files for AI search",
            f"Skipped {result.skipped_count} files (already up-to-date)",
            f"Created {result.folder_count} folder markers",
            f"Failed {result.error_count} files"
        ]
        
        logger.info("Document sync completed", 
                   synced=result.synced_count,
                   processed=result.processed_count,
                   errors=result.error_count)
        
        return result
    
    def _create_blob_name(self, doc: Dict, sync_mode: str) -> str:
        """Create standardized blob name from document metadata."""
        if "path_" in sync_mode:
            path_parts = sync_mode.replace("path_", "").split("_")
            folder_name = "/".join(path_parts)
            
            if len(path_parts) >= 2 and path_parts[0] == "Projects":
                project_id = doc.get('project_id', path_parts[-1] if len(path_parts) > 1 else 'general')
                blob_name = f"{folder_name}/{project_id}/{doc['name']}"
            else:
                blob_name = f"{folder_name}/{doc['name']}"
        else:
            folder_path = doc.get('folder_path', '')
            if folder_path:
                blob_name = f"{folder_path}/{doc['name']}"
            else:
                blob_name = f"suitefiles/{doc['drive_name']}/{doc['name']}"
        
        return blob_name
    
    async def _should_skip_document(self, doc: Dict, blob_client) -> bool:
        """Check if document should be skipped (already up-to-date)."""
        try:
            if not blob_client.exists():
                return False
            
            properties = blob_client.get_blob_properties()
            if doc.get("modified") and properties.last_modified:
                doc_modified = doc.get("modified")
                blob_modified = properties.last_modified.isoformat()
                return doc_modified <= blob_modified
            
            return False
        except Exception:
            return False
    
    async def _process_folder_document(self, doc: Dict, blob_client, sync_mode: str):
        """Process folder document by creating .keep file."""
        keep_file_content = (
            f"# This file ensures the '{doc['name']}' folder is visible\n"
            f"# Created: {datetime.utcnow().isoformat()}\n"
            f"# Folder: {doc.get('full_path', '')}\n"
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
        
        metadata = {
            "source": sync_mode,
            "original_filename": ".keep",
            "drive_name": sanitize_metadata_value(doc["drive_name"]), 
            "project_id": sanitize_metadata_value(doc.get("project_id", "")),
            "document_type": "folder_marker",
            "folder_category": sanitize_metadata_value(doc.get("folder_category", "")),
            "last_modified": sanitize_metadata_value(doc.get("modified", "")),
            "is_critical": str(doc.get("is_critical_for_search", False)),
            "full_path": sanitize_metadata_value(doc.get("full_path", "")),
            "parent_folder": sanitize_metadata_value(doc["name"]),
            "content_type": "text/plain",
            "size": str(len(keep_file_content)),
            "is_folder": "false",
            "is_folder_marker": "true"
        }
        
        blob_client.upload_blob(
            keep_file_content.encode('utf-8'), 
            overwrite=True, 
            metadata=metadata
        )
        
        logger.debug("Created folder marker", folder=doc["name"])
    
    async def _process_file_document(self, doc: Dict, blob_client, sync_mode: str, graph_client: MicrosoftGraphClient):
        """Process regular file document."""
        # Download file content
        file_content = await graph_client.download_file(
            doc["site_id"], 
            doc["drive_id"], 
            doc["file_id"]
        )
        
        # Upload to blob storage with metadata
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
        
        metadata = {
            "source": sync_mode,
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
            "is_folder": "false"
        }
        
        blob_client.upload_blob(file_content, overwrite=True, metadata=metadata)
        
        # Extract text and index for AI search
        try:
            await self._process_for_ai_search(blob_client.blob_name)
            logger.debug("Processed for AI search", blob_name=blob_client.blob_name)
        except Exception as e:
            logger.warning("Failed to process for AI search", 
                          blob_name=blob_client.blob_name, 
                          error=str(e))
            # Don't fail the whole sync for AI processing errors
    
    async def _process_for_ai_search(self, blob_name: str):
        """Extract text and index document for AI search."""
        from ..api.documents import extract_text, index_document
        from ..integrations.azure_search import get_search_client
        
        # Extract text content
        await extract_text(blob_name, self.storage_client)
        
        # Index for search
        search_client = get_search_client()
        await index_document(blob_name, search_client, self.storage_client)


def get_document_sync_service(storage_client: BlobServiceClient) -> DocumentSyncService:
    """Factory function to create DocumentSyncService instance."""
    return DocumentSyncService(storage_client)
