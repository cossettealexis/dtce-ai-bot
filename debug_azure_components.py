#!/usr/bin/env python3
"""
Simple test to verify what's actually deployed in Azure and working
"""

import asyncio
import sys
import os
import traceback

# Add the project root to path
sys.path.insert(0, os.path.abspath('.'))

from dtce_ai_bot.config.settings import get_settings
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from openai import AsyncAzureOpenAI

async def test_azure_components():
    """Test each Azure component individually"""
    
    settings = get_settings()
    
    print("🔧 Testing Azure Components Individually")
    print("="*60)
    
    # 1. Test Azure Search Client
    try:
        print("\n1️⃣ Testing Azure Search Client...")
        search_client = SearchClient(
            endpoint=settings.azure_search_endpoint,
            index_name=settings.azure_search_index_name,
            credential=AzureKeyCredential(settings.azure_search_key)
        )
        
        # Simple search test
        results = search_client.search("test", top=1)
        result_list = list(results)
        print(f"✅ Azure Search works - found {len(result_list)} results")
        
    except Exception as e:
        print(f"❌ Azure Search failed: {e}")
        traceback.print_exc()
        return
    
    # 2. Test Azure OpenAI Client
    try:
        print("\n2️⃣ Testing Azure OpenAI Client...")
        openai_client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint
        )
        
        # Test simple completion
        response = await openai_client.chat.completions.create(
            model=settings.azure_openai_deployment_name,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10
        )
        print(f"✅ Azure OpenAI works - response: {response.choices[0].message.content}")
        
    except Exception as e:
        print(f"❌ Azure OpenAI failed: {e}")
        traceback.print_exc()
        return
    
    # 3. Test embedding model
    try:
        print("\n3️⃣ Testing Embedding Model...")
        embeddings = await openai_client.embeddings.create(
            input=["test text"],
            model="text-embedding-3-small"  # This might be the issue
        )
        print(f"✅ Embeddings work - got {len(embeddings.data[0].embedding)} dimensions")
        
    except Exception as e:
        print(f"❌ Embeddings failed: {e}")
        print("This is likely the issue!")
        traceback.print_exc()
    
    # 4. Test RAG Handler initialization
    try:
        print("\n4️⃣ Testing RAG Handler...")
        from dtce_ai_bot.services.rag_handler import RAGHandler
        
        rag_handler = RAGHandler(search_client, openai_client, settings.azure_openai_deployment_name, settings)
        print("✅ RAG Handler initialized successfully")
        
    except Exception as e:
        print(f"❌ RAG Handler failed: {e}")
        traceback.print_exc()
    
    # 5. Test Document QA Service
    try:
        print("\n5️⃣ Testing Document QA Service...")
        from dtce_ai_bot.services.document_qa import DocumentQAService
        
        qa_service = DocumentQAService(search_client)
        print("✅ Document QA Service initialized successfully")
        
    except Exception as e:
        print(f"❌ Document QA Service failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_azure_components())
