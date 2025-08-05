"""
Azure Search dependency injection for FastAPI.
"""

from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchFieldDataType,
    ComplexField
)
from azure.core.credentials import AzureKeyCredential
from ..config.settings import get_settings
import logging

logger = logging.getLogger(__name__)


def get_search_client() -> SearchClient:
    """Get Azure Search client."""
    settings = get_settings()
    endpoint = f"https://{settings.azure_search_service_name}.search.windows.net"
    return SearchClient(
        endpoint=endpoint,
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )


def get_search_index_client() -> SearchIndexClient:
    """Get Azure Search Index Management client."""
    settings = get_settings()
    endpoint = f"https://{settings.azure_search_service_name}.search.windows.net"
    return SearchIndexClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )


async def create_search_index_if_not_exists():
    """Create the search index if it doesn't exist."""
    try:
        settings = get_settings()
        index_client = get_search_index_client()
        
        # Check if index exists
        try:
            index_client.get_index(settings.azure_search_index_name)
            logger.info(f"Search index '{settings.azure_search_index_name}' already exists")
            return
        except Exception:
            logger.info(f"Creating search index '{settings.azure_search_index_name}'")
        
        # Define the index schema
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SimpleField(name="blob_name", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="blob_url", type=SearchFieldDataType.String),
            SearchableField(name="filename", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="content_type", type=SearchFieldDataType.String, filterable=True),
            SearchableField(name="folder", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SimpleField(name="size", type=SearchFieldDataType.Int64, filterable=True),
            SearchableField(name="content", type=SearchFieldDataType.String, analyzer_name="en.lucene"),
            SimpleField(name="last_modified", type=SearchFieldDataType.DateTimeOffset, filterable=True, sortable=True),
            SimpleField(name="created_date", type=SearchFieldDataType.DateTimeOffset, filterable=True, sortable=True),
            SearchableField(name="project_name", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SimpleField(name="year", type=SearchFieldDataType.Int32, filterable=True, facetable=True),
        ]
        
        # Create the index
        index = SearchIndex(name=settings.azure_search_index_name, fields=fields)
        index_client.create_index(index)
        
        logger.info(f"Search index '{settings.azure_search_index_name}' created successfully")
        
    except Exception as e:
        logger.error(f"Failed to create search index: {str(e)}")
        raise
