#!/usr/bin/env python3

import os
import sys
import asyncio
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

async def debug_ai_prompt():
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
        
        rag_handler = RAGHandler(
            search_client=search_client,
            openai_client=openai_client,
            model_name="gpt-4"
        )
        
        # Get some documents using direct search
        documents = await rag_handler._search_documents(
            "health safety policy", 
            use_semantic=False
        )
        
        # Filter to current documents only
        current_docs = []
        for doc in documents:
            blob_name = doc.get('blob_name', '') or doc.get('filename', '')
            is_superseded = any(term in blob_name.lower() for term in ['superseded', 'superceded', 'archive', 'old'])
            if not is_superseded:
                current_docs.append(doc)
        
        print(f"Found {len(current_docs)} current documents")
        
        if current_docs:
            # Check what the formatted content looks like
            retrieved_content = rag_handler._format_documents_simple(current_docs[:2])
            
            print("=== FORMATTED CONTENT SENT TO AI ===")
            print(retrieved_content)
            print("\\n" + "="*80)
            
            # Check document formatting with folder context
            folder_context = {"query_type": "policy"}
            formatted_with_context = rag_handler._format_documents_with_folder_context(current_docs[:2], folder_context)
            
            print("=== FORMATTED WITH CONTEXT ===")
            print(formatted_with_context)
            print("\\n" + "="*80)
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_ai_prompt())
