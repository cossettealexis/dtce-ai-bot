#!/usr/bin/env python3

import os
import sys
import asyncio
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

async def find_policy_documents():
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
        
        # Search for policy documents
        search_results = search_client.search(
            search_text="policy health safety wellness",
            top=20,
            include_total_count=True
        )
        
        current_docs = []
        superseded_docs = []
        
        for doc in search_results:
            filename = doc.get('filename', 'Unknown')
            blob_name = doc.get('blob_name', '')
            blob_url = doc.get('blob_url', '')
            
            # Check if superseded/archived
            is_superseded = any(term in blob_name.lower() for term in ['superseded', 'superceded', 'archive', 'old', 'draft', 'backup'])
            
            if is_superseded:
                superseded_docs.append((filename, blob_name, blob_url))
            else:
                current_docs.append((filename, blob_name, blob_url))
        
        print(f"=== CURRENT POLICY DOCUMENTS ({len(current_docs)}) ===")
        for i, (filename, blob_name, blob_url) in enumerate(current_docs, 1):
            print(f"{i}. {filename}")
            print(f"   Path: {blob_name}")
            print(f"   URL: {blob_url[:80]}...")
            print()
        
        print(f"\n=== SUPERSEDED POLICY DOCUMENTS ({len(superseded_docs)}) ===")
        for i, (filename, blob_name, blob_url) in enumerate(superseded_docs[:5], 1):
            print(f"{i}. {filename}")
            print(f"   Path: {blob_name}")
            print()
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(find_policy_documents())
