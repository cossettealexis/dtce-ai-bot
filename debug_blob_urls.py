#!/usr/bin/env python3

import os
import sys
import asyncio
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

async def debug_blob_urls():
    try:
        from azure.search.documents import SearchClient
        from azure.core.credentials import AzureKeyCredential
        
        search_service_name = os.getenv('AZURE_SEARCH_SERVICE_NAME')
        search_endpoint = f"https://{search_service_name}.search.windows.net" if search_service_name else None
        search_key = os.getenv('AZURE_SEARCH_ADMIN_KEY') 
        index_name = os.getenv('AZURE_SEARCH_INDEX_NAME')
        
        search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=index_name,
            credential=AzureKeyCredential(search_key)
        )
        
        # Search for wellness policy
        search_results = search_client.search(
            search_text="wellness policy",
            top=3,
            include_total_count=True
        )
        
        print("=== SEARCH RESULTS FOR 'wellness policy' ===")
        for i, doc in enumerate(search_results):
            print(f"\n--- Document {i+1} ---")
            print(f"All available fields: {list(doc.keys())}")
            
            # Print all fields and their values
            for key, value in doc.items():
                if isinstance(value, str) and len(value) > 100:
                    print(f"{key}: {value[:100]}...")
                else:
                    print(f"{key}: {value}")
            
            print("-" * 40)
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_blob_urls())
