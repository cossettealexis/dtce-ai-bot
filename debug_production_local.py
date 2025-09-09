#!/usr/bin/env python3
"""
DEBUG: Compare Local vs Production Configuration
Test the same question using the same code paths to identify differences
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def debug_configuration_differences():
    """Test configuration and response differences between local and what production would use."""
    
    try:
        from dtce_ai_bot.services.rag_handler import RAGHandler
        from dtce_ai_bot.config.settings import Settings
        from azure.search.documents.aio import SearchClient
        from azure.core.credentials import AzureKeyCredential
        from openai import AsyncAzureOpenAI
        
        print("🔍 DEBUGGING LOCAL vs PRODUCTION CONFIGURATION")
        print("=" * 80)
        
        # Load settings (same as production would)
        settings = Settings()
        
        print("📋 CONFIGURATION CHECK:")
        print(f"Environment: {settings.environment}")
        print(f"Azure OpenAI Endpoint: {settings.azure_openai_endpoint[:50]}..." if settings.azure_openai_endpoint else "NOT SET")
        print(f"Azure OpenAI Deployment: {settings.azure_openai_deployment_name}")
        print(f"Azure OpenAI API Version: {settings.azure_openai_api_version}")
        print(f"Azure Search Service: {settings.azure_search_service_name}")
        print(f"Azure Search Index: {settings.azure_search_index_name}")
        print(f"Model Name: {settings.azure_openai_deployment_name}")
        print()
        
        # Initialize exactly like production Teams bot does via DocumentQAService
        print("🤖 INITIALIZING SERVICES (Production Path):")
        
        # Same initialization as DocumentQAService
        search_client = SearchClient(
            endpoint=f'https://{settings.azure_search_service_name}.search.windows.net',
            index_name=settings.azure_search_index_name,
            credential=AzureKeyCredential(settings.azure_search_admin_key)
        )
        
        openai_client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint
        )
        
        rag_handler = RAGHandler(search_client, openai_client, settings.azure_openai_deployment_name)
        print("✅ RAG Handler initialized successfully")
        print()
        
        # Test the EXACT same question that works locally but fails in Teams
        test_question = "What is our wellness policy?"
        
        print(f"❓ TESTING QUESTION: {test_question}")
        print("-" * 50)
        
        # Call process_question (same as Teams bot does)
        result = await rag_handler.process_question(test_question)
        
        print("📊 RESULT ANALYSIS:")
        print(f"Response Type: {result.get('rag_type', 'unknown')}")
        print(f"Search Method: {result.get('search_method', 'unknown')}")
        print(f"Documents Found: {result.get('documents_searched', 0)}")
        print(f"Confidence: {result.get('confidence', 'unknown')}")
        print()
        
        print("💬 AI RESPONSE:")
        print("-" * 50)
        answer = result.get('answer', 'No answer provided')
        print(answer[:500] + "..." if len(answer) > 500 else answer)
        print()
        
        print("📄 SOURCES:")
        sources = result.get('sources', [])
        for i, source in enumerate(sources[:3], 1):
            print(f"{i}. {source.get('filename', 'Unknown')}")
            if source.get('link'):
                print(f"   SuiteFiles: {source['link']}")
        print()
        
        # Test search functionality directly
        print("🔍 DIRECT SEARCH TEST:")
        print("-" * 50)
        from dtce_ai_bot.services.semantic_search import SemanticSearch
        semantic_search = SemanticSearch(search_client)
        
        search_docs = await semantic_search.search_documents("wellness policy", None)
        print(f"Direct search found: {len(search_docs)} documents")
        for i, doc in enumerate(search_docs[:3], 1):
            print(f"{i}. {doc.get('filename', 'Unknown')} (score: {doc.get('@search.score', 0):.3f})")
        print()
        
        print("✅ DIAGNOSTIC COMPLETE")
        print("=" * 80)
        
        # If we get here with good results, the issue might be:
        # 1. Environment variables different in Azure
        # 2. Different Azure OpenAI model behavior in production
        # 3. Network/latency issues affecting response quality
        # 4. Teams message formatting or truncation
        
        return result
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    asyncio.run(debug_configuration_differences())
