#!/usr/bin/env python3
"""
Direct test of the categorization method
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
from openai import AsyncAzureOpenAI

async def test_categorization():
    """Test just the categorization method."""
    print("🔍 Testing Question Categorization")
    print("=" * 40)
    
    try:
        settings = Settings()
        
        # Initialize clients
        search_endpoint = f"https://{settings.azure_search_service_name}.search.windows.net"
        search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=settings.azure_search_index_name,
            credential=AzureKeyCredential(settings.azure_search_admin_key)
        )
        
        openai_client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint
        )
        
        rag = RAGHandler(
            search_client=search_client,
            openai_client=openai_client,
            model_name=settings.azure_openai_deployment_name
        )
        
        # Test categorization directly
        test_questions = [
            "What is the wellness policy?",
            "How much should project 225 cost?",
            "What NZ standards apply to concrete?",
            "How do I submit timesheets?"
        ]
        
        for question in test_questions:
            print(f"\n📝 Question: {question}")
            try:
                strategy = await rag._determine_search_strategy(question)
                print(f"   Category: {strategy.get('prompt_category')}")
                print(f"   Confidence: {strategy.get('confidence')}")
                print(f"   Reasoning: {strategy.get('reasoning')}")
                print(f"   DTCE Search Needed: {strategy.get('needs_dtce_search')}")
            except Exception as e:
                print(f"   ERROR: {e}")
        
        await search_client.close()
        await openai_client.close()
        
    except Exception as e:
        print(f"❌ Setup Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_categorization())
