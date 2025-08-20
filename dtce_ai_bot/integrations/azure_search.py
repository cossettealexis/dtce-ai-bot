"""
Azure Search dependency injection for FastAPI.
"""

from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SearchField, SearchFieldDataType, SimpleField, SearchableField,
    SemanticConfiguration, SemanticPrioritizedFields, SemanticField, SemanticSearch
)
from azure.core.credentials import AzureKeyCredential
from ..config.settings import get_settings
import logging

logger = logging.getLogger(__name__)


def get_search_client() -> SearchClient:
    """Get Azure Search client."""
    settings = get_settings()
    endpoint = settings.azure_search_base_url.format(service_name=settings.azure_search_service_name)
    return SearchClient(
        endpoint=endpoint,
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )


def get_search_index_client() -> SearchIndexClient:
    """Get Azure Search Index Management client."""
    settings = get_settings()
    endpoint = settings.azure_search_base_url.format(service_name=settings.azure_search_service_name)
    return SearchIndexClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )


async def create_search_index():
    """Create the search index if it doesn't exist, or update it with proper semantic configuration."""
    try:
        settings = get_settings()
        index_client = get_search_index_client()
        
        # Always force update to ensure semantic configuration is properly applied
        logger.info(f"Force updating search index '{settings.azure_search_index_name}' to ensure semantic configuration")
        
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
        
        # Configure semantic search - only use fields that exist and are searchable
        semantic_config = SemanticConfiguration(
            name="default",
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="content"),  # Use content instead of filename for title
                content_fields=[
                    SemanticField(field_name="content"),
                    SemanticField(field_name="project_name")
                ],
                keywords_fields=[
                    SemanticField(field_name="folder")
                ]
            )
        )
        
        semantic_search = SemanticSearch(configurations=[semantic_config])
        
        
        # Create the index with semantic search (will create or update)
        index = SearchIndex(
            name=settings.azure_search_index_name, 
            fields=fields,
            semantic_search=semantic_search
        )
        
        logger.info(f"Updating search index '{settings.azure_search_index_name}' with semantic configuration")
        index_client.create_or_update_index(index)
        
        logger.info(f"Search index '{settings.azure_search_index_name}' configured successfully with semantic search")
        
    except Exception as e:
        logger.error(f"Failed to create search index: {str(e)}")
        raise
