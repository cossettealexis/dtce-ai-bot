#!/Users/cossettealexisgabuya/Documents/Projects/dtce-ai-bot/.venv/bin/python
"""
SAFE INDEXING SCRIPT - INDEX ONLY, NO DELETIONS

This script ONLY indexes Templates and Master_Project_Folder_Aug24 files.
It uses 'mergeOrUpload' action which:
- Adds new documents if they don't exist
- Updates existing documents by merging new content
- NEVER deletes any documents

Safety guarantees:
1. No delete operations anywhere in the code
2. Only processes Templates/ and Master_Project_Folder_Aug24/ paths
3. Uses merge action to preserve existing data
4. Read-only operations on blob storage
"""

import os
import sys
import asyncio
import base64
import logging
import structlog
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from functools import lru_cache
from datetime import datetime, timedelta

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.aio import SearchClient
from azure.storage.blob.aio import BlobServiceClient
from azure.ai.formrecognizer.aio import DocumentAnalysisClient
from azure.storage.blob import generate_blob_sas, BlobSasPermissions

# --- Load Environment & Configure Logging ---
load_dotenv()
logging.basicConfig(
    level=logging.INFO, format="%(message)s", stream=sys.stdout
)
logger = structlog.get_logger(__name__)

# --- Configuration ---
class ScriptSettings(BaseSettings):
    """Configuration settings required for this script, loaded from .env file."""
    azure_storage_connection_string: str
    azure_search_service_endpoint: str
    azure_search_index_name: str
    azure_search_api_key: str
    
    # Document Intelligence
    azure_document_intelligence_endpoint: str = ""
    azure_document_intelligence_key: str = ""
    AZURE_FORM_RECOGNIZER_ENDPOINT: str = ""
    AZURE_FORM_RECOGNIZER_KEY: str = ""

    @property
    def doc_intel_endpoint(self) -> str:
        endpoint = self.azure_document_intelligence_endpoint or self.AZURE_FORM_RECOGNIZER_ENDPOINT
        if not endpoint:
            raise ValueError("Document Intelligence endpoint not configured")
        return endpoint

    @property
    def doc_intel_key(self) -> str:
        key = self.azure_document_intelligence_key or self.AZURE_FORM_RECOGNIZER_KEY
        if not key:
            raise ValueError("Document Intelligence key not configured")
        return key

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

@lru_cache()
def get_script_settings() -> ScriptSettings:
    """Returns a cached instance of the script settings."""
    return ScriptSettings()

# --- Azure Clients ---
def get_search_client(settings: ScriptSettings) -> SearchClient:
    """Initializes Azure AI Search client."""
    return SearchClient(
        endpoint=settings.azure_search_service_endpoint,
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_api_key),
    )

def get_storage_client(settings: ScriptSettings) -> BlobServiceClient:
    """Initializes Azure Blob Storage client."""
    return BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)

def get_doc_intel_client(settings: ScriptSettings) -> DocumentAnalysisClient:
    """Initializes Azure Document Intelligence client."""
    return DocumentAnalysisClient(
        endpoint=settings.doc_intel_endpoint,
        credential=AzureKeyCredential(settings.doc_intel_key)
    )

# --- Helper Functions ---
def encode_document_id(blob_name: str) -> str:
    """Generates a base64-encoded document ID from the blob name."""
    return base64.urlsafe_b64encode(blob_name.encode("utf-8")).decode("utf-8")

def should_skip_file(blob_name: str) -> bool:
    """Determines if a file should be skipped based on its extension."""
    skip_extensions = {".lnk", ".url", ".ini", ".ds_store"}
    _, ext = os.path.splitext(blob_name.lower())
    return ext in skip_extensions

def generate_sas_url(storage_client: BlobServiceClient, container_name: str, blob_name: str) -> str:
    """Generates a SAS URL for secure blob access."""
    account_name = storage_client.account_name
    account_key = storage_client.credential.account_key
    
    sas_token = generate_blob_sas(
        account_name=account_name,
        container_name=container_name,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(hours=1)
    )
    
    return f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"

async def extract_content_with_doc_intel(blob_url: str, doc_intel_client: DocumentAnalysisClient) -> str:
    """Extracts text content from a document using Azure Document Intelligence."""
    try:
        poller = await doc_intel_client.begin_analyze_document_from_url(
            "prebuilt-read", blob_url
        )
        result = await poller.result()
        
        if result.content:
            return result.content.strip()
        return ""
    except Exception as e:
        logger.warning(f"Document Intelligence extraction failed: {str(e)}")
        return ""

