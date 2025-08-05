"""
Azure Storage dependency injection for FastAPI.
"""

from azure.storage.blob import BlobServiceClient
from ..config.settings import get_settings


def get_storage_client() -> BlobServiceClient:
    """Get Azure Blob Storage client."""
    settings = get_settings()
    return BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)
