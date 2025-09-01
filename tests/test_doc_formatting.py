#!/usr/bin/env python3

import os
import sys
import asyncio
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

async def test_document_formatting():
    try:
        from azure.search.documents import SearchClient
        from azure.core.credentials import AzureKeyCredential
        from openai import AsyncAzureOpenAI
        from dtce_ai_bot.services.rag_handler import RAGHandler
        
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
        
        openai_client = AsyncAzureOpenAI(
            azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
            api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            api_version="2023-05-15"
        )
        
        # Create RAG handler
        rag_handler = RAGHandler(
            search_client=search_client,
            openai_client=openai_client,
            model_name="gpt-4"
        )
        
        # Get documents from search
        search_results = search_client.search(
            search_text="wellness policy",
            top=3,
            include_total_count=True
        )
        
        documents = [dict(doc) for doc in search_results]
        
        print("=== RAW DOCUMENTS ===")
        for i, doc in enumerate(documents):
            print(f"Document {i+1}: {doc.get('filename')}")
            blob_url = rag_handler._get_blob_url_from_doc(doc)
            suitefiles_link = rag_handler._get_safe_suitefiles_url(blob_url)
            print(f"  Raw blob_url: {blob_url}")
            print(f"  SuiteFiles link: {suitefiles_link}")
            print()
        
        # Test document formatting
        folder_context = {"query_type": "policy"}
        formatted_docs = rag_handler._format_documents_with_folder_context(documents, folder_context)
        
        print("=== FORMATTED DOCUMENTS FOR AI ===")
        print(formatted_docs)
        print("\n" + "="*80)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_document_formatting())
