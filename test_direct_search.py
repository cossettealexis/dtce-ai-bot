#!/usr/bin/env python3

import os
import sys
import asyncio
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

async def test_direct_search():
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
        
        print("=== TESTING DIRECT SEARCH (NO SEMANTIC) ===")
        
        # Use direct search for current health & safety policy
        documents = await rag_handler._search_documents(
            "health safety policy", 
            project_filter=None, 
            use_semantic=False  # Use direct search, not semantic
        )
        
        print(f"Found {len(documents)} documents with direct search")
        
        # Filter out superseded documents
        current_docs = []
        for doc in documents:
            blob_name = doc.get('blob_name', '') or doc.get('filename', '')
            is_superseded = any(term in blob_name.lower() for term in ['superseded', 'superceded', 'archive', 'old'])
            if not is_superseded:
                current_docs.append(doc)
        
        print(f"After filtering superseded: {len(current_docs)} current documents")
        
        if current_docs:
            # Format documents and check links
            folder_context = {"query_type": "policy"}
            formatted_docs = rag_handler._format_documents_with_folder_context(current_docs[:3], folder_context)
            
            print("\\n=== FORMATTED DOCS (showing links) ===")
            print(formatted_docs[:1000] + "..." if len(formatted_docs) > 1000 else formatted_docs)
            
            # Now try to generate full RAG response with current docs
            retrieved_content = rag_handler._format_documents_simple(current_docs[:3])
            
            print("\\n=== TESTING FULL RAG WITH CURRENT DOCS ===")
            result = await rag_handler._process_rag_with_full_prompt(
                "health safety policy", 
                retrieved_content, 
                current_docs[:3]
            )
            
            print("ANSWER:")
            print(result['answer'][:500] + "..." if len(result['answer']) > 500 else result['answer'])
            
            print("\\nSOURCES:")
            for source in result.get('sources', []):
                print(f"- {source}")
        else:
            print("No current documents found!")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_direct_search())
