#!/usr/bin/env python3
"""
Simple test to check if Azure Search index has documents
"""
import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.config.settings import Settings
from azure.search.documents.aio import SearchClient
from azure.core.credentials import AzureKeyCredential

async def test_search_index():
    """Test if the Azure Search index has documents."""
    print("🔍 Testing Azure Search Index")
    print("=" * 40)
    
    try:
        settings = Settings()
        
        # Initialize Azure Search client
        search_endpoint = f"https://{settings.azure_search_service_name}.search.windows.net"
        search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=settings.azure_search_index_name,
            credential=AzureKeyCredential(settings.azure_search_admin_key)
        )
        
        # Test a basic search
        results = await search_client.search(search_text="*", top=5)
        documents = [doc async for doc in results]
        
        print(f"📊 Total documents found: {len(documents)}")
        
        if documents:
            print("\n📄 Sample documents:")
            for i, doc in enumerate(documents[:3], 1):
                print(f"  {i}. {doc.get('filename', 'Unknown file')}")
                print(f"     Folder: {doc.get('folder', 'Unknown folder')}")
                print(f"     Content preview: {doc.get('content', '')[:100]}...")
                print()
        else:
            print("❌ No documents found in the index!")
            
        await search_client.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_search_index())
