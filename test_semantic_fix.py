#!/usr/bin/env python3
"""
Test the semantic search fix
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.services.document_qa import DocumentQAService
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from dtce_ai_bot.config.settings import get_settings

async def test_semantic_search():
    """Test if semantic search now works for wellness/wellbeing"""
    
    print("🧠 TESTING SEMANTIC SEARCH FIX")
    print("=" * 50)
    
    try:
        settings = get_settings()
        
        search_client = SearchClient(
            endpoint=f"https://{settings.azure_search_service_name}.search.windows.net",
            index_name=settings.azure_search_index_name,
            credential=AzureKeyCredential(settings.azure_search_admin_key)
        )
        
        qa_service = DocumentQAService(search_client)
        
        # Test the wellness policy query
        query = "what is our wellness policy"
        print(f"🔍 Testing: '{query}'")
        print("-" * 50)
        
        result = await qa_service.answer_question(query)
        
        answer = result.get('answer', 'No answer')
        rag_type = result.get('rag_type', 'unknown')
        sources = result.get('sources', [])
        confidence = result.get('confidence', 'unknown')
        
        print(f"📝 Answer: {answer[:300]}...")
        print(f"🎯 RAG Type: {rag_type}")
        print(f"💪 Confidence: {confidence}")
        print(f"📚 Sources Found: {len(sources)}")
        
        if sources:
            print("\n📄 Top Sources:")
            for i, source in enumerate(sources[:3], 1):
                filename = source.get('filename', 'Unknown')
                print(f"   {i}. {filename}")
        
        # Check if it found actual wellness policy content
        if "wellness policy" in answer.lower() or "wellbeing policy" in answer.lower():
            if len(sources) > 0:
                print("\n✅ SUCCESS: Found wellness policy documents!")
            else:
                print("\n⚠️ Found policy mention but no sources")
        else:
            print("\n❌ Still not finding wellness policy properly")
        
        print(f"\n🎯 TEST COMPLETE")
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_semantic_search())
