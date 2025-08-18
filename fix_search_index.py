#!/usr/bin/env python3
"""
Script to fix the Azure Search index field name conflicts.
Since we can't delete existing fields, we'll create a new index with updated field names.
"""

import asyncio
import os
from dtce_ai_bot.integrations.azure.search_client import AzureSearchClient
from dtce_ai_bot.config.settings import Settings

async def create_new_index():
    """Create a new search index with the correct field names."""
    
    # Temporarily change the index name to create a new one
    settings = Settings()
    original_index_name = settings.azure_search_index_name
    new_index_name = f"{original_index_name}-v2"
    
    print(f"Creating new index: {new_index_name}")
    print(f"Original index: {original_index_name}")
    
    # Update the index name
    settings.azure_search_index_name = new_index_name
    
    # Create the search client with new index name
    search_client = AzureSearchClient()
    search_client.index_name = new_index_name
    
    # Create the new index
    result = await search_client.create_or_update_index()
    
    if result:
        print(f"✅ Successfully created new index: {new_index_name}")
        print(f"📝 Update your .env file to use: AZURE_SEARCH_INDEX_NAME={new_index_name}")
        
        # Get statistics
        stats = await search_client.get_index_statistics()
        print(f"📊 Index statistics: {stats}")
        
    else:
        print(f"❌ Failed to create new index: {new_index_name}")
    
    return result

async def test_existing_index():
    """Test the existing index to see what fields it has."""
    
    search_client = AzureSearchClient()
    
    print(f"Testing existing index: {search_client.index_name}")
    
    # Try to get statistics
    stats = await search_client.get_index_statistics()
    print(f"Index statistics: {stats}")
    
    print("Skipping search test due to field name conflicts...")

if __name__ == "__main__":
    print("🔍 Azure Search Index Diagnostic Tool")
    print("=" * 50)
    
    print("\n1. Testing existing index...")
    asyncio.run(test_existing_index())
    
    print("\n2. Creating new index with correct field names...")
    result = asyncio.run(create_new_index())
    
    if result:
        print("\n✅ New index created successfully!")
        print("Next steps:")
        print("1. Update your .env file with the new index name")
        print("2. Re-index your documents using the new index")
        print("3. Update your application to use the new index")
    else:
        print("\n❌ Index creation failed. Check the error messages above.")
