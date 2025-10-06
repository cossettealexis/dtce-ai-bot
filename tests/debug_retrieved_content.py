#!/usr/bin/env python3
"""
Debug script to see what's actually in the retrieved content for wellness policy
"""

import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.services.rag_handler import RAGHandler
from dtce_ai_bot.config.settings import Settings

async def debug_retrieved_content():
    """Debug what content is actually being retrieved"""
    print("🔍 Debugging retrieved content for wellness policy...")
    
    # Initialize the RAG handler properly
    settings = Settings()
    from openai import AsyncAzureOpenAI
    
    # Initialize Azure OpenAI client
    openai_client = AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.azure_openai_endpoint
    )
    
    rag_handler = RAGHandler(
        settings=settings,
        openai_client=openai_client,
        model_name=settings.azure_openai_deployment_name
    )
    
    # Test query
    test_query = "what's our wellness policy"
    
    try:
        # Get the search results directly from semantic search
        search_results = await rag_handler.semantic_search.search_documents(
            query=test_query,
            top_k=5
        )
        
        print(f"\n📊 Found {len(search_results)} documents")
        print("=" * 80)
        
        for i, doc in enumerate(search_results, 1):
            print(f"\n🗄️  DOCUMENT {i}:")
            print(f"Filename: {doc.get('filename', 'Unknown')}")
            print(f"Folder: {doc.get('folder', 'Unknown')}")
            
            # Check for various URL fields
            print(f"\nURL FIELDS:")
            print(f"  blob_url: {doc.get('blob_url', 'MISSING')}")
            print(f"  blobUrl: {doc.get('blobUrl', 'MISSING')}")
            print(f"  url: {doc.get('url', 'MISSING')}")
            print(f"  source_url: {doc.get('source_url', 'MISSING')}")
            
            # Show content snippet
            content = doc.get('content', '')
            print(f"\nContent snippet: {content[:200]}...")
            
            print("-" * 40)
        
        # Now see how it gets formatted
        print(f"\n📝 FORMATTED CONTENT:")
        print("=" * 80)
        formatted_content = rag_handler._format_documents_for_prompt(search_results)
        print(formatted_content[:2000] + "..." if len(formatted_content) > 2000 else formatted_content)
        
    except Exception as e:
        print(f"❌ Error during debug: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_retrieved_content())