async def index_document(
    blob_name: str,
    search_client: SearchClient,
    storage_client: BlobServiceClient,
    doc_intel_client: DocumentAnalysisClient,
    container_name: str
) -> tuple[bool, str]:
    """
    Index a single document using mergeOrUpload action.
    This NEVER deletes - only adds or updates.
    """
    try:
        # Generate document ID
        doc_id = encode_document_id(blob_name)
        
        # Generate SAS URL
        blob_url = generate_sas_url(storage_client, container_name, blob_name)
        
        # Extract content using Document Intelligence
        content = await extract_content_with_doc_intel(blob_url, doc_intel_client)
        
        # Prepare document for indexing
        folder = os.path.dirname(blob_name)
        filename = os.path.basename(blob_name)
        
        document = {
            "id": doc_id,
            "blob_url": blob_url.split("?")[0],  # Remove SAS token from stored URL
            "content": content,
            "folder": folder,
            "filename": filename,
            "last_modified": datetime.utcnow().isoformat() + "Z",
        }
        
        # Upload with mergeOrUpload action (SAFE - no deletes)
        await search_client.merge_or_upload_documents(documents=[document])
        
        logger.info(f"✅ Indexed: {blob_name}")
        return (True, blob_name)
        
    except Exception as e:
        logger.error(f"❌ Failed to index {blob_name}: {str(e)}")
        return (False, blob_name)

async def main():
    """
    Main function to index Templates and Master_Project_Folder_Aug24 files.
    SAFETY: Only reads from blob storage, only indexes (no deletes).
    """
    settings = get_script_settings()
    
    # Initialize clients
    search_client = get_search_client(settings)
    storage_client = get_storage_client(settings)
    doc_intel_client = get_doc_intel_client(settings)
    
    container_name = "dtce-documents"
    
    # SAFETY: Only these two folders will be processed
    folders_to_index = [
        "Templates/",
        "Templates/Master_Project_Folder_Aug24/"
    ]
    
    print("=" * 80)
    print("🔒 SAFE TEMPLATES INDEXING SCRIPT")
    print("=" * 80)
    print("Safety guarantees:")
    print("  ✅ NO delete operations")
    print("  ✅ Only indexes Templates/ and Master_Project_Folder_Aug24/")
    print("  ✅ Uses mergeOrUpload (preserves existing data)")
    print("  ✅ Read-only on blob storage")
    print("=" * 80)
    print()
    
    total_success = 0
    total_failed = 0
    
    try:
        container_client = storage_client.get_container_client(container_name)
        
        for folder_prefix in folders_to_index:
            print(f"\n📁 Processing folder: {folder_prefix}")
            print("-" * 80)
            
            folder_success = 0
            folder_failed = 0
            
            # List all blobs in this folder
            async for blob in container_client.list_blobs(name_starts_with=folder_prefix):
                if should_skip_file(blob.name):
                    logger.info(f"⏭️  Skipping: {blob.name}")
                    continue
                
                # Index the document
                success, blob_name = await index_document(
                    blob.name,
                    search_client,
                    storage_client,
                    doc_intel_client,
                    container_name
                )
                
                if success:
                    folder_success += 1
                else:
                    folder_failed += 1
            
            print(f"\n📊 Folder Summary: {folder_prefix}")
            print(f"  ✅ Success: {folder_success}")
            print(f"  ❌ Failed: {folder_failed}")
            
            total_success += folder_success
            total_failed += folder_failed
        
    except Exception as e:
        logger.error(f"Critical error: {str(e)}", exc_info=True)
    
    finally:
        print("\n" + "=" * 80)
        print("📊 FINAL INDEXING SUMMARY")
        print("=" * 80)
        print(f"✅ Total successfully indexed: {total_success}")
        print(f"❌ Total failed: {total_failed}")
        print("=" * 80)
        print("\n🔒 SAFETY CONFIRMED: No documents were deleted")
        print("=" * 80)
        
        # Close clients
        await search_client.close()
        await storage_client.close()
        await doc_intel_client.close()

if __name__ == "__main__":
    print("\n⚠️  SAFETY CHECK: This script will ONLY index files, NEVER delete")
    print("Press Ctrl+C to cancel, or wait 3 seconds to continue...\n")
    
    import time
    time.sleep(3)
    
    asyncio.run(main())
