#!/usr/bin/env python3
"""
PRODUCTION Re-indexing - Index ALL real documents from Azure Storage directly
"""

import os
import sys
import asyncio
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
import re
from datetime import datetime
import time
from azure.core.exceptions import ServiceResponseError

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env file
load_dotenv()

async def production_reindex():
    """Re-index ALL production documents directly from Azure Storage."""
    print("🚨 PRODUCTION RE-INDEXING - Processing ALL real documents")
    print("=" * 80)
    
    # Get settings from environment variables (same as production)
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    
    # Correctly parse the search service name from the endpoint
    search_endpoint = os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT")
    search_service_name = ""
    if search_endpoint:
        match = re.search(r"https://(.*?)\.search\.windows\.net", search_endpoint)
        if match:
            search_service_name = match.group(1)

    search_key = os.getenv("AZURE_SEARCH_ADMIN_KEY") or os.getenv("AZURE_SEARCH_API_KEY")
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "dtce-documents-index")
    container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "dtce-documents")
    
    if not connection_string or not search_key or not search_service_name:
        print("❌ Missing Azure credentials in environment variables")
        print("Set AZURE_STORAGE_CONNECTION_STRING, AZURE_SEARCH_SERVICE_ENDPOINT, and AZURE_SEARCH_ADMIN_KEY")
        return
    
    # Initialize clients
    storage_client = BlobServiceClient.from_connection_string(connection_string)
    search_client = SearchClient(
        endpoint=search_endpoint,
        index_name=index_name,
        credential=AzureKeyCredential(search_key)
    )
    
    container_client = storage_client.get_container_client(container_name)
    
    # Get an iterator for blobs from production storage
    print(f"📋 Getting blob iterator from container '{container_name}'...")
    try:
        blob_iterator = container_client.list_blobs()
    except Exception as e:
        print(f"❌ Failed to get blob iterator: {e}")
        return

    # Index ALL documents
    print(f"🔥 Indexing production documents...")
    success_count = 0
    error_count = 0
    total_count = 0
    
    for blob in blob_iterator:
        total_count += 1
        try:
            print(f"[{total_count}] {blob.name}")
            
            # Get blob metadata with retry
            blob_client = storage_client.get_blob_client(container=container_name, blob=blob.name)
            
            metadata = {}
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    blob_properties = blob_client.get_blob_properties()
                    metadata = blob_properties.metadata or {}
                    break
                except (ServiceResponseError, ConnectionResetError) as e:
                    if attempt < max_retries - 1:
                        print(f"  ... network error getting metadata, retrying in 5s ({e})")
                        time.sleep(5)
                    else:
                        raise e

            # Extract project info from the blob path itself as a fallback
            folder_path = blob.name.rsplit('/', 1)[0] if '/' in blob.name else ''
            project_name = ""
            year = None
            
            if folder_path:
                path_parts = folder_path.split("/")
                # Logic to find project name and year from path
                if len(path_parts) > 1 and path_parts[0] == 'Projects':
                    if len(path_parts) > 2 and path_parts[1].isdigit(): # e.g. Projects/220/
                        project_name = path_parts[1]
                        if len(path_parts) > 3 and path_parts[2].isdigit() and len(path_parts[2]) == 4:
                            year = int(path_parts[2])
                    elif len(path_parts) > 2: # e.g. Projects/Some Project/
                        project_name = path_parts[1]

            # Create search document
            document_id = re.sub(r'[^a-zA-Z0-9_-]', '_', blob.name)
            document_id = re.sub(r'_+', '_', document_id).strip('_')
            
            filename = os.path.basename(blob.name)
            content = f"Document: {filename}"
            if folder_path:
                content += f" | Path: {folder_path}"
            if project_name:
                content += f" | Project: {project_name}"
            
            search_document = {
                "id": document_id,
                "blob_name": blob.name,
                "blob_url": blob_client.url,
                "filename": filename,
                "content_type": metadata.get("content_type", blob.content_settings.content_type or ""),
                "folder": folder_path,
                "size": blob.size or 0,
                "content": content,
                "last_modified": blob.last_modified.isoformat(),
                "created_date": blob.creation_time.isoformat() if blob.creation_time else blob.last_modified.isoformat(),
                "project_name": project_name,
                "year": year
            }
            
            # Upload to search index with retry
            for attempt in range(max_retries):
                try:
                    result = search_client.upload_documents([search_document])
                    if result[0].succeeded:
                        success_count += 1
                        if total_count % 100 == 0:  # Progress every 100 docs
                            print(f"  ✅ Progress: {success_count}/{total_count} indexed")
                        break  # Break on success
                    else:
                        if attempt < max_retries - 1:
                            print(f"  ... upload failed, retrying in 5s. Reason: {result[0].error_message}")
                            time.sleep(5)
                        else:
                            error_count += 1
                            print(f"  ❌ Failed to index after retries. Reason: {result[0].error_message}")
                except (ServiceResponseError, ConnectionResetError) as e:
                    if attempt < max_retries - 1:
                        print(f"  ... network error during upload, retrying in 5s ({e})")
                        time.sleep(5)
                    else:
                        raise e
                
        except Exception as e:
            error_count += 1
            print(f"  ❌ Error processing {blob.name}: {str(e)[:150]}")
    
    print(f"\n🎉 PRODUCTION RE-INDEXING COMPLETE!")
    print(f"✅ Successfully indexed: {success_count}")
    print(f"❌ Errors: {error_count}")
    print(f"📊 Total documents processed: {total_count}")
    if total_count > 0:
        print(f"📈 Success rate: {(success_count/total_count*100):.1f}%")
    
    if success_count > 0:
        print(f"\n🤖 Your production bot should now find documents!")
    else:
        print(f"\n💥 No documents were indexed - check credentials and permissions")

if __name__ == "__main__":
    asyncio.run(production_reindex())
