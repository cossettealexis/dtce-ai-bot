"""
Search Index Management Module

Manages Azure AI Search index creation, updates, and document ingestion.
"""

from typing import List, Dict, Any, Optional
import logging
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SearchField, SearchFieldDataType, SimpleField, 
    SearchableField, VectorSearch, HnswAlgorithmConfiguration,
    VectorSearchProfile, SemanticConfiguration, SemanticField,
    SemanticPrioritizedFields, SemanticSearch
)
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ResourceNotFoundError

from .config import RAGConfig
from .chunker import Chunk

logger = logging.getLogger(__name__)


class SearchIndexer:
    """
    Manages Azure AI Search index and document operations
    """
    
    def __init__(self, config: RAGConfig):
        self.config = config
        
        # Initialize clients
        credential = AzureKeyCredential(config.azure.search_admin_key)
        
        self.index_client = SearchIndexClient(
            endpoint=config.azure.search_endpoint,
            credential=credential
        )
        
        self.search_client = SearchClient(
            endpoint=config.azure.search_endpoint,
            index_name=config.azure.search_index_name,
            credential=credential
        )
    
    def create_index(self, recreate: bool = False) -> bool:
        """
        Create or update the search index
        
        Args:
            recreate: Whether to delete and recreate existing index
            
        Returns:
            True if successful, False otherwise
        """
        try:
            index_name = self.config.azure.search_index_name
            
            # Check if index exists
            try:
                existing_index = self.index_client.get_index(index_name)
                if existing_index and not recreate:
                    logger.info(f"Index '{index_name}' already exists")
                    return True
                elif existing_index and recreate:
                    logger.info(f"Deleting existing index '{index_name}'")
                    self.index_client.delete_index(index_name)
            except ResourceNotFoundError:
                pass  # Index doesn't exist, which is fine
            
            # Create new index
            index = self._build_index_schema()
            self.index_client.create_index(index)
            
            logger.info(f"Created search index '{index_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Error creating index: {e}")
            return False
    
    def _build_index_schema(self) -> SearchIndex:
        """Build the search index schema"""
        index_name = self.config.azure.search_index_name
        
        # Define fields
        fields = [
            # Document identification
            SimpleField(name="chunk_id", type=SearchFieldDataType.String, key=True),
            SimpleField(name="document_id", type=SearchFieldDataType.String, filterable=True),
            
            # Content fields
            SearchableField(name="content", type=SearchFieldDataType.String, analyzer_name="en.microsoft"),
            SearchableField(name="title", type=SearchFieldDataType.String, analyzer_name="en.microsoft"),
            
            # Vector field for semantic search
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=self.config.models.embedding_dimensions,
                vector_search_profile_name="dtce-vector-profile"
            ),
            
            # Metadata fields
            SimpleField(name="document_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SimpleField(name="document_name", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="section", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="page", type=SearchFieldDataType.Int32, filterable=True),
            SimpleField(name="standard_code", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SimpleField(name="category", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SimpleField(name="last_updated", type=SearchFieldDataType.DateTimeOffset, filterable=True, sortable=True),
            
            # Chunk metadata
            SimpleField(name="chunk_index", type=SearchFieldDataType.Int32, filterable=True),
            SimpleField(name="token_count", type=SearchFieldDataType.Int32, filterable=True),
            SimpleField(name="chunk_length", type=SearchFieldDataType.Int32, filterable=True),
            
            # Raw metadata as JSON
            SimpleField(name="metadata", type=SearchFieldDataType.String),
        ]
        
        # Vector search configuration
        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(
                    name="dtce-hnsw",
                    parameters={
                        "m": 4,
                        "efConstruction": 400,
                        "efSearch": 500,
                        "metric": "cosine"
                    }
                )
            ],
            profiles=[
                VectorSearchProfile(
                    name="dtce-vector-profile",
                    algorithm_configuration_name="dtce-hnsw"
                )
            ]
        )
        
        # Semantic search configuration
        semantic_config = SemanticConfiguration(
            name="dtce-semantic-config",
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="title"),
                content_fields=[SemanticField(field_name="content")],
                keywords_fields=[
                    SemanticField(field_name="document_type"),
                    SemanticField(field_name="standard_code"),
                    SemanticField(field_name="category")
                ]
            )
        )
        
        semantic_search = SemanticSearch(
            configurations=[semantic_config]
        )
        
        # Create index
        index = SearchIndex(
            name=index_name,
            fields=fields,
            vector_search=vector_search,
            semantic_search=semantic_search
        )
        
        return index
    
    def index_chunks(self, chunks: List[Chunk], batch_size: int = 100) -> bool:
        """
        Index document chunks in the search index
        
        Args:
            chunks: List of document chunks to index
            batch_size: Number of chunks to index per batch
            
        Returns:
            True if successful, False otherwise
        """
        if not chunks:
            logger.warning("No chunks to index")
            return True
        
        try:
            total_chunks = len(chunks)
            indexed_count = 0
            
            # Process in batches
            for i in range(0, total_chunks, batch_size):
                batch = chunks[i:i + batch_size]
                documents = [self._chunk_to_document(chunk) for chunk in batch]
                
                # Upload batch
                result = self.search_client.upload_documents(documents)
                
                # Check for errors
                succeeded = sum(1 for r in result if r.succeeded)
                failed = len(result) - succeeded
                
                indexed_count += succeeded
                
                if failed > 0:
                    logger.warning(f"Failed to index {failed} documents in batch {i//batch_size + 1}")
                
                logger.info(f"Indexed batch {i//batch_size + 1}: {succeeded}/{len(batch)} documents")
            
            logger.info(f"Successfully indexed {indexed_count}/{total_chunks} chunks")
            return indexed_count > 0
            
        except Exception as e:
            logger.error(f"Error indexing chunks: {e}")
            return False
    
    def _chunk_to_document(self, chunk: Chunk) -> Dict[str, Any]:
        """Convert a chunk to a search document"""
        metadata = chunk.metadata.copy()
        
        # Extract embedding
        content_vector = metadata.pop('embedding', None)
        
        # Build document
        document = {
            "chunk_id": chunk.chunk_id,
            "content": chunk.content,
            "content_vector": content_vector,
            "chunk_index": metadata.get('chunk_index', 0),
            "token_count": chunk.token_count,
            "chunk_length": chunk.end_char - chunk.start_char,
            "metadata": str(metadata)  # Store as JSON string
        }
        
        # Add metadata fields
        document.update({
            "document_id": metadata.get('document_id', ''),
            "document_name": metadata.get('document_name', ''),
            "document_type": metadata.get('document_type', ''),
            "title": metadata.get('title', ''),
            "section": metadata.get('section', ''),
            "page": metadata.get('page'),
            "standard_code": metadata.get('standard_code', ''),
            "category": metadata.get('category', ''),
            "last_updated": metadata.get('last_updated'),
        })
        
        # Remove None values
        document = {k: v for k, v in document.items() if v is not None}
        
        return document
    
    def delete_document(self, document_id: str) -> bool:
        """
        Delete all chunks for a document
        
        Args:
            document_id: ID of the document to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Search for chunks of the document
            results = self.search_client.search(
                search_text="*",
                filter=f"document_id eq '{document_id}'",
                select=["chunk_id"]
            )
            
            # Collect chunk IDs
            chunk_ids = [result["chunk_id"] for result in results]
            
            if not chunk_ids:
                logger.info(f"No chunks found for document {document_id}")
                return True
            
            # Delete chunks
            documents_to_delete = [{"chunk_id": chunk_id} for chunk_id in chunk_ids]
            result = self.search_client.delete_documents(documents_to_delete)
            
            # Check results
            succeeded = sum(1 for r in result if r.succeeded)
            logger.info(f"Deleted {succeeded}/{len(chunk_ids)} chunks for document {document_id}")
            
            return succeeded > 0
            
        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {e}")
            return False
    
    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the search index"""
        try:
            # Get index info
            index = self.index_client.get_index(self.config.azure.search_index_name)
            
            # Count documents
            results = self.search_client.search(
                search_text="*",
                include_total_count=True,
                top=1
            )
            
            return {
                "index_name": index.name,
                "field_count": len(index.fields),
                "document_count": results.get_count(),
                "vector_search_enabled": index.vector_search is not None,
                "semantic_search_enabled": index.semantic_search is not None
            }
            
        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return {"error": str(e)}
    
    def search_documents(self, query: str = "*", filters: Dict[str, Any] = None, 
                        top: int = 10) -> List[Dict[str, Any]]:
        """
        Search documents in the index
        
        Args:
            query: Search query
            filters: Metadata filters
            top: Number of results to return
            
        Returns:
            List of search results
        """
        try:
            # Build filter string
            filter_string = None
            if filters:
                filter_conditions = []
                for key, value in filters.items():
                    if isinstance(value, str):
                        filter_conditions.append(f"{key} eq '{value}'")
                    else:
                        filter_conditions.append(f"{key} eq {value}")
                filter_string = " and ".join(filter_conditions)
            
            # Search
            results = self.search_client.search(
                search_text=query,
                filter=filter_string,
                top=top,
                include_total_count=True
            )
            
            # Convert to list
            documents = []
            for result in results:
                documents.append(dict(result))
            
            return documents
            
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return []
