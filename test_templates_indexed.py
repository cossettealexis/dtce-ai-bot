"""
Quick test to verify Templates files are indexed and searchable
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.config.settings import Settings
from dtce_ai_bot.services.azure_rag_service_v2 import RAGOrchestrator
from azure.search.documents.aio import SearchClient
from azure.core.credentials import AzureKeyCredential
from openai import AsyncAzureOpenAI

async def test_templates():
    """Test if bot can answer Templates questions"""
    
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
    
    orchestrator = RAGOrchestrator(
        search_client=search_client,
        openai_client=openai_client,
        model_name=settings.azure_openai_deployment_name,
        max_retries=3
    )
    
    # Test queries about Templates
    test_queries = [
        "what fee proposal templates does DTCE have?",
        "show me templates from the Templates folder",
        "what templates are available for projects?",
    ]
    
    print("=" * 80)
    print("🧪 TESTING TEMPLATES INDEXING")
    print("=" * 80)
    print()
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*80}")
        print(f"Test {i}: '{query}'")
        print('-' * 80)
        
        try:
            response = await orchestrator.process_query(
                user_query=query,
                conversation_history=[]
            )
            
            # Check if Templates folder is mentioned in sources
            templates_found = False
            sources = response.get('sources', [])
            for source in sources:
                if 'Templates/' in source.get('folder', ''):
                    templates_found = True
                    print(f"\n✅ FOUND Templates file: {source.get('filename', 'Unknown')}")
                    print(f"   Folder: {source.get('folder', 'Unknown')}")
            
            print(f"\n📄 Answer Preview (first 300 chars):")
            answer = response.get('answer', str(response))
            print(answer[:300] + "...")
            
            if templates_found:
                print(f"\n✅ SUCCESS: Bot found Templates files!")
            else:
                print(f"\n⚠️  WARNING: No Templates files in sources")
                
        except Exception as e:
            print(f"\n❌ ERROR: {str(e)}")
    
    print("\n" + "=" * 80)
    print("🧪 TEST COMPLETE")
    print("=" * 80)
    
    await search_client.close()
    await openai_client.close()

if __name__ == "__main__":
    asyncio.run(test_templates())
