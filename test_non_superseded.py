#!/usr/bin/env python3

import os
import sys
import asyncio
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

async def test_non_superseded():
    try:
        from azure.search.documents import SearchClient
        from azure.core.credentials import AzureKeyCredential
        
        # Initialize clients
        search_service_name = os.getenv('AZURE_SEARCH_SERVICE_NAME')
        search_endpoint = f"https://{search_service_name}.search.windows.net" if search_service_name else None
        search_key = os.getenv('AZURE_SEARCH_ADMIN_KEY') 
        index_name = os.getenv('AZURE_SEARCH_INDEX_NAME')
        
        search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=index_name,
            credential=AzureKeyCredential(search_key)
        )
        
        # Search for current wellness policy (not superseded)
        search_results = search_client.search(
            search_text="wellness policy -superseded",
            top=10,
            include_total_count=True
        )
        
        print("=== NON-SUPERSEDED WELLNESS DOCUMENTS ===")
        for i, doc in enumerate(search_results):
            filename = doc.get('filename', 'Unknown')
            blob_name = doc.get('blob_name', '')
            blob_url = doc.get('blob_url', '')
            
            # Check if superseded
            is_superseded = any(term in blob_name.lower() for term in ['superseded', 'superceded', 'archive', 'old'])
            
            print(f"Document {i+1}: {filename}")
            print(f"  Blob name: {blob_name}")
            print(f"  Superseded: {is_superseded}")
            print(f"  URL: {blob_url[:100]}...")
            print()
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_non_superseded())
