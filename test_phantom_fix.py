#!/usr/bin/env python3

import asyncio
import sys
import os
sys.path.append('.')

from dtce_ai_bot.services.rag_handler import RAGHandler
from dtce_ai_bot.config.settings import get_settings
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from openai import AsyncAzureOpenAI

async def test_fixed_search():
    """Test if the phantom document fix resolves the wellbeing policy search issue."""
    
    settings = get_settings()
    
    # Build search endpoint URL
    search_endpoint = f"https://{settings.azure_search_service_name}.search.windows.net"
    
    # Initialize search client
    search_client = SearchClient(
        endpoint=search_endpoint,
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )
    
    # Initialize OpenAI client  
    openai_client = AsyncAzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version
    )
    
    rag = RAGHandler(search_client, openai_client, settings.azure_openai_deployment_name)
    
    print("🔍 Testing Fixed Phantom Document Detection")
    print("=" * 60)
    
    # Test the problematic query that was going to fallback
    query = "whats our wellbeing policy and what does it say"
    print(f"\n🧪 Testing Query: '{query}'")
    print("-" * 50)
    
    try:
        # Test search documents directly
        documents = await rag._search_documents(query)
        print(f"✅ Documents found: {len(documents)}")
        
        if documents:
            print("📄 Found documents:")
            for i, doc in enumerate(documents[:5], 1):
                filename = doc.get('filename', 'Unknown')
                content_len = len(doc.get('content', ''))
                print(f"   {i}. {filename} (content: {content_len} chars)")
                
                # Check if this would have been filtered as phantom before
                content = doc.get('content', '')
                if content and 50 < len(content) < 100:
                    print(f"      ⚠️  This would have been incorrectly filtered before (content: {len(content)} chars)")
        else:
            print("❌ No documents found - search still has issues")
            
        # Now test full RAG query
        print(f"\n🤖 Testing Full RAG Query...")
        result = await rag.process_rag_query(query)
        print(f"✅ RAG Type: {result.get('rag_type', 'unknown')}")
        print(f"✅ Documents Searched: {result.get('documents_searched', 0)}")
        print(f"✅ Sources: {len(result.get('sources', []))}")
        
        if result.get('rag_type') == 'gpt_knowledge_fallback':
            print("❌ STILL GOING TO FALLBACK! Need to investigate further.")
        else:
            print("✅ SUCCESS! Query now finds documents instead of going to fallback.")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_fixed_search())
