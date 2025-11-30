"""
Check Azure Search index to see if Templates files are indexed
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dtce_ai_bot.config.settings import Settings
from azure.search.documents.aio import SearchClient
from azure.core.credentials import AzureKeyCredential

async def check_templates_in_index():
    """Check if Templates files are in the search index"""
    
    settings = Settings()
    
    search_client = SearchClient(
        endpoint=settings.azure_search_service_endpoint,
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_api_key)
    )
    
    print("=" * 80)
    print("🔍 CHECKING AZURE SEARCH INDEX FOR TEMPLATES FILES")
    print("=" * 80)
    print()
    
    # Search for documents with "Templates/" in folder path
    results = await search_client.search(
        search_text="Templates",
        select=["filename", "folder", "blob_url"],
        top=100
    )
    
    count = 0
    async for result in results:
        count += 1
        print(f"{count}. {result['filename']}")
        print(f"   Folder: {result['folder']}")
        print(f"   URL: {result.get('blob_url', 'N/A')}")
        print()
    
    print("=" * 80)
    print(f"📊 TOTAL TEMPLATES FILES FOUND IN INDEX: {count}")
    print("=" * 80)
    
    await search_client.close()

if __name__ == "__main__":
    asyncio.run(check_templates_in_index())
