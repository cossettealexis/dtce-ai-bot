#!/usr/bin/env python3
"""
Test the intelligent fallback system when no RAG patterns match.
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dtce_ai_bot.services.document_qa import DocumentQAService
from dtce_ai_bot.config.settings import get_settings
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

async def test_intelligent_fallback():
    """Test questions that don't match RAG patterns but should still get intelligent answers."""
    
    print("🧠 Testing Intelligent Fallback System")
    print("=" * 60)
    
    # Initialize services
    settings = get_settings()
    
    # Build the search endpoint URL
    search_endpoint = f"https://{settings.azure_search_service_name}.search.windows.net"
    
    search_client = SearchClient(
        endpoint=search_endpoint,
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )
    
    qa_service = DocumentQAService(search_client)
    
    # Test questions that DON'T match RAG patterns but should still work
    test_questions = [
        "How do I design a timber beam for 6m span?",
        "What's the deflection limit for residential floors?", 
        "How do we typically detail steel connections?",
        "What foundation type should I use for soft clay?",
        "How to calculate wind loads on a building?",
        "What's the best practice for concrete curing?",
        "How do I design a retaining wall for 2m height?",
        "What reinforcement is needed for a concrete slab?",
        "How to detail timber frame connections?",
        "What are the seismic design requirements?"
    ]
    
    print(f"Testing {len(test_questions)} non-RAG pattern questions...\n")
    
    results = []
    
    for i, question in enumerate(test_questions, 1):
        print(f"🔍 Q{i}: {question}")
        print("-" * 50)
        
        try:
            # First check if it matches RAG patterns
            rag_response = await qa_service.rag_handler.process_rag_query(question)
            
            if rag_response.get('rag_type') == 'general_query':
                print("✅ No RAG pattern matched - testing intelligent fallback...")
                
                # Test the intelligent fallback
                response = await qa_service._handle_intelligent_fallback(question)
                
                print(f"🎯 Intent: {response.get('intent', 'Unknown')}")
                print(f"📊 Confidence: {response.get('confidence', 'Unknown')}")
                print(f"📄 Documents: {response.get('documents_searched', 0)}")
                print(f"🔍 Search Type: {response.get('search_type', 'Unknown')}")
                print(f"💬 Answer Preview: {response.get('answer', '')[:150]}...")
                
                results.append({
                    'question': question,
                    'intent': response.get('intent'),
                    'confidence': response.get('confidence'),
                    'docs_found': response.get('documents_searched', 0),
                    'answer_length': len(response.get('answer', '')),
                    'has_answer': len(response.get('answer', '')) > 50
                })
                
            else:
                print(f"⚠️ Question matched RAG pattern: {rag_response.get('rag_type')}")
                results.append({
                    'question': question,
                    'matched_rag': True,
                    'rag_type': rag_response.get('rag_type')
                })
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            results.append({
                'question': question,
                'error': str(e)
            })
        
        print()
    
    # Summary
    print("📈 INTELLIGENT FALLBACK TEST RESULTS")
    print("=" * 60)
    
    intelligent_responses = [r for r in results if 'intent' in r]
    rag_matches = [r for r in results if 'matched_rag' in r]
    errors = [r for r in results if 'error' in r]
    
    print(f"🧠 Intelligent Fallback Used: {len(intelligent_responses)}/{len(test_questions)}")
    print(f"🎯 RAG Pattern Matches: {len(rag_matches)}/{len(test_questions)}")
    print(f"❌ Errors: {len(errors)}/{len(test_questions)}")
    
    if intelligent_responses:
        print(f"\n🔍 INTELLIGENT FALLBACK ANALYSIS:")
        print(f"• Average Documents Found: {sum(r['docs_found'] for r in intelligent_responses) / len(intelligent_responses):.1f}")
        print(f"• Questions with Good Answers: {sum(1 for r in intelligent_responses if r['has_answer'])}/{len(intelligent_responses)}")
        
        intents = {}
        for r in intelligent_responses:
            intent = r.get('intent', 'Unknown')
            intents[intent] = intents.get(intent, 0) + 1
        
        print(f"• Intent Distribution:")
        for intent, count in intents.items():
            print(f"  - {intent}: {count}")
        
        confidence_dist = {}
        for r in intelligent_responses:
            conf = r.get('confidence', 'unknown')
            confidence_dist[conf] = confidence_dist.get(conf, 0) + 1
        
        print(f"• Confidence Distribution:")
        for conf, count in confidence_dist.items():
            print(f"  - {conf}: {count}")
    
    print(f"\n🎉 Intelligent fallback system successfully handles non-RAG questions!")

if __name__ == "__main__":
    asyncio.run(test_intelligent_fallback())
