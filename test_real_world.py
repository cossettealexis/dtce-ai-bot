#!/usr/bin/env python3
"""
Test real-world engineering questions with the intelligent system.
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dtce_ai_bot.services.document_qa import DocumentQAService
from dtce_ai_bot.config.settings import get_settings
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

async def test_real_world_questions():
    """Test real-world engineering questions that engineers actually ask."""
    
    print("🏗️ Testing Real-World Engineering Questions")
    print("=" * 60)
    
    # Initialize services
    settings = get_settings()
    search_endpoint = f"https://{settings.azure_search_service_name}.search.windows.net"
    
    search_client = SearchClient(
        endpoint=search_endpoint,
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_admin_key)
    )
    
    qa_service = DocumentQAService(search_client)
    
    # Real questions engineers ask (mix of RAG and non-RAG)
    real_questions = [
        # Design questions (likely no RAG match)
        "I need to design a 8m span steel beam for a warehouse. What size should I use?",
        "How do I calculate the capacity of a 300mm concrete column?",
        "What's the maximum cantilever length for a timber deck?",
        
        # Code questions (might match RAG)
        "What does NZS 3101 say about minimum concrete cover?",
        "Tell me about strength reduction factors for beams",
        
        # Project questions (might match RAG)
        "Show me past projects with precast panels",
        "What timber projects have we done in Wellington?",
        
        # Mixed questions (probably no RAG match)
        "How do we handle differential settlement in foundations?",
        "What's the best connection detail for steel to concrete?",
        "How do I design for 50 year return period wind loads?",
        
        # Practical questions (probably no RAG match)
        "What's causing cracking in this concrete slab?",
        "How do I fix a sagging timber beam?",
        "What inspection points are critical for steel construction?"
    ]
    
    print(f"Testing {len(real_questions)} real-world questions...\n")
    
    for i, question in enumerate(real_questions, 1):
        print(f"🔍 Q{i}: {question}")
        print("-" * 70)
        
        try:
            # Use the full QA service (includes RAG check + intelligent fallback)
            response = await qa_service.answer_question(question)
            
            print(f"🎯 Search Type: {response.get('search_type', response.get('rag_type', 'Unknown'))}")
            print(f"📊 Confidence: {response.get('confidence', 'Unknown')}")
            print(f"📄 Documents: {response.get('documents_searched', 0)}")
            
            if 'intent' in response:
                print(f"🧠 Intent: {response.get('intent')}")
            
            answer = response.get('answer', '')
            print(f"💬 Answer ({len(answer)} chars): {answer[:200]}...")
            
            sources = response.get('sources', [])
            if sources:
                print(f"📁 Sources: {len(sources)} documents")
                for j, source in enumerate(sources[:2], 1):
                    print(f"  {j}. {source.get('filename', 'Unknown')}")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
        
        print()
    
    print("🎉 Real-world question testing complete!")
    print("\n💡 Key Benefits:")
    print("• RAG patterns handle specific DTCE workflow questions")
    print("• Intelligent fallback handles general engineering questions") 
    print("• GPT provides natural, conversational answers")
    print("• Always searches documents first before giving answers")
    print("• Maintains engineering accuracy with document context")

if __name__ == "__main__":
    asyncio.run(test_real_world_questions())
