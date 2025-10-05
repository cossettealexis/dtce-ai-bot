#!/usr/bin/env python3
"""
Test actual construction questions
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.services.document_qa import DocumentQAService
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from dtce_ai_bot.config.settings import get_settings

async def test_construction_questions():
    """Test real construction questions"""
    
    print("🏗️ TESTING CONSTRUCTION QUESTIONS")
    print("=" * 60)
    
    try:
        settings = get_settings()
        
        search_client = SearchClient(
            endpoint=f"https://{settings.azure_search_service_name}.search.windows.net",
            index_name=settings.azure_search_index_name,
            credential=AzureKeyCredential(settings.azure_search_admin_key)
        )
        
        qa_service = DocumentQAService(search_client)
        
        # Test construction questions
        test_questions = [
            "test",
            "What are the maximum spans for 90x45mm joists?", 
            "What are NZS 3604 requirements?",
            "seismic design requirements",
            "timber beam calculations"
        ]
        
        for i, question in enumerate(test_questions, 1):
            print(f"\n🔍 Question {i}: '{question}'")
            print("-" * 50)
            
            try:
                result = await qa_service.answer_question(question)
                
                answer = result.get('answer', 'No answer')
                rag_type = result.get('rag_type', 'unknown')
                sources = len(result.get('sources', []))
                confidence = result.get('confidence', 'unknown')
                docs_searched = result.get('documents_searched', 0)
                
                print(f"📝 Answer: {answer[:200]}...")
                print(f"🎯 RAG Type: {rag_type}")
                print(f"💪 Confidence: {confidence}")
                print(f"📚 Sources: {sources}")
                print(f"🔍 Docs Searched: {docs_searched}")
                
                # Check quality
                if rag_type == 'azure_hybrid_rag':
                    print("✅ Using Azure RAG system")
                else:
                    print(f"❌ Wrong RAG type: {rag_type}")
                
                if "I don't have" in answer or "cannot provide" in answer:
                    print("⚠️ Generic 'no info' response")
                elif len(answer) > 100 and sources > 0:
                    print("✅ Good detailed response with sources")
                else:
                    print("⚠️ Short or unsourced response")
                    
            except Exception as e:
                print(f"❌ Error: {str(e)}")
        
        print(f"\n🎯 CONSTRUCTION QUESTIONS TEST COMPLETE")
        
    except Exception as e:
        print(f"❌ Setup failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_construction_questions())
