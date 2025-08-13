"""
Health check service endpoints.
"""

from fastapi import APIRouter
from datetime import datetime
from typing import Dict, Any

router = APIRouter()


@router.get("/")
async def health_check() -> Dict[str, Any]:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "DTCE AI Assistant",
        "version": "1.0.0"
    }


@router.get("/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """Detailed health check with service dependencies."""
    # TODO: Add checks for Azure services, SharePoint, etc.
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "DTCE AI Assistant",
        "version": "1.0.0",
        "dependencies": {
            "azure_storage": "not_implemented",
            "azure_search": "not_implemented", 
            "azure_openai": "not_implemented",
            "sharepoint": "not_implemented"
        }
    }
