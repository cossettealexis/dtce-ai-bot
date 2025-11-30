"""
Index Templates files that are already in blob storage
This script reads from the blob storage and indexes the Templates files
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from azure.storage.blob import BlobServiceClient
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from dtce_ai_bot.config.settings import Settings
from dtce_ai_bot.services.document_indexer import DocumentIndexer

async def index_templates_from_blob():
    """Index Templates files from blob storage"""
    settings = Settings()
    
    # Initialize blob client
    blob_service_client = BlobServiceClient(
        account_url=f"https://{settings.azure_storage_account_name}.blob.core.windows.net",
        credential=settings.azure_storage_account_key
    )
    
    # Initialize search client
    search_client = SearchClient(
        endpoint=settings.azure_search_service_endpoint,
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )
    
    # Initialize indexer
    indexer = DocumentIndexer(
        search_client=search_client,
        blob_service_client=blob_service_client,
        container_name=settings.azure_storage_container_name
    )
    
    print("🔍 Searching for Templates files in blob storage...")
    container_client = blob_service_client.get_container_client(settings.azure_storage_container_name)
    
    # List all blobs with "Templates" in the path
    templates_blobs = []
    blob_list = container_client.list_blobs()
    
    for blob in blob_list:
        if "Templates" in blob.name:
            templates_blobs.append(blob)
            print(f"  Found: {blob.name}")
    
    print(f"\n📊 Total Templates files found: {len(templates_blobs)}")
    
    if not templates_blobs:
        print("❌ No Templates files found in blob storage!")
        return
    
    print("\n🔄 Starting indexing process...")
    
    # Index each blob
    indexed_count = 0
    failed_count = 0
    
    for blob in templates_blobs:
        try:
            print(f"\n📄 Indexing: {blob.name}")
            
            # Create document metadata
            doc_metadata = {
                "id": blob.name.replace("/", "_").replace(" ", "_"),
                "filename": os.path.basename(blob.name),
                "blob_url": f"https://{settings.azure_storage_account_name}.blob.core.windows.net/{settings.azure_storage_container_name}/{blob.name}",
                "folder": os.path.dirname(blob.name),
                "file_type": os.path.splitext(blob.name)[1].lower(),
                "source": "Templates",
            }
            
            # Download blob content
            blob_client = container_client.get_blob_client(blob.name)
            blob_data = blob_client.download_blob()
            content = blob_data.readall()
            
            # Index the document
            await indexer.index_document(
                doc_id=doc_metadata["id"],
                filename=doc_metadata["filename"],
                content=content,
                metadata=doc_metadata
            )
            
            indexed_count += 1
            print(f"  ✅ Indexed successfully")
            
        except Exception as e:
            failed_count += 1
            print(f"  ❌ Failed: {str(e)}")
    
    print(f"\n{'='*80}")
    print(f"📊 INDEXING SUMMARY")
    print(f"{'='*80}")
    print(f"Total files found: {len(templates_blobs)}")
    print(f"✅ Successfully indexed: {indexed_count}")
    print(f"❌ Failed: {failed_count}")
    print(f"{'='*80}")
    
    await search_client.close()

if __name__ == "__main__":
    asyncio.run(index_templates_from_blob())
