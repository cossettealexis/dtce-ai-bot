#!/Users/cossettealexisgabuya/Documents/Projects/dtce-ai-bot/.venv/bin/python
"""
Standalone script to re-index documents in an Azure AI Search index.

This script connects directly to Azure services to fetch documents from a blob storage
container, re-process them through Document Intelligence, and update the records
in the search index. It is designed to run independently of the main FastAPI application
to avoid import conflicts and simplify execution.

Key operations:
1.  Connects to Azure Blob Storage and Azure AI Search using credentials from .env.
2.  Lists blobs within a specified folder (`--folder-prefix`).
3.  For each blob, it generates a SAS token for secure access.
4.  Calls Azure Document Intelligence to re-extract text content.
5.  Generates the correct document ID (base64 of blob name) to match existing records.
6.  Uploads the updated document to the search index using a 'merge' action,
    which preserves existing fields and only updates the new ones (`content`, `folder`, `project_name`).
"""

import os
import sys
import asyncio
import argparse
import base64
import logging
import structlog
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List
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


# --- Standalone Configuration ---
class ScriptSettings(BaseSettings):
    """Configuration settings required for this script, loaded from .env file."""
    azure_storage_connection_string: str
    azure_search_service_endpoint: str
    azure_search_index_name: str
    azure_search_api_key: str
    
    # Support both new and old env var names for Document Intelligence
    azure_document_intelligence_endpoint: str = ""
    azure_document_intelligence_key: str = ""
    AZURE_FORM_RECOGNIZER_ENDPOINT: str = ""
    AZURE_FORM_RECOGNIZER_KEY: str = ""

    @property
    def doc_intel_endpoint(self) -> str:
        endpoint = self.azure_document_intelligence_endpoint or self.AZURE_FORM_RECOGNIZER_ENDPOINT
        if not endpoint:
            raise ValueError("Document Intelligence endpoint is not configured. Set either AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT or AZURE_FORM_RECOGNIZER_ENDPOINT.")
        return endpoint

    @property
    def doc_intel_key(self) -> str:
        key = self.azure_document_intelligence_key or self.AZURE_FORM_RECOGNIZER_KEY
        if not key:
            raise ValueError("Document Intelligence key is not configured. Set either AZURE_DOCUMENT_INTELLIGENCE_KEY or AZURE_FORM_RECOGNIZER_KEY.")
        return key

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

@lru_cache()
def get_script_settings() -> ScriptSettings:
    """Returns a cached instance of the script settings."""
    try:
        return ScriptSettings()
    except Exception as e:
        logger.error("Failed to load settings. Have you created a .env file?", error=str(e))
        sys.exit(1)

# --- Standalone Azure Clients ---
def get_search_client(settings: ScriptSettings) -> SearchClient:
    """Initializes a standalone Azure AI Search client."""
    return SearchClient(
        endpoint=settings.azure_search_service_endpoint,
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_api_key),
    )

def get_storage_client(settings: ScriptSettings) -> BlobServiceClient:
    """Initializes a standalone Azure Blob Storage client."""
    return BlobServiceClient.from_connection_string(
        settings.azure_storage_connection_string
    )

def get_doc_intelligence_client(settings: ScriptSettings) -> DocumentAnalysisClient:
    """Initializes a standalone Document Intelligence client."""
    return DocumentAnalysisClient(
        endpoint=settings.doc_intel_endpoint,
        credential=AzureKeyCredential(settings.doc_intel_key),
    )

def get_blob_sas_url(storage_client: BlobServiceClient, container_name: str, blob_name: str) -> str:
    """Generates a SAS URL for a specific blob."""
    account_key = storage_client.credential.account_key
    sas_token = generate_blob_sas(
        account_name=storage_client.account_name,
        container_name=container_name,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(hours=1),
    )
    return f"https://{storage_client.account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"

# --- Helper Functions ---
def should_skip_file(blob_name: str) -> bool:
    """Determines if a file should be skipped based on its extension."""
    excluded_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.ico', '.svg', '.webp', '.mp4', '.mov', '.avi', '.wmv', '.zip', '.rar', '.7z']
    return any(blob_name.lower().endswith(ext) for ext in excluded_extensions)

def clean_text(text: str) -> str:
    """Basic text cleaning."""
    return " ".join(text.replace("\n", " ").split())

