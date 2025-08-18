#!/usr/bin/env python3
"""
Script to re-index existing documents from Azure Storage to the new search index.
This script reads existing documents from storage and indexes them to the new index.
"""

import asyncio
from dtce_ai_bot.integrations.azure_storage import get_storage_client
from dtce_ai_bot.integrations.azure.search_client import AzureSearchClient
from dtce_ai_bot.api.documents import index_document
from dtce_ai_bot.config.settings import get_settings

async def reindex_all_documents():
    """Re-index all documents from Azure Storage to the new search index."""
    
    settings = get_settings()
    storage_client = get_storage_client()
    search_client = AzureSearchClient()
    
    print(f"🔄 Re-indexing documents to: {search_client.index_name}")
    print("=" * 60)
    
    try:
        # Get container client
        container_client = storage_client.get_container_client(settings.azure_storage_container)
        
        # List all blobs
        print("📁 Scanning Azure Storage for documents...")
        blob_list = list(container_client.list_blobs())
        total_blobs = len(blob_list)
        
        print(f"📊 Found {total_blobs} documents to re-index")
        
        if total_blobs == 0:
            print("ℹ️  No documents found in storage")
            return
        
        # Re-index each document
        success_count = 0
        error_count = 0
        
        for i, blob in enumerate(blob_list, 1):
            blob_name = blob.name
            print(f"[{i}/{total_blobs}] Processing: {blob_name}")
            
            try:
                # Use existing index_document function
                result = await index_document(blob_name, search_client, storage_client)
                success_count += 1
                print(f"  ✅ Successfully indexed")
                
            except Exception as e:
                error_count += 1
                print(f"  ❌ Error: {str(e)}")
        
        print("\n" + "=" * 60)
        print("📊 Re-indexing Summary:")
        print(f"✅ Successfully indexed: {success_count}")
        print(f"❌ Errors: {error_count}")
        print(f"📁 Total processed: {success_count + error_count}")
        
        # Get final index statistics
        print("\n🔍 Final index statistics:")
        stats = await search_client.get_index_statistics()
        print(f"Documents in index: {stats.get('document_count', 0)}")
        
    except Exception as e:
        print(f"❌ Re-indexing failed: {str(e)}")

if __name__ == "__main__":
    print("🔄 Document Re-indexing Tool")
    print("This will re-index all documents from Azure Storage to the new search index.")
    print("Your original files will not be modified.\n")
    
    # Ask for confirmation
    response = input("Continue with re-indexing? (y/N): ")
    if response.lower() != 'y':
        print("Re-indexing cancelled.")
        exit(0)
    
    asyncio.run(reindex_all_documents())
