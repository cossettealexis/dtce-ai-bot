#!/usr/bin/env python3

import os
import sys
import asyncio
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

async def test_full_rag():
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
        
        print("=== TESTING FULL RAG QUERY ===")
        print("Query: 'wellness policy'")
        
        # Process the full RAG query
        result = await rag_handler.process_rag_query("wellness policy")
        
        print(f"\n--- RAG RESULT ---")
        print(f"Answer: {result['answer']}")
        print(f"\nSources ({len(result.get('sources', []))}):")
        for i, source in enumerate(result.get('sources', []), 1):
            print(f"{i}. {source}")
        
        print(f"\nConfidence: {result.get('confidence', 'unknown')}")
        print(f"Documents searched: {result.get('documents_searched', 0)}")
        print(f"RAG type: {result.get('rag_type', 'unknown')}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_full_rag())
