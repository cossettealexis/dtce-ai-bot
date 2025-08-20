#!/usr/bin/env python3
"""
Emergency re-indexing script - indexes all blobs from storage into search index.
"""

import asyncio
import os
import sys
from azure.storage.blob import BlobServiceClient
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
import json
import re
from datetime import datetime

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from dtce_ai_bot.config.settings import get_settings

async def emergency_reindex():
    """Re-index all blobs immediately."""
    print("🚨 EMERGENCY RE-INDEXING - Restoring all documents to search index")
    print("=" * 80)
    
    settings = get_settings()
    
    # Initialize clients
    storage_client = BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)
    
    search_client = SearchClient(
        endpoint=f"https://{settings.azure_search_service_name}.search.windows.net",
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )
    
    container_client = storage_client.get_container_client(settings.azure_storage_container)
    
    # List all blobs
    print("📋 Listing all blobs...")
    blobs = list(container_client.list_blobs())
    print(f"Found {len(blobs)} blobs to index")
    
    if len(blobs) == 0:
        print("❌ No blobs found in storage!")
        return
    
    # Index each blob
    success_count = 0
    error_count = 0
    
    for i, blob in enumerate(blobs, 1):
        try:
            print(f"[{i}/{len(blobs)}] Processing: {blob.name}")
            
            # Get blob metadata
            blob_client = storage_client.get_blob_client(
                container=settings.azure_storage_container,
                blob=blob.name
            )
            
            blob_properties = blob_client.get_blob_properties()
            metadata = blob_properties.metadata or {}
            
            # Extract project information from folder path
            folder_path = metadata.get("folder", "")
            project_name = ""
            year = None
            
            if folder_path:
                path_parts = folder_path.split("/")
                for part in path_parts:
                    if part.isdigit() and len(part) == 4:  # Year
                        year = int(part)
                    elif part and not part.startswith("."):  # Potential project name
                        project_name = part
            
            # Create simple document for indexing
            document_id = re.sub(r'[^a-zA-Z0-9_-]', '_', blob.name)
            document_id = re.sub(r'_+', '_', document_id).strip('_')
            
            # Basic content extraction from filename and metadata
            filename = metadata.get("original_filename", blob.name)
            content = f"Document: {filename}"
            if folder_path:
                content += f" Location: {folder_path}"
            if project_name:
                content += f" Project: {project_name}"
            
            search_document = {
                "id": document_id,
                "blob_name": blob.name,
                "blob_url": blob_client.url,
                "filename": filename,
                "content_type": metadata.get("content_type", ""),
                "folder": folder_path,
                "size": int(metadata.get("size", blob.size or 0)),
                "content": content,
                "last_modified": blob.last_modified.isoformat(),
                "created_date": blob.creation_time.isoformat() if blob.creation_time else blob.last_modified.isoformat(),
                "project_name": project_name,
                "year": year
            }
            
            # Upload to search index
            result = search_client.upload_documents([search_document])
            
            if result[0].succeeded:
                print(f"  ✅ Indexed successfully")
                success_count += 1
            else:
                print(f"  ❌ Failed to index")
                error_count += 1
                
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
            error_count += 1
    
    print(f"\n🎉 RE-INDEXING COMPLETE!")
    print(f"✅ Successfully indexed: {success_count}")
    print(f"❌ Errors: {error_count}")
    print(f"📊 Total processed: {len(blobs)}")
    
    if success_count > 0:
        print(f"\n🔍 Your search index is now restored!")
        print(f"🤖 The bot should be able to find documents again")
    else:
        print(f"\n💥 No documents were indexed - check the errors above")

if __name__ == "__main__":
    asyncio.run(emergency_reindex())
