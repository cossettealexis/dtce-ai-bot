#!/usr/bin/env python3
"""
Debug what fields are actually in the search results
"""
import asyncio
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from dtce_ai_bot.config.settings import get_settings

async def debug_search_fields():
    """Check what fields are actually returned from wellness policy search"""
    
    print("🔍 DEBUGGING SEARCH RESULT FIELDS")
    print("=" * 60)
    
    settings = get_settings()
    
    search_client = SearchClient(
        endpoint=f"https://{settings.azure_search_service_name}.search.windows.net",
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )
    
    # Search for wellness policy
    query = "wellness policy"
    print(f"Searching for: '{query}'")
    print("-" * 60)
    
    results = search_client.search(
        search_text=query,
        top=3
    )
    
    for i, result in enumerate(results, 1):
        print(f"\n📄 DOCUMENT {i}:")
        print(f"Available fields: {list(result.keys())}")
        print()
        
        # Check each possible content field
        content_fields = ['content', 'Content', 'text', 'body', 'chunk', 'text_content']
        
        for field in content_fields:
            value = result.get(field)
            if value:
                print(f"✅ Found field '{field}': {value[:200]}...")
                break
        else:
            print("❌ No content field found!")
            
        # Show all fields with their values
        print("\nAll fields:")
        for key, value in result.items():
            if isinstance(value, str):
                print(f"  {key}: {value[:100] if len(value) > 100 else value}")
            else:
                print(f"  {key}: {value}")

if __name__ == "__main__":
    asyncio.run(debug_search_fields())
