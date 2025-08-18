#!/usr/bin/env python3
"""
Script to update Azure Search indexer to index all blob storage folders.
"""

import asyncio
from azure.search.documents.indexes import SearchIndexerClient
from azure.core.credentials import AzureKeyCredential
from dtce_ai_bot.config.settings import Settings

async def main():
    """Update the indexer to include all folders."""
    
    # Initialize settings and client
    settings = Settings()
    credential = AzureKeyCredential(settings.azure_search_admin_key)
    endpoint = settings.azure_search_base_url.format(service_name=settings.azure_search_service_name)
    
    indexer_client = SearchIndexerClient(endpoint=endpoint, credential=credential)
    
    try:
        # List current indexers
        print("🔍 Current indexers:")
        indexers = list(indexer_client.get_indexers())
        for indexer in indexers:
            print(f"  📋 Name: {indexer.name}")
            print(f"     Data Source: {indexer.data_source_name}")
            print(f"     Target Index: {indexer.target_index_name}")
            print(f"     Schedule: {indexer.schedule}")
            print("---")
        
        # List current data sources
        print("\n🗂️  Current data sources:")
        data_sources = list(indexer_client.get_data_sources())
        for ds in data_sources:
            print(f"  📁 Name: {ds.name}")
            print(f"     Type: {ds.type}")
            print(f"     Container: {ds.container.name}")
            if hasattr(ds.container, 'query') and ds.container.query:
                print(f"     Query/Filter: {ds.container.query}")
            else:
                print("     Query/Filter: None (indexes entire container)")
            print("---")
        
        # Check if any filters are limiting to just Projects
        print("\n🔍 Analysis:")
        for ds in data_sources:
            if hasattr(ds.container, 'query') and ds.container.query:
                if 'Projects' in ds.container.query and ('Clients' not in ds.container.query or 'Engineering' not in ds.container.query):
                    print(f"⚠️  Data source '{ds.name}' appears to be filtered to Projects only")
                    print(f"   Current filter: {ds.container.query}")
                    print("   This explains why only Projects folder is indexed!")
                else:
                    print(f"✅ Data source '{ds.name}' filter looks comprehensive")
            else:
                print(f"✅ Data source '{ds.name}' has no filter (should index everything)")
        
        print("\n📋 Next steps:")
        print("1. Go to Azure Portal → Azure Search Service")
        print("2. Click 'Data sources' → Select your data source")
        print("3. Remove any folder-specific filters OR update to include all folders:")
        print("   - Remove filter completely to index everything")
        print("   - Or use: folderPath eq 'Clients' or folderPath eq 'DTCE Workplace Essentials' or folderPath eq 'Engineering' or folderPath eq 'Projects'")
        print("4. Click 'Indexers' → Select your indexer → 'Run'")
        print("5. Wait for indexing to complete (may take a while for all folders)")
        
    except Exception as e:
        print(f"❌ Error accessing indexer configuration: {e}")
        print("Please check your Azure Search service permissions and configuration.")

if __name__ == "__main__":
    asyncio.run(main())
