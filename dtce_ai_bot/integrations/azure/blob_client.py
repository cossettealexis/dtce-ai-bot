import asyncio
from typing import List, Optional
from azure.storage.blob import BlobServiceClient, ContainerClient
from azure.core.exceptions import AzureError
import json
import structlog
from datetime import datetime

from ...config.settings import Settings
from ...models.documents import DocumentMetadata

logger = structlog.get_logger(__name__)


class AzureBlobClient:
    """Client for interacting with Azure Blob Storage."""
    
    def __init__(self):
        self.settings = Settings()
        self.connection_string = self.settings.azure_storage_connection_string
        self.container_name = self.settings.azure_storage_container_name
        self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
        self.container_client = self.blob_service_client.get_container_client(self.container_name)
    
    async def ensure_container_exists(self) -> bool:
        """Ensure the blob container exists, create if not."""
        try:
            # Check if container exists
            try:
                await asyncio.to_thread(self.container_client.get_container_properties)
                logger.info("Blob container exists", container=self.container_name)
                return True
            except Exception:
                # Container doesn't exist, create it
                await asyncio.to_thread(self.container_client.create_container)
                logger.info("Created blob container", container=self.container_name)
                return True
                
        except AzureError as e:
            logger.error("Failed to ensure container exists", error=str(e))
            return False
    
    def _generate_blob_name(self, document: DocumentMetadata) -> str:
        """Generate a unique blob name for a document."""
        # Use project ID and file path to create a hierarchical structure
        safe_path = document.file_path.replace("/", "_").replace("\\", "_")
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        if document.project_id:
            return f"projects/{document.project_id}/{safe_path}_{timestamp}.json"
        else:
            return f"engineering/{safe_path}_{timestamp}.json"
    
    async def upload_document_metadata(self, document: DocumentMetadata) -> Optional[str]:
        """Upload document metadata to blob storage."""
        try:
            blob_name = self._generate_blob_name(document)
            
            # Convert to JSON
            metadata_json = document.model_dump_json(indent=2)
            
            # Upload to blob storage
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            await asyncio.to_thread(
                blob_client.upload_blob,
                metadata_json,
                overwrite=True,
                content_type="application/json"
            )
            
            # Update document with blob URL
            blob_url = blob_client.url
            document.blob_url = blob_url
            
            logger.info("Uploaded document metadata", file=document.file_name, blob_name=blob_name)
            return blob_url
            
        except AzureError as e:
            logger.error("Failed to upload document metadata", file=document.file_name, error=str(e))
            return None
    
    async def upload_document_content(self, document: DocumentMetadata, content: bytes) -> Optional[str]:
        """Upload document content to blob storage."""
        try:
            # Generate blob name for content
            content_blob_name = self._generate_blob_name(document).replace(".json", f"_content{document.file_type}")
            
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=content_blob_name
            )
            
            # Set appropriate content type based on file extension
            content_type = self._get_content_type(document.file_type)
            
            await asyncio.to_thread(
                blob_client.upload_blob,
                content,
                overwrite=True,
                content_type=content_type
            )
            
            content_url = blob_client.url
            logger.info("Uploaded document content", file=document.file_name, blob_name=content_blob_name)
            return content_url
            
        except AzureError as e:
            logger.error("Failed to upload document content", file=document.file_name, error=str(e))
            return None
    
    def _get_content_type(self, file_extension: str) -> str:
        """Get appropriate content type for file extension."""
        content_types = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".doc": "application/msword",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xls": "application/vnd.ms-excel",
            ".txt": "text/plain"
        }
        return content_types.get(file_extension.lower(), "application/octet-stream")
    
    async def download_blob_content(self, blob_name: str) -> Optional[bytes]:
        """Download content from blob storage."""
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            content = await asyncio.to_thread(blob_client.download_blob)
            return content.readall()
            
        except AzureError as e:
            logger.error("Failed to download blob content", blob_name=blob_name, error=str(e))
            return None
    
    async def list_documents(self, prefix: str = "") -> List[str]:
        """List all document blobs with optional prefix filter."""
        try:
            blobs = []
            blob_list = self.container_client.list_blobs(name_starts_with=prefix)
            
            for blob in blob_list:
                if blob.name.endswith(".json"):
                    blobs.append(blob.name)
            
            return blobs
            
        except AzureError as e:
            logger.error("Failed to list documents", error=str(e))
            return []
    
    async def get_document_metadata(self, blob_name: str) -> Optional[DocumentMetadata]:
        """Retrieve document metadata from blob storage."""
        try:
            content = await self.download_blob_content(blob_name)
            if content:
                metadata_dict = json.loads(content.decode('utf-8'))
                return DocumentMetadata(**metadata_dict)
            return None
            
        except Exception as e:
            logger.error("Failed to get document metadata", blob_name=blob_name, error=str(e))
            return None
    
    async def delete_document(self, blob_name: str) -> bool:
        """Delete a document from blob storage."""
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            await asyncio.to_thread(blob_client.delete_blob)
            logger.info("Deleted document", blob_name=blob_name)
            return True
            
        except AzureError as e:
            logger.error("Failed to delete document", blob_name=blob_name, error=str(e))
            return False
    
    async def batch_upload_documents(self, documents: List[DocumentMetadata]) -> List[str]:
        """Upload multiple documents in batch."""
        successful_uploads = []
        
        for document in documents:
            blob_url = await self.upload_document_metadata(document)
            if blob_url:
                successful_uploads.append(blob_url)
        
        logger.info("Batch upload completed", 
                   total=len(documents), 
                   successful=len(successful_uploads))
        
        return successful_uploads
