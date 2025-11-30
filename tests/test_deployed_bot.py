"""
Quick test script to verify the deployed bot is working correctly
"""
import asyncio
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dtce_ai_bot.config.settings import Settings
from dtce_ai_bot.services.azure_rag_service_v2 import RAGOrchestrator
from azure.search.documents.aio import SearchClient
from azure.core.credentials import AzureKeyCredential
from openai import AsyncAzureOpenAI

async def test_queries():
    """Test the bot with various queries"""
    
    # Load settings
    settings = Settings()
    
    # Initialize clients
    search_client = SearchClient(
        endpoint=settings.azure_search_service_endpoint,
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_api_key)
    )
    
    openai_client = AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version="2024-08-01-preview",
        azure_endpoint=settings.azure_openai_endpoint
    )
    
    # Initialize orchestrator
    orchestrator = RAGOrchestrator(
        search_client=search_client,
        openai_client=openai_client,
        model_name=settings.azure_openai_deployment_name,
        max_retries=3
    )
    
    # Test queries
    test_cases = [
        "show me 2024 projects",
        "give me project numbers from 2024",
        "show me project numbers from the past 4 years"
    ]
    
    print("=" * 80)
    print("TESTING DEPLOYED BOT")
    print("=" * 80)
    
    for i, query in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"TEST {i}: {query}")
        print(f"{'='*80}")
        
        try:
            result = await orchestrator.process_question(query, session_id="test")
            
            print(f"\n✓ Intent: {result.get('intent', 'N/A')}")
            print(f"✓ Filter: {result.get('search_filter', 'N/A')}")
            print(f"✓ Total Documents: {result.get('total_documents', 0)}")
            print(f"\n✓ Answer Preview (first 500 chars):")
            print("-" * 80)
            answer = result.get('answer', '')
            print(answer[:500] + "..." if len(answer) > 500 else answer)
            
            # Check if it found projects
            if 'project' in answer.lower() and any(char.isdigit() for char in answer):
                print(f"\n✓ SUCCESS: Found project numbers in response")
            else:
                print(f"\n✗ WARNING: No project numbers detected in response")
                
        except Exception as e:
            print(f"\n✗ ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
    
    await search_client.close()
    await openai_client.close()

if __name__ == "__main__":
    asyncio.run(test_queries())
