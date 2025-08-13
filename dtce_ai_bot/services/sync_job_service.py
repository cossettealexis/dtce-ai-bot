"""
Async sync job service for handling long-running document synchronization.
Implements background job processing with progress tracking.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import structlog
from concurrent.futures import ThreadPoolExecutor
import threading

from ..models.sync_job import SyncJob, SyncJobStatus, SyncJobProgress, SyncJobResult, SyncJobRequest
from ..integrations.microsoft_graph import MicrosoftGraphClient
from azure.storage.blob import BlobServiceClient

logger = structlog.get_logger(__name__)


class SyncJobService:
    """Service for managing async document sync jobs."""
    
    def __init__(self):
        self.jobs: Dict[str, SyncJob] = {}
        self.executor = ThreadPoolExecutor(max_workers=2)  # Limit concurrent syncs
        self._lock = threading.Lock()
    
    def create_job(self, request: SyncJobRequest) -> SyncJob:
        """Create a new sync job."""
        job_id = str(uuid.uuid4())
        
        job = SyncJob(
            job_id=job_id,
            status=SyncJobStatus.PENDING,
            path=request.path,
            description=request.description or f"Sync {request.path or 'all documents'}",
            created_at=datetime.utcnow()
        )
        
        with self._lock:
            self.jobs[job_id] = job
        
        logger.info("Created sync job", job_id=job_id, path=request.path)
        return job
    
    def get_job(self, job_id: str) -> Optional[SyncJob]:
        """Get a sync job by ID."""
        with self._lock:
            return self.jobs.get(job_id)
    
    def list_jobs(self, limit: int = 50) -> List[SyncJob]:
        """List recent sync jobs."""
        with self._lock:
            jobs = list(self.jobs.values())
        
        # Sort by creation time, newest first
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        return jobs[:limit]
    
    def start_job(self, job_id: str, graph_client: MicrosoftGraphClient, storage_client: BlobServiceClient):
        """Start executing a sync job in the background."""
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        if job.status != SyncJobStatus.PENDING:
            raise ValueError(f"Job {job_id} is not in pending status")
        
        # Update job status
        job.status = SyncJobStatus.RUNNING
        job.started_at = datetime.utcnow()
        
        # Start the job in background
        future = self.executor.submit(self._run_sync_job, job_id, graph_client, storage_client)
        
        logger.info("Started sync job", job_id=job_id)
        return future
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running sync job."""
        job = self.get_job(job_id)
        if not job:
            return False
        
        if job.status == SyncJobStatus.RUNNING:
            job.status = SyncJobStatus.CANCELLED
            job.completed_at = datetime.utcnow()
            logger.info("Cancelled sync job", job_id=job_id)
            return True
        
        return False
    
    def _run_sync_job(self, job_id: str, graph_client: MicrosoftGraphClient, storage_client: BlobServiceClient):
        """Execute the sync job with progress tracking."""
        job = self.get_job(job_id)
        if not job:
            return
        
        try:
            logger.info("Running sync job", job_id=job_id, path=job.path)
            
            # Get documents to sync
            if job.path:
                suitefiles_docs = asyncio.run(graph_client.sync_suitefiles_documents_by_path(job.path))
                sync_mode = f"path_{job.path.replace('/', '_')}"
            else:
                suitefiles_docs = asyncio.run(graph_client.sync_suitefiles_documents())
                sync_mode = "full_sync"
            
            # Update progress
            job.progress.total_files = len(suitefiles_docs)
            job.logs.append(f"Found {len(suitefiles_docs)} documents to process")
            
            if not suitefiles_docs:
                job.status = SyncJobStatus.COMPLETED
                job.completed_at = datetime.utcnow()
                job.result = SyncJobResult()
                return
            
            # Process documents with progress tracking
            result = self._process_documents_with_progress(job_id, suitefiles_docs, storage_client, sync_mode)
            
            # Complete the job
            job.status = SyncJobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.result = result
            job.progress.percentage = 100.0
            
            logger.info("Completed sync job", 
                       job_id=job_id, 
                       synced_count=result.synced_count,
                       processed_count=result.processed_count)
            
        except Exception as e:
            logger.error("Sync job failed", job_id=job_id, error=str(e))
            job.status = SyncJobStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.error_message = str(e)
            job.logs.append(f"ERROR: {str(e)}")
    
    def _process_documents_with_progress(self, job_id: str, suitefiles_docs: List, storage_client: BlobServiceClient, sync_mode: str) -> SyncJobResult:
        """Process documents with detailed progress tracking."""
        from ..config.settings import get_settings
        from ..api.documents import extract_text, index_document
        from ..integrations.azure_search import get_search_client
        
        settings = get_settings()
        job = self.get_job(job_id)
        
        synced_count = 0
        processed_count = 0
        ai_ready_count = 0
        skipped_count = 0
        error_count = 0
        errors = []
        
        start_time = datetime.utcnow()
        
        for i, doc in enumerate(suitefiles_docs):
            # Check if job was cancelled
            if job.status == SyncJobStatus.CANCELLED:
                break
            
            try:
                # Update progress
                job.progress.processed_files = i + 1
                job.progress.current_file = doc.get("name", "Unknown")
                job.progress.current_operation = "Uploading to blob storage"
                job.progress.percentage = (i / len(suitefiles_docs)) * 100
                
                # Estimate remaining time
                if i > 0:
                    elapsed = (datetime.utcnow() - start_time).total_seconds() / 60
                    avg_time_per_file = elapsed / i
                    remaining_files = len(suitefiles_docs) - i
                    job.progress.estimated_remaining_minutes = remaining_files * avg_time_per_file
                
                # Process the document (same logic as original sync)
                blob_name = self._create_blob_name(doc, sync_mode)
                blob_client = storage_client.get_blob_client(
                    container=settings.azure_storage_container,
                    blob=blob_name
                )
                
                # Check if already processed
                if blob_client.exists():
                    properties = blob_client.get_blob_properties()
                    if doc.get("modified") and properties.last_modified:
                        doc_modified = doc.get("modified")
                        blob_modified = properties.last_modified.isoformat()
                        if doc_modified <= blob_modified:
                            skipped_count += 1
                            ai_ready_count += 1
                            continue
                
                # Upload and process the document
                if doc.get("is_folder", False):
                    # Handle folder
                    self._process_folder(doc, blob_client, sync_mode)
                    ai_ready_count += 1
                else:
                    # Handle file
                    self._process_file(doc, blob_client, storage_client, sync_mode)
                    processed_count += 1
                    ai_ready_count += 1
                
                synced_count += 1
                
                # Update progress
                job.progress.successful_files += 1
                
                # Log progress every 10 files
                if (i + 1) % 10 == 0:
                    job.logs.append(f"Processed {i + 1}/{len(suitefiles_docs)} files")
                
            except Exception as e:
                error_count += 1
                error_msg = f"Failed to process {doc.get('name', 'unknown')}: {str(e)}"
                errors.append(error_msg)
                job.logs.append(f"ERROR: {error_msg}")
                job.progress.failed_files += 1
                logger.warning("Document processing failed", 
                             job_id=job_id, 
                             file=doc.get("name"), 
                             error=str(e))
        
        return SyncJobResult(
            synced_count=synced_count,
            processed_count=processed_count,
            ai_ready_count=ai_ready_count,
            skipped_count=skipped_count,
            error_count=error_count,
            errors=errors,
            performance_notes=[
                f"✅ {synced_count} files synced to blob storage",
                f"✅ {processed_count} files processed for AI",
                f"⚡ {skipped_count} files skipped (already up-to-date)",
                f"❌ {error_count} files failed processing"
            ]
        )
    
    def _create_blob_name(self, doc: dict, sync_mode: str) -> str:
        """Create blob name from document info."""
        # Same logic as original sync
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
    
    def _process_folder(self, doc: dict, blob_client, sync_mode: str):
        """Process folder document."""
        # Create .keep file for folder
        keep_file_content = f"# This file ensures the '{doc['name']}' folder is visible\n# Created: {datetime.utcnow().isoformat()}\n# Folder: {doc.get('full_path', '')}\n"
        
        metadata = {
            "source": sync_mode,
            "original_filename": ".keep",
            "drive_name": doc["drive_name"], 
            "project_id": str(doc.get("project_id", "")),
            "document_type": "folder_marker",
            "folder_category": doc.get("folder_category", ""),
            "last_modified": doc.get("modified", ""),
            "is_critical": str(doc.get("is_critical_for_search", False)),
            "full_path": doc.get("full_path", ""),
            "parent_folder": doc["name"],
            "content_type": "text/plain",
            "size": str(len(keep_file_content)),
            "is_folder": "false",
            "is_folder_marker": "true"
        }
        
        blob_client.upload_blob(keep_file_content.encode('utf-8'), overwrite=True, metadata=metadata)
    
    def _process_file(self, doc: dict, blob_client, storage_client, sync_mode: str):
        """Process regular file document."""
        from ..integrations.microsoft_graph import get_graph_client
        
        # Download file content
        graph_client = get_graph_client()
        file_content = asyncio.run(graph_client.download_file(
            doc["site_id"], 
            doc["drive_id"], 
            doc["file_id"]
        ))
        
        # Upload to blob storage
        metadata = {
            "source": sync_mode,
            "original_filename": doc["name"],
            "drive_name": doc["drive_name"], 
            "project_id": str(doc.get("project_id", "")),
            "document_type": doc.get("document_type", ""),
            "folder_category": doc.get("folder_category", ""),
            "last_modified": doc.get("modified", ""),
            "is_critical": str(doc.get("is_critical_for_search", False)),
            "full_path": doc.get("full_path", ""),
            "content_type": doc.get("mime_type", ""),
            "size": str(doc.get("size", 0)),
            "is_folder": "false"
        }
        
        blob_client.upload_blob(file_content, overwrite=True, metadata=metadata)
        
        # Extract text and index for AI
        try:
            asyncio.run(extract_text(blob_client.blob_name, storage_client))
            
            from ..integrations.azure_search import get_search_client
            search_client = get_search_client()
            asyncio.run(index_document(blob_client.blob_name, search_client, storage_client))
        except Exception as e:
            logger.warning("Failed to process file for AI", blob_name=blob_client.blob_name, error=str(e))


# Global service instance
_sync_job_service = None

def get_sync_job_service() -> SyncJobService:
    """Get the global sync job service instance."""
    global _sync_job_service
    if _sync_job_service is None:
        _sync_job_service = SyncJobService()
    return _sync_job_service
