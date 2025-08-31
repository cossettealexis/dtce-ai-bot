#!/usr/bin/env python3

import os
import sys
import asyncio
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

async def test_url_conversion():
    try:
        from azure.search.documents import SearchClient
        from azure.core.credentials import AzureKeyCredential
        
        # Initialize search client
        search_service_name = os.getenv('AZURE_SEARCH_SERVICE_NAME')
        search_endpoint = f"https://{search_service_name}.search.windows.net" if search_service_name else None
        search_key = os.getenv('AZURE_SEARCH_ADMIN_KEY') 
        index_name = os.getenv('AZURE_SEARCH_INDEX_NAME')
        
        search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=index_name,
            credential=AzureKeyCredential(search_key)
        )
        
        # Import our RAG handler
        from dtce_ai_bot.services.rag_handler import RAGHandler
        from openai import AsyncAzureOpenAI
        
        openai_client = AsyncAzureOpenAI(
            azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
            api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            api_version="2023-05-15"
        )
        
        # Create RAG handler instance
        rag_handler = RAGHandler(
            search_client=search_client,
            openai_client=openai_client,
            model_name="gpt-4"
        )
        
        # Search for wellness policy
        search_results = search_client.search(
            search_text="wellness policy",
            top=3,
            include_total_count=True
        )
        
        print("=== TESTING URL CONVERSION ===")
        for i, doc in enumerate(search_results):
            print(f"\n--- Document {i+1}: {doc.get('filename')} ---")
            
            # Extract raw blob URL
            blob_url = doc.get('blob_url', '')
            print(f"Raw blob_url: {blob_url}")
            
            # Test our extraction method
            extracted_url = rag_handler._get_blob_url_from_doc(doc)
            print(f"Extracted URL: {extracted_url}")
            
            # Test our safe SuiteFiles URL conversion
            safe_url = rag_handler._get_safe_suitefiles_url(extracted_url)
            print(f"Safe SuiteFiles URL: {safe_url}")
            
            # Test direct conversion
            if blob_url:
                direct_conversion = rag_handler._convert_to_suitefiles_url(blob_url)
                print(f"Direct SuiteFiles conversion: {direct_conversion}")
            
            print("-" * 60)
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_url_conversion())
