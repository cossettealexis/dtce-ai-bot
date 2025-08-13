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
from ..services.document_sync_service import get_document_sync_service
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
        """Execute the sync job with progress tracking using centralized sync service."""
        job = self.get_job(job_id)
        if not job:
            return
        
        try:
            logger.info("Running sync job", job_id=job_id, path=job.path)
            
            # Create progress callback to update job status
            def progress_callback(progress_data: dict):
                if job.status == SyncJobStatus.CANCELLED:
                    return
                
                # Update job progress
                job.progress.total_files = progress_data.get("total_files", job.progress.total_files)
                job.progress.processed_files = progress_data.get("processed_files", 0)
                job.progress.current_file = progress_data.get("current_file")
                job.progress.current_operation = progress_data.get("current_operation")
                job.progress.percentage = progress_data.get("percentage", 0.0)
                job.progress.estimated_remaining_minutes = progress_data.get("estimated_remaining_minutes")
                
                # Add log messages
                if "message" in progress_data:
                    job.logs.append(progress_data["message"])
            
            # Use centralized sync service
            sync_service = get_document_sync_service(storage_client)
            sync_result = asyncio.run(sync_service.sync_documents(
                graph_client=graph_client,
                path=job.path,
                progress_callback=progress_callback
            ))
            
            # Update job progress counts
            job.progress.successful_files = sync_result.synced_count - sync_result.error_count
            job.progress.failed_files = sync_result.error_count
            
            # Convert sync result to job result
            job_result = SyncJobResult(
                synced_count=sync_result.synced_count,
                processed_count=sync_result.processed_count,
                ai_ready_count=sync_result.ai_ready_count,
                skipped_count=sync_result.skipped_count,
                error_count=sync_result.error_count,
                errors=sync_result.errors,
                performance_notes=sync_result.performance_notes
            )
            
            # Complete the job
            job.status = SyncJobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.result = job_result
            job.progress.percentage = 100.0
            
            logger.info("Completed sync job", 
                       job_id=job_id, 
                       synced_count=sync_result.synced_count,
                       processed_count=sync_result.processed_count)
            
        except Exception as e:
            logger.error("Sync job failed", job_id=job_id, error=str(e))
            job.status = SyncJobStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.error_message = str(e)
            job.logs.append(f"ERROR: {str(e)}")
# Global service instance
_sync_job_service = None

def get_sync_job_service() -> SyncJobService:
    """Get the global sync job service instance."""
    global _sync_job_service
    if _sync_job_service is None:
        _sync_job_service = SyncJobService()
    return _sync_job_service
