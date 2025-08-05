"""
Azure Search dependency injection for FastAPI.
"""

from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from ..config.settings import get_settings


def get_search_client() -> SearchClient:
    """Get Azure Search client."""
    settings = get_settings()
    endpoint = f"https://{settings.azure_search_service_name}.search.windows.net"
    return SearchClient(
        endpoint=endpoint,
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )
