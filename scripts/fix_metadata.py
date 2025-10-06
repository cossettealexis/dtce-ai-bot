#!/usr/bin/env python
"""
Fast Metadata Fix Script for Azure AI Search

This script is designed for a single, high-speed purpose: to correct missing
metadata fields (like 'folder' and 'project_name') for documents in an Azure
AI Search index.

It works by:
1.  Connecting to Azure Blob Storage and Azure AI Search.
2.  Streaming a list of blobs from a specified folder prefix.
3.  For each blob, it immediately generates a small payload containing only
    the document's ID and the corrected metadata fields.
4.  It does NOT read the file content or call the slow Document Intelligence service.
5.  It uploads these small metadata updates to the search index in large batches,
    using the 'merge' action to preserve all other existing data.

This approach is dramatically faster than a full re-index.
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

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.aio import SearchClient
from azure.storage.blob.aio import BlobServiceClient

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
        logger.error("Failed to load settings. Have you created a .env file with the required Azure credentials?", error=str(e))
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
    """Initializes a standalone Azure Blob Storage client with robust retries."""
    # Configure a more aggressive retry policy to handle transient network errors.
    return BlobServiceClient.from_connection_string(
        settings.azure_storage_connection_string,
        retry_total=10,  # Increase the total number of retries
        retry_backoff_factor=2,  # Double the backoff time for each retry
        connection_timeout=120, # Increase timeout for initial connection
        read_timeout=240 # Increase timeout for reading data
    )

# --- Main Execution ---
async def main(container_name: str, folder_prefix: str, batch_size: int):
    """Main metadata update process."""
    logger.info(
        "Starting FAST metadata fix process",
        container=container_name,
        prefix=folder_prefix,
        batch_size=batch_size,
    )

    settings = get_script_settings()
    
    async with get_search_client(settings) as search_client, \
               get_storage_client(settings) as storage_client:

        logger.info("Azure clients initialized successfully.")
        
        documents_to_upload = []
        total_processed = 0
        
        try:
            container_client = storage_client.get_container_client(container_name)
            logger.info(f"Streaming blobs from folder '{folder_prefix}'...")

            async for blob in container_client.list_blobs(name_starts_with=folder_prefix):
                total_processed += 1
                
                # Generate the document key using URL-safe Base64 encoding, as required by Azure Search
                document_key = base64.urlsafe_b64encode(blob.name.encode('utf-8')).decode('utf-8')
                
                # Create the minimal update payload
                metadata_update = {
                    "@search.action": "merge",
                    "id": document_key,
                    "folder": "/".join(blob.name.split("/")[:-1]) if "/" in blob.name else "",
                    "project_name": blob.name.split("/")[1] if blob.name.startswith("Projects/") and len(blob.name.split("/")) > 1 else "N/A",
                }
                documents_to_upload.append(metadata_update)

                if len(documents_to_upload) >= batch_size:
                    logger.info(f"Uploading a batch of {len(documents_to_upload)} metadata updates...")
                    await search_client.upload_documents(documents=documents_to_upload)
                    logger.info(f"Batch uploaded. Total processed so far: {total_processed}")
                    documents_to_upload = []

            # Upload any remaining documents in the last batch
            if documents_to_upload:
                logger.info(f"Uploading final batch of {len(documents_to_upload)} metadata updates...")
                await search_client.upload_documents(documents=documents_to_upload)
                logger.info("Final batch uploaded.")

        except Exception as e:
            logger.error("A critical error occurred during processing", error=str(e), exc_info=True)
            return
        finally:
            print("\n--- Metadata Fix Summary ---")
            print(f"✅ Total documents processed: {total_processed}")
            print("----------------------------")
            logger.info("Metadata fix process finished.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix metadata for documents in Azure AI Search.")
    parser.add_argument("--container-name", default="dtce-documents", help="Name of the Azure Blob Storage container.")
    parser.add_argument("--folder-prefix", required=True, help="The folder prefix to fix metadata for (e.g., 'Projects/225').")
    parser.add_argument("--batch-size", type=int, default=1000, help="Number of documents to upload per batch.")
    
    args = parser.parse_args()
    
    asyncio.run(main(args.container_name, args.folder_prefix, args.batch_size))
