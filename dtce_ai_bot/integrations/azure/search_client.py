import asyncio
from typing import List, Dict, Any, Optional
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    ComplexField
)
import structlog
from datetime import datetime

from ...config.settings import Settings
from ...models.legacy_models import DocumentMetadata, SearchQuery, SearchResult, SearchResponse

logger = structlog.get_logger(__name__)


class AzureSearchClient:
    """Client for interacting with Azure Cognitive Search."""
    
    def __init__(self):
        self.settings = Settings()
        self.service_name = self.settings.azure_search_service_name
        self.admin_key = self.settings.azure_search_admin_key
        self.index_name = self.settings.azure_search_index_name
        
        self.endpoint = self.settings.azure_search_base_url.format(service_name=self.service_name)
        self.credential = AzureKeyCredential(self.admin_key)
        
        self.search_client = SearchClient(
            endpoint=self.endpoint,
            index_name=self.index_name,
            credential=self.credential
        )
        
        self.index_client = SearchIndexClient(
            endpoint=self.endpoint,
            credential=self.credential
        )
    
    def _create_search_index_schema(self) -> SearchIndex:
        """Create the search index schema for DTCE documents."""
        
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SimpleField(name="file_id", type=SearchFieldDataType.String),
            SearchableField(name="file_name", type=SearchFieldDataType.String, analyzer="standard.lucene"),
            SimpleField(name="file_path", type=SearchFieldDataType.String),
            SimpleField(name="file_size", type=SearchFieldDataType.Int64),
            SimpleField(name="file_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SimpleField(name="modified_date", type=SearchFieldDataType.DateTimeOffset, filterable=True, sortable=True),
            SimpleField(name="created_date", type=SearchFieldDataType.DateTimeOffset, filterable=True, sortable=True),
            SimpleField(name="sharepoint_url", type=SearchFieldDataType.String),
            SimpleField(name="project_id", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SimpleField(name="document_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SearchableField(name="folder_path", type=SearchFieldDataType.String, analyzer="keyword"),
            SearchableField(name="content_preview", type=SearchFieldDataType.String, analyzer="standard.lucene"),
            SearchableField(name="extracted_text", type=SearchFieldDataType.String, analyzer="standard.lucene"),
            SearchableField(name="client_name", type=SearchFieldDataType.String, analyzer="standard.lucene"),
            SearchableField(name="project_title", type=SearchFieldDataType.String, analyzer="standard.lucene"),
            SimpleField(name="project_status", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SearchableField(name="keywords", type=SearchFieldDataType.Collection(SearchFieldDataType.String)),
            SimpleField(name="blob_url", type=SearchFieldDataType.String),
            SimpleField(name="indexed_date", type=SearchFieldDataType.DateTimeOffset, filterable=True, sortable=True)
        ]
        
        return SearchIndex(
            name=self.index_name,
            fields=fields
        )
    
    async def create_or_update_index(self) -> bool:
        """Create or update the search index."""
        try:
            index = self._create_search_index_schema()
            
            await asyncio.to_thread(self.index_client.create_or_update_index, index)
            logger.info("Search index created/updated successfully", index_name=self.index_name)
            return True
            
        except Exception as e:
            logger.error("Failed to create/update search index", error=str(e))
            return False
    
    def _document_to_search_document(self, document: DocumentMetadata) -> Dict[str, Any]:
        """Convert DocumentMetadata to search document format."""
        
        # Generate a unique ID for the search document
        doc_id = f"{document.file_id}_{hash(document.file_path)}"
        
        search_doc = {
            "id": doc_id,
            "file_id": document.file_id,
            "file_name": document.file_name,
            "file_path": document.file_path,
            "file_size": document.file_size,
            "file_type": document.file_type,
            "modified_date": document.modified_date.isoformat() if document.modified_date else None,
            "created_date": document.created_date.isoformat() if document.created_date else None,
            "sharepoint_url": document.sharepoint_url,
            "project_id": document.project_id,
            "document_type": document.document_type.value,
            "folder_path": document.folder_path,
            "content_preview": document.content_preview,
            "extracted_text": document.extracted_text,
            "client_name": document.client_name,
            "project_title": document.project_title,
            "project_status": document.project_status.value,
            "keywords": document.keywords,
            "blob_url": document.blob_url,
            "indexed_date": datetime.utcnow().isoformat()
        }
        
        # Remove None values to avoid indexing issues
        return {k: v for k, v in search_doc.items() if v is not None}
    
    async def index_document(self, document: DocumentMetadata) -> bool:
        """Index a single document in Azure Search."""
        try:
            search_doc = self._document_to_search_document(document)
            
            result = await asyncio.to_thread(
                self.search_client.upload_documents,
                documents=[search_doc]
            )
            
            if result[0].succeeded:
                logger.info("Document indexed successfully", file_name=document.file_name)
                return True
            else:
                logger.error("Failed to index document", 
                           file_name=document.file_name, 
                           error=result[0].error_message)
                return False
                
        except Exception as e:
            logger.error("Error indexing document", file_name=document.file_name, error=str(e))
            return False
    
    async def batch_index_documents(self, documents: List[DocumentMetadata]) -> int:
        """Index multiple documents in batch."""
        successful_count = 0
        
        try:
            # Convert all documents to search format
            search_docs = [self._document_to_search_document(doc) for doc in documents]
            
            # Upload in batches (Azure Search has limits)
            batch_size = 100
            for i in range(0, len(search_docs), batch_size):
                batch = search_docs[i:i + batch_size]
                
                results = await asyncio.to_thread(
                    self.search_client.upload_documents,
                    documents=batch
                )
                
                batch_successful = sum(1 for result in results if result.succeeded)
                successful_count += batch_successful
                
                logger.info("Batch indexed", 
                          batch_size=len(batch), 
                          successful=batch_successful)
        
        except Exception as e:
            logger.error("Error during batch indexing", error=str(e))
        
        logger.info("Batch indexing completed", 
                   total=len(documents), 
                   successful=successful_count)
        
        return successful_count
    
    async def search_documents(self, query: SearchQuery) -> SearchResponse:
        """Search for documents using natural language query."""
        start_time = datetime.utcnow()
        
        try:
            # Build search parameters
            search_params = {
                "search_text": query.query,
                "top": query.max_results,
                "include_total_count": True,
                "highlight_fields": "content_preview,extracted_text,file_name,project_title" if query.include_content else None
            }
            
            # Add filters if provided
            if query.filters:
                filter_parts = []
                for field, value in query.filters.items():
                    if isinstance(value, list):
                        # Handle array filters
                        filter_parts.append(f"{field}/any(x: x eq '{value[0]}')")
                    else:
                        filter_parts.append(f"{field} eq '{value}'")
                
                if filter_parts:
                    search_params["filter"] = " and ".join(filter_parts)
            
            # Execute search
            results = await asyncio.to_thread(
                self.search_client.search,
                **search_params
            )
            
            # Convert results to our format
            search_results = []
            for result in results:
                # Convert back to DocumentMetadata
                doc_metadata = self._search_result_to_document_metadata(result)
                
                # Extract highlights
                highlights = []
                if hasattr(result, '@search.highlights'):
                    for field, highlight_list in result['@search.highlights'].items():
                        highlights.extend(highlight_list)
                
                search_results.append(SearchResult(
                    document=doc_metadata,
                    score=result['@search.score'],
                    highlights=highlights
                ))
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            response = SearchResponse(
                query=query.query,
                total_results=len(search_results),
                results=search_results,
                processing_time=processing_time
            )
            
            logger.info("Search completed", 
                       query=query.query, 
                       results=len(search_results), 
                       time=processing_time)
            
            return response
            
        except Exception as e:
            logger.error("Search failed", query=query.query, error=str(e))
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            return SearchResponse(
                query=query.query,
                total_results=0,
                results=[],
                processing_time=processing_time
            )
    
    def _search_result_to_document_metadata(self, search_result: Dict[str, Any]) -> DocumentMetadata:
        """Convert search result back to DocumentMetadata."""
        
        # Parse dates
        modified_date = None
        if search_result.get("modified_date"):
            modified_date = datetime.fromisoformat(search_result["modified_date"])
        
        created_date = None
        if search_result.get("created_date"):
            created_date = datetime.fromisoformat(search_result["created_date"])
        
        indexed_date = None
        if search_result.get("indexed_date"):
            indexed_date = datetime.fromisoformat(search_result["indexed_date"])
        
        return DocumentMetadata(
            file_id=search_result.get("file_id", ""),
            file_name=search_result.get("file_name", ""),
            file_path=search_result.get("file_path", ""),
            file_size=search_result.get("file_size", 0),
            file_type=search_result.get("file_type", ""),
            modified_date=modified_date,
            created_date=created_date,
            sharepoint_url=search_result.get("sharepoint_url", ""),
            project_id=search_result.get("project_id"),
            document_type=search_result.get("document_type", "Other"),
            folder_path=search_result.get("folder_path", ""),
            content_preview=search_result.get("content_preview"),
            extracted_text=search_result.get("extracted_text"),
            client_name=search_result.get("client_name"),
            project_title=search_result.get("project_title"),
            project_status=search_result.get("project_status", "unknown"),
            keywords=search_result.get("keywords", []),
            blob_url=search_result.get("blob_url"),
            indexed_date=indexed_date
        )
    
    async def delete_document(self, document_id: str) -> bool:
        """Delete a document from the search index."""
        try:
            await asyncio.to_thread(
                self.search_client.delete_documents,
                documents=[{"id": document_id}]
            )
            logger.info("Document deleted from index", document_id=document_id)
            return True
            
        except Exception as e:
            logger.error("Failed to delete document from index", document_id=document_id, error=str(e))
            return False
    
    async def get_index_statistics(self) -> Dict[str, Any]:
        """Get statistics about the search index."""
        try:
            stats = await asyncio.to_thread(self.index_client.get_index_statistics, self.index_name)
            return {
                "document_count": stats.document_count,
                "storage_size": stats.storage_size
            }
        except Exception as e:
            logger.error("Failed to get index statistics", error=str(e))
            return {}
