#!/usr/bin/env python3
"""
PRODUCTION Re-indexing - Index ALL real documents from Azure Storage directly
"""

import os
import sys
import asyncio
from azure.storage.blob import BlobServiceClient
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
import re
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def production_reindex():
    """Re-index ALL production documents directly from Azure Storage."""
    print("🚨 PRODUCTION RE-INDEXING - Processing ALL real documents")
    print("=" * 80)
    
    # Get settings from environment variables (same as production)
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    search_service = os.getenv("AZURE_SEARCH_SERVICE_NAME", "dtce-search")
    search_key = os.getenv("AZURE_SEARCH_ADMIN_KEY")
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "dtce-documents-index")
    container_name = os.getenv("AZURE_STORAGE_CONTAINER", "dtce-documents")
    
    if not connection_string or not search_key:
        print("❌ Missing Azure credentials in environment variables")
        print("Set AZURE_STORAGE_CONNECTION_STRING and AZURE_SEARCH_ADMIN_KEY")
        return
    
    # Initialize clients
    storage_client = BlobServiceClient.from_connection_string(connection_string)
    search_client = SearchClient(
        endpoint=f"https://{search_service}.search.windows.net",
        index_name=index_name,
        credential=AzureKeyCredential(search_key)
    )
    
    container_client = storage_client.get_container_client(container_name)
    
    # Get ALL blobs from production storage
    print(f"📋 Getting ALL blobs from container '{container_name}'...")
    try:
        blobs = list(container_client.list_blobs())
        print(f"✅ Found {len(blobs)} production documents")
    except Exception as e:
        print(f"❌ Failed to list blobs: {e}")
        return
    
    if len(blobs) == 0:
        print("❌ No documents found in production storage!")
        return
    
    # Index ALL documents
    print(f"🔥 Indexing {len(blobs)} production documents...")
    success_count = 0
    error_count = 0
    
    for i, blob in enumerate(blobs, 1):
        try:
            print(f"[{i}/{len(blobs)}] {blob.name}")
            
            # Get blob metadata
            blob_client = storage_client.get_blob_client(container=container_name, blob=blob.name)
            blob_properties = blob_client.get_blob_properties()
            metadata = blob_properties.metadata or {}
            
            # Extract project info
            folder_path = metadata.get("folder", "")
            project_name = ""
            year = None
            
            if folder_path:
                path_parts = folder_path.split("/")
                for part in path_parts:
                    if part.isdigit() and len(part) == 4:
                        year = int(part)
                    elif part and not part.startswith("."):
                        project_name = part
            
            # Create search document
            document_id = re.sub(r'[^a-zA-Z0-9_-]', '_', blob.name)
            document_id = re.sub(r'_+', '_', document_id).strip('_')
            
            filename = metadata.get("original_filename", blob.name)
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
                success_count += 1
                if i % 10 == 0:  # Progress every 10 docs
                    print(f"  ✅ Progress: {success_count}/{i} indexed")
            else:
                error_count += 1
                print(f"  ❌ Failed to index")
                
        except Exception as e:
            error_count += 1
            print(f"  ❌ Error: {str(e)[:100]}")
    
    print(f"\n🎉 PRODUCTION RE-INDEXING COMPLETE!")
    print(f"✅ Successfully indexed: {success_count}")
    print(f"❌ Errors: {error_count}")
    print(f"📊 Total documents: {len(blobs)}")
    print(f"📈 Success rate: {(success_count/len(blobs)*100):.1f}%")
    
    if success_count > 0:
        print(f"\n🤖 Your production bot should now find documents!")
        print(f"🔍 Try asking about precast, retaining walls, etc.")
    else:
        print(f"\n💥 No documents were indexed - check credentials and permissions")

if __name__ == "__main__":
    asyncio.run(production_reindex())
