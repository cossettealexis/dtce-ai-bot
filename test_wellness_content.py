"""Test to see exactly what content is in wellness policy documents"""
import asyncio
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
import os
from dotenv import load_dotenv
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.config.settings import get_settings

load_dotenv()
settings = get_settings()

async def check_wellness_documents():
    # Initialize search client
    endpoint = f"https://{settings.azure_search_service_name}.search.windows.net"
    search_client = SearchClient(
        endpoint=endpoint,
        index_name="dtce-documents-index",
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )
    
    print("\n=== SEARCHING FOR WELLNESS POLICY DOCUMENTS ===\n")
    
    # Search for wellness/wellbeing documents
    results = search_client.search(
        search_text="wellbeing wellness policy",
        select=["filename", "content", "blob_url"],
        top=5
    )
    
    for i, doc in enumerate(results, 1):
        print(f"\n--- Document {i} ---")
        print(f"Filename: {doc.get('filename', 'N/A')}")
        print(f"Content Length: {len(doc.get('content', ''))}")
        print(f"Content Preview (first 500 chars):")
        content = doc.get('content', 'NO CONTENT')
        print(f"{content[:500]}")
        print(f"\nFull content:\n{content}")
        print(f"\nBlob URL: {doc.get('blob_url', 'N/A')}")
        print("-" * 80)

if __name__ == "__main__":
    asyncio.run(check_wellness_documents())
