#!/usr/bin/env python3
"""
Script to recreate Azure Search index with correct semantic configuration.
"""

import asyncio
from dtce_ai_bot.config.settings import get_settings
from azure.search.documents.indexes import SearchIndexClient
from azure.core.credentials import AzureKeyCredential

async def recreate_index():
    """Recreate the Azure Search index with correct semantic configuration."""
    settings = get_settings()
    
    print(f"🔧 Recreating Azure Search index: {settings.azure_search_index_name}")
    
    # Get index client
    index_client = SearchIndexClient(
        endpoint=f"https://{settings.azure_search_service_name}.search.windows.net",
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )
    
    try:
        # Delete existing index
        print("🗑️  Deleting existing index...")
        index_client.delete_index(settings.azure_search_index_name)
        print("✅ Index deleted successfully")
        
        # Wait a moment for deletion to complete
        await asyncio.sleep(5)
        
        # Create new index with correct configuration
        print("🏗️  Creating new index with correct semantic configuration...")
        from dtce_ai_bot.integrations.azure_search import create_search_index
        await create_search_index()
        print("✅ Index created successfully with correct semantic configuration")
        
        # Verify the new configuration
        print("🔍 Verifying semantic configuration...")
        index = index_client.get_index(settings.azure_search_index_name)
        
        if index.semantic_search and index.semantic_search.configurations:
            config = index.semantic_search.configurations[0]
            print(f"✅ Semantic config name: {config.name}")
            print(f"✅ Title field: {config.prioritized_fields.title_field.field_name}")
            print(f"✅ Content fields: {[field.field_name for field in config.prioritized_fields.content_fields]}")
        else:
            print("❌ No semantic configuration found!")
        
    except Exception as e:
        print(f"❌ Error recreating index: {e}")

if __name__ == "__main__":
    asyncio.run(recreate_index())
