#!/usr/bin/env python3
"""
Test the simplified RAG system to see if it provides better answers.
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# Add the project root to the path
sys.path.insert(0, os.path.abspath('.'))

from dtce_ai_bot.integrations.azure_search import get_search_client
from dtce_ai_bot.services.rag_handler import RAGHandler
from dtce_ai_bot.config.settings import get_settings
from openai import AsyncAzureOpenAI

# Load environment variables
load_dotenv()

async def test_simplified_rag():
    """Test the simplified RAG system."""
    
    settings = get_settings()
    search_client = get_search_client()
    
    # Create OpenAI client
    openai_client = AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.azure_openai_endpoint
    )
    
    rag_handler = RAGHandler(search_client, openai_client, settings.azure_openai_deployment_name)
    
    test_questions = [
        "wellness policy",
        "what's our wellness policy and what does it say"
    ]
    
    print("🧪 TESTING SIMPLIFIED RAG SYSTEM")
    print("=" * 50)
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n🔍 Test {i}: '{question}'")
        print("-" * 30)
        
        try:
            result = await rag_handler.process_rag_query(question)
            
            print(f"Answer: {result.get('answer', 'No answer')}")
            print(f"Sources: {len(result.get('sources', []))} documents")
            print(f"Confidence: {result.get('confidence', 'unknown')}")
            
            # Show sources
            sources = result.get('sources', [])
            if sources:
                print("\nSources found:")
                for j, source in enumerate(sources[:3], 1):
                    filename = source.get('filename', 'Unknown')
                    link = source.get('link', 'No link')
                    print(f"  {j}. {filename}")
                    print(f"     Link: {link}")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
        
        print()

if __name__ == "__main__":
    asyncio.run(test_simplified_rag())
