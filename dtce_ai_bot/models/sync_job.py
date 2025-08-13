"""
Sync job models for async document synchronization.
Following SOLID principles with proper model separation.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class SyncJobStatus(str, Enum):
    """Status enum for sync jobs."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SyncJobRequest(BaseModel):
    """Request model for starting a sync job."""
    path: Optional[str] = None
    force_resync: bool = False
    batch_size: int = 50
    description: Optional[str] = None


class SyncJobProgress(BaseModel):
    """Progress information for a sync job."""
    total_files: int = 0
    processed_files: int = 0
    successful_files: int = 0
    failed_files: int = 0
    current_file: Optional[str] = None
    current_operation: Optional[str] = None
    percentage: float = 0.0
    estimated_remaining_minutes: Optional[float] = None


class SyncJobResult(BaseModel):
    """Result information for a completed sync job."""
    synced_count: int = 0
    processed_count: int = 0
    ai_ready_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    errors: List[str] = []
    performance_notes: List[str] = []


class SyncJob(BaseModel):
    """Complete sync job model."""
    job_id: str
    status: SyncJobStatus
    path: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: SyncJobProgress = SyncJobProgress()
    result: Optional[SyncJobResult] = None
    error_message: Optional[str] = None
    logs: List[str] = []


class SyncJobSummary(BaseModel):
    """Summary model for listing sync jobs."""
    job_id: str
    status: SyncJobStatus
    path: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    progress_percentage: float = 0.0
    duration_minutes: Optional[float] = None
