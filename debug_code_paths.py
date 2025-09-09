#!/usr/bin/env python3
"""
DEBUG: Compare exact same question through both code paths
Teams bot path vs Local test path
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def compare_code_paths():
    """Compare the exact same question through both code paths."""
    
    try:
        from dtce_ai_bot.services.rag_handler import RAGHandler
        from dtce_ai_bot.services.document_qa import DocumentQAService
        from dtce_ai_bot.config.settings import Settings
        from azure.search.documents.aio import SearchClient
        from azure.core.credentials import AzureKeyCredential
        from openai import AsyncAzureOpenAI
        
        print("🔄 COMPARING CODE PATHS: Local Test vs Teams Bot")
        print("=" * 80)
        
        # Initialize exactly the same way both paths do
        settings = Settings()
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
        
        # Test question
        test_question = "What is our wellness policy?"
        
        print(f"❓ Testing question: {test_question}")
        print()
        
        # PATH 1: Direct RAG Handler (Local test way)
        print("🔬 PATH 1: Direct RAG Handler (Local Test)")
        print("-" * 50)
        rag_handler = RAGHandler(search_client, openai_client, settings.azure_openai_deployment_name)
        result1 = await rag_handler.process_question(test_question)
        
        print(f"Response Type: {result1.get('rag_type', 'unknown')}")
        print(f"Documents Found: {result1.get('documents_searched', 0)}")
        print(f"Answer Length: {len(result1.get('answer', ''))}")
        print(f"Answer Preview: {result1.get('answer', '')[:200]}...")
        print()
        
        # PATH 2: Through DocumentQAService (Teams bot way)
        print("🤖 PATH 2: Through DocumentQAService (Teams Bot)")
        print("-" * 50)
        qa_service = DocumentQAService(search_client)
        result2 = await qa_service.answer_question(test_question)
        
        print(f"Response Type: {result2.get('rag_type', 'unknown')}")
        print(f"Documents Found: {result2.get('documents_searched', 0)}")
        print(f"Answer Length: {len(result2.get('answer', ''))}")
        print(f"Answer Preview: {result2.get('answer', '')[:200]}...")
        print()
        
        # PATH 3: Teams bot actual call
        print("📱 PATH 3: Teams Bot Actual Call")
        print("-" * 50)
        result3 = await qa_service.rag_handler.process_question(test_question)
        
        print(f"Response Type: {result3.get('rag_type', 'unknown')}")
        print(f"Documents Found: {result3.get('documents_searched', 0)}")
        print(f"Answer Length: {len(result3.get('answer', ''))}")
        print(f"Answer Preview: {result3.get('answer', '')[:200]}...")
        print()
        
        # Compare results
        print("📊 COMPARISON ANALYSIS")
        print("=" * 50)
        
        # Check if answers are the same
        answer1 = result1.get('answer', '')
        answer2 = result2.get('answer', '')
        answer3 = result3.get('answer', '')
        
        print(f"Path 1 vs Path 2 same: {answer1 == answer2}")
        print(f"Path 1 vs Path 3 same: {answer1 == answer3}")
        print(f"Path 2 vs Path 3 same: {answer2 == answer3}")
        
        print(f"All three identical: {answer1 == answer2 == answer3}")
        
        if answer1 != answer2:
            print("\n❌ FOUND DIFFERENCE: DocumentQAService gives different results!")
            print("This explains why Teams bot differs from local test.")
        elif answer1 != answer3:
            print("\n❌ FOUND DIFFERENCE: Teams bot actual call differs!")
        else:
            print("\n✅ All paths give identical results - issue must be elsewhere")
            
        return result1, result2, result3
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None, None

if __name__ == "__main__":
    asyncio.run(compare_code_paths())
