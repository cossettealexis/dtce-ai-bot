#!/usr/bin/env python3

import os
import sys
import asyncio
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

async def test_semantic_search_documents():
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
        
        print("=== TESTING SEMANTIC SEARCH FOR 'wellness policy' ===")
        
        # Test what semantic search returns
        try:
            documents = await rag_handler.semantic_search.search_documents("wellness policy")
            print(f"Semantic search returned {len(documents)} documents")
            
            for i, doc in enumerate(documents[:8], 1):
                filename = doc.get('filename', 'Unknown')
                blob_name = doc.get('blob_name', '') or filename
                print(f"{i}. {filename}")
                print(f"   Path: {blob_name}")
                
                # Check if superseded
                is_superseded = any(term in blob_name.lower() for term in ['superseded', 'superceded', 'archive', 'old'])
                print(f"   Superseded: {is_superseded}")
                print()
                
        except Exception as e:
            print(f"Semantic search failed: {e}")
            print("Trying direct search instead...")
            
            # Fallback to direct search
            documents = await rag_handler._search_documents("wellness policy", use_semantic=False)
            print(f"Direct search returned {len(documents)} documents")
            
            for i, doc in enumerate(documents[:8], 1):
                filename = doc.get('filename', 'Unknown')
                blob_name = doc.get('blob_name', '') or filename
                print(f"{i}. {filename}")
                print(f"   Path: {blob_name}")
                
                # Check if superseded
                is_superseded = any(term in blob_name.lower() for term in ['superseded', 'superceded', 'archive', 'old'])
                print(f"   Superseded: {is_superseded}")
                print()
        
        # Also test what we get for "health safety" which should have current documents
        print("\\n=== TESTING SEMANTIC SEARCH FOR 'health safety' ===")
        try:
            health_docs = await rag_handler.semantic_search.search_documents("health safety")
            print(f"Health safety search returned {len(health_docs)} documents")
            
            current_docs = []
            for doc in health_docs[:8]:
                filename = doc.get('filename', 'Unknown')
                blob_name = doc.get('blob_name', '') or filename
                is_superseded = any(term in blob_name.lower() for term in ['superseded', 'superceded', 'archive', 'old'])
                if not is_superseded:
                    current_docs.append(doc)
                    
            print(f"Found {len(current_docs)} current (non-superseded) documents")
            for i, doc in enumerate(current_docs[:5], 1):
                print(f"{i}. {doc.get('filename', 'Unknown')}")
                
        except Exception as e:
            print(f"Health safety semantic search failed: {e}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_semantic_search_documents())
