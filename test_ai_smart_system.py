#!/usr/bin/env python3
"""
Test the AI-smart system without keyword filtering
"""
import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.services.rag_handler import RAGHandler
from dtce_ai_bot.config.settings import Settings
from azure.search.documents.aio import SearchClient
from azure.core.credentials import AzureKeyCredential
from openai import AsyncAzureOpenAI, AsyncOpenAI

async def test_ai_smart_responses():
    """Test the AI-smart system responses."""
    print("🧠 Testing AI-Smart DTCE Bot (No Keyword Filtering)")
    print("=" * 60)
    
    try:
        # Initialize settings and clients
        settings = Settings()
        
        # Initialize Azure Search client
        search_endpoint = f"https://{settings.azure_search_service_name}.search.windows.net"
        search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=settings.azure_search_index_name,
            credential=AzureKeyCredential(settings.azure_search_admin_key)
        )
        
        # Initialize OpenAI client for Azure OpenAI
        if settings.azure_openai_endpoint:
            # Use Azure OpenAI
            openai_client = AsyncAzureOpenAI(
                api_key=settings.azure_openai_api_key,
                api_version=settings.azure_openai_api_version,
                azure_endpoint=settings.azure_openai_endpoint
            )
            model_name = settings.azure_openai_deployment_name
        else:
            # Use regular OpenAI
            openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
            model_name = settings.openai_model_name
        
        # Initialize RAG handler properly
        rag = RAGHandler(
            search_client=search_client,
            openai_client=openai_client,
            model_name=model_name
        )
        
        # Test questions that should work with AI intelligence
        test_questions = [
            "What is the wellness policy?",  # Same question that was inconsistent
            "Tell me about employee wellbeing",  # Related but different phrasing
            "How much should project 225 cost?",  # Project reference test
            "What NZ standards apply to concrete?",  # Standards test
        ]
        
        for i, question in enumerate(test_questions, 1):
            print(f"\n{i}. Testing: '{question}'")
            print("-" * 40)
            
            try:
                result = await rag.universal_ai_assistant(question)
                
                print(f"📄 Category: {result.get('category', result.get('prompt_category', 'Unknown'))}")
                print(f"📊 Documents Found: {result.get('document_count', result.get('documents_searched', 0))}")
                print(f"💡 Response Preview: {result.get('response', result.get('answer', 'No response'))[:200]}...")
                
                # Debug: show full result keys
                print(f"🔍 Debug - Available keys: {list(result.keys())}")
                
            except Exception as e:
                print(f"❌ Error: {e}")
    
    except Exception as e:
        print(f"❌ Setup Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_ai_smart_responses())
