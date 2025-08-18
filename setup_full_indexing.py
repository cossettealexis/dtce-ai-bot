#!/usr/bin/env python3
"""
Create Azure Search indexer configuration to index all blob storage folders.
"""

import sys
sys.path.append('.')
from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
from azure.search.documents.indexes.models import (
    SearchIndex, SearchField, SearchFieldDataType, SimpleField, SearchableField,
    SearchIndexer, SearchIndexerDataSourceConnection, SearchIndexerDataContainer
)
from azure.core.credentials import AzureKeyCredential
from dtce_ai_bot.config.settings import Settings

def create_index_schema():
    """Create the search index schema."""
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="filename", type=SearchFieldDataType.String),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SearchableField(name="folder", type=SearchFieldDataType.String),
        SearchableField(name="project_name", type=SearchFieldDataType.String),
        SimpleField(name="blob_url", type=SearchFieldDataType.String),
        SimpleField(name="last_modified", type=SearchFieldDataType.String),
        SimpleField(name="content_type", type=SearchFieldDataType.String),
        SimpleField(name="size", type=SearchFieldDataType.Int32),
    ]
    
    return SearchIndex(name="dtce-documents-index", fields=fields)

def main():
    """Set up Azure Search indexing for all blob storage folders."""
    
    # Initialize
    settings = Settings()
    credential = AzureKeyCredential(settings.azure_search_admin_key)
    endpoint = settings.azure_search_base_url.format(service_name=settings.azure_search_service_name)
    
    index_client = SearchIndexClient(endpoint=endpoint, credential=credential)
    indexer_client = SearchIndexerClient(endpoint=endpoint, credential=credential)
    
    print("🚀 Setting up Azure Search indexing for all folders...")
    print("=" * 60)
    
    try:
        # Step 1: Create or update the index
        print("📋 Step 1: Creating search index...")
        index = create_index_schema()
        result = index_client.create_or_update_index(index)
        print(f"   ✅ Index '{result.name}' created/updated successfully")
        
        # Step 2: Create data source connection for blob storage
        print("🗂️  Step 2: Creating data source connection...")
        
        # Create data source that indexes ALL folders (no filter)
        data_source = SearchIndexerDataSourceConnection(
            name="dtce-blob-datasource",
            type="azureblob",
            connection_string=f"DefaultEndpointsProtocol=https;AccountName={settings.azure_storage_account_name};AccountKey={settings.azure_storage_account_key};EndpointSuffix=core.windows.net",
            container=SearchIndexerDataContainer(
                name="dtce-documents",
                # No query filter = indexes ALL folders: Clients, DTCE Workplace Essentials, Engineering, Projects
            )
        )
        
        result = indexer_client.create_or_update_data_source_connection(data_source)
        print(f"   ✅ Data source '{result.name}' created/updated successfully")
        print("   📁 Will index ALL folders: Clients, DTCE Workplace Essentials, Engineering, Projects")
        
        # Step 3: Create indexer
        print("⚙️  Step 3: Creating indexer...")
        
        indexer = SearchIndexer(
            name="dtce-documents-indexer",
            data_source_name="dtce-blob-datasource",
            target_index_name="dtce-documents-index",
            # Schedule to run daily
            schedule={
                "interval": "PT24H"  # Every 24 hours
            }
        )
        
        result = indexer_client.create_or_update_indexer(indexer)
        print(f"   ✅ Indexer '{result.name}' created/updated successfully")
        
        # Step 4: Run the indexer immediately
        print("🏃 Step 4: Running indexer to start indexing...")
        indexer_client.run_indexer("dtce-documents-indexer")
        print("   ✅ Indexer started! This will take a while to process all folders.")
        
        print("\\n🎉 SUCCESS! Azure Search is now configured to index all folders:")
        print("   📁 Clients")
        print("   📁 DTCE Workplace Essentials") 
        print("   📁 Engineering")
        print("   📁 Projects")
        print("\\n⏳ The indexing process is now running in the background.")
        print("   It may take 30+ minutes to index all documents in all folders.")
        print("   You can check progress in the Azure Portal under your Search Service.")
        
        # Check indexer status
        print("\\n📊 Current indexer status:")
        status = indexer_client.get_indexer_status("dtce-documents-indexer")
        print(f"   Status: {status.status}")
        print(f"   Last result: {status.last_result.status if status.last_result else 'None'}")
        
    except Exception as e:
        print(f"❌ Error setting up indexing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