async def update_document_in_search(
    doc_info: dict,
    search_client: SearchClient,
    storage_client: BlobServiceClient,
    doc_intel_client: DocumentAnalysisClient,
    container_name: str
) -> tuple[bool, int]:
    """Fetches, analyzes, and updates a single document in the Azure Search index."""
    blob_name = doc_info.get("blob_name")
    if not blob_name:
        logger.error("Document info is missing 'blob_name'", doc_info=doc_info)
        return False, 0

    try:
        sas_url = get_blob_sas_url(storage_client, container_name, blob_name)
        poller = await doc_intel_client.begin_analyze_document_from_url("prebuilt-layout", sas_url)
        analysis_result = await poller.result()

        if not analysis_result.content:
            logger.warning("Document Intelligence returned no content", blob_name=blob_name)
            return False, 0
        
        new_content = clean_text(analysis_result.content)
        document_key = base64.b64encode(blob_name.encode('utf-8')).decode('utf-8')
        
        updated_document = {
            "@search.action": "merge",
            "id": document_key,
            "content": new_content,
            "folder": "/".join(blob_name.split("/")[:-1]) if "/" in blob_name else "",
            "project_name": blob_name.split("/")[1] if blob_name.startswith("Projects/") and len(blob_name.split("/")) > 1 else "N/A",
        }

        upload_result = await search_client.upload_documents(documents=[updated_document])
        
        if upload_result and upload_result[0].succeeded:
            logger.info("Successfully updated document", blob_name=blob_name)
            return True, len(new_content)
        else:
            status = upload_result[0] if upload_result else "N/A"
            logger.error("Failed to upload updated document", blob_name=blob_name, status=status)
            return False, 0

    except Exception as e:
        logger.error("Exception during document update", blob_name=blob_name, error=str(e), exc_info=True)
        return False, 0

# --- Main Execution ---
async def main(container_name: str, folder_prefix: str):
    """Main content update process."""
    logger.info(
        "Starting interactive re-index process",
        container=container_name,
        prefix=folder_prefix,
    )

    settings = get_script_settings()
    
    async with get_search_client(settings) as search_client, \
               get_storage_client(settings) as storage_client, \
               get_doc_intelligence_client(settings) as doc_intel_client:

        logger.info("Azure clients initialized successfully.")
        
        total_success_count = 0
        total_failed_count = 0
        batch_size = 100
        batch_tasks = []
        
        try:
            container_client = storage_client.get_container_client(container_name)
            logger.info(f"Streaming blobs from folder '{folder_prefix}'. Processing will begin immediately.")

            async for blob in container_client.list_blobs(name_starts_with=folder_prefix):
                if should_skip_file(blob.name):
                    continue

                doc_info = {"blob_name": blob.name}
                task = update_document_in_search(doc_info, search_client, storage_client, doc_intel_client, container_name)
                batch_tasks.append(task)

                if len(batch_tasks) >= batch_size:
                    logger.info(f"Processing a batch of {len(batch_tasks)} documents...")
                    results = await asyncio.gather(*batch_tasks)
                    
                    success_count = sum(1 for r in results if r[0])
                    total_success_count += success_count
                    total_failed_count += len(results) - success_count
                    
                    logger.info(f"Batch complete. Success: {success_count}, Failed: {len(results) - success_count}")
                    logger.info(f"Running totals -> Success: {total_success_count}, Failed: {total_failed_count}")
                    batch_tasks = []

            # Process any remaining tasks in the last batch
            if batch_tasks:
                logger.info(f"Processing final batch of {len(batch_tasks)} documents...")
                results = await asyncio.gather(*batch_tasks)
                success_count = sum(1 for r in results if r[0])
                total_success_count += success_count
                total_failed_count += len(results) - success_count
                logger.info(f"Final batch complete. Success: {success_count}, Failed: {len(results) - success_count}")

        except Exception as e:
            logger.error("A critical error occurred during blob processing", error=str(e), exc_info=True)
            return
        finally:
            print("\n--- Final Re-indexing Summary ---")
            print(f"✅ Total successfully updated: {total_success_count}")
            print(f"❌ Total failed to update: {total_failed_count}")
            print("---------------------------------")
            logger.info("Re-indexing process finished.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-index documents from Azure Blob Storage.")
    parser.add_argument("--container-name", default="dtce-documents", help="Name of the Azure Blob Storage container.")
    parser.add_argument("--folder-prefix", required=True, help="The folder prefix to limit re-indexing (e.g., 'Projects/225').")
    
    args = parser.parse_args()
    
    asyncio.run(main(args.container_name, args.folder_prefix))
