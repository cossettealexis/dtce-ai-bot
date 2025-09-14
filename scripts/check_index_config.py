#!/usr/bin/env python3
"""
Diagnostic script to check Azure Search index configuration.
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dtce_ai_bot.config.settings import get_settings
from dtce_ai_bot.integrations.azure_search import get_search_client
from azure.search.documents.indexes import SearchIndexClient
from azure.core.credentials import AzureKeyCredential

async def check_index_config():
    """Check the current Azure Search index configuration."""
    settings = get_settings()
    
    print(f"🔍 Checking Azure Search index: {settings.azure_search_index_name}")
    print(f"🔍 Service: {settings.azure_search_service_name}")
    
    # Get index client
    index_client = SearchIndexClient(
        endpoint=f"https://{settings.azure_search_service_name}.search.windows.net",
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )
    
    try:
        # Get the index
        index = index_client.get_index(settings.azure_search_index_name)
        
        print(f"\n📊 Index found: {index.name}")
        print(f"📊 Fields count: {len(index.fields)}")
        
        print("\n📋 Fields:")
        for field in index.fields:
            print(f"  - {field.name}: {field.type} (searchable: {getattr(field, 'searchable', 'N/A')}, retrievable: {getattr(field, 'retrievable', 'N/A')})")
        
        print(f"\n🔧 Semantic configuration: {index.semantic_search}")
        if index.semantic_search:
            print(f"🔧 Semantic configurations count: {len(index.semantic_search.configurations)}")
            for config in index.semantic_search.configurations:
                print(f"  - Name: {config.name}")
                print(f"    Title field: {config.prioritized_fields.title_field}")
                print(f"    Content fields: {[field.field_name for field in config.prioritized_fields.content_fields]}")
        else:
            print("❌ No semantic search configuration found!")
        
        # Test search client
        search_client = get_search_client()
        print(f"\n🔍 Testing search client...")
        
        # Try a simple search
        results = search_client.search("test", top=1)
        count = 0
        for result in results:
            count += 1
            break
        print(f"✅ Simple search works (found {count} results)")
        
        # Try semantic search
        try:
            results = search_client.search(
                "test", 
                query_type="semantic",
                semantic_configuration_name="default",
                top=1
            )
            count = 0
            for result in results:
                count += 1
                break
            print(f"✅ Semantic search works (found {count} results)")
        except Exception as e:
            print(f"❌ Semantic search failed: {e}")
        
    except Exception as e:
        print(f"❌ Error checking index: {e}")

if __name__ == "__main__":
    asyncio.run(check_index_config())
