#!/usr/bin/env python3
"""
Test the new conversational RAG implementation.

This script tests the improved ChatGPT-like conversational responses
to ensure the bot now provides comprehensive, detailed answers rather
than just document links.
"""

import asyncio
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dtce_ai_bot.services.document_qa import DocumentQAService
from dtce_ai_bot.config.settings import get_settings
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential


async def test_conversational_rag():
    """Test the new conversational RAG implementation."""
    
    print("🤖 DTCE AI Bot - Conversational RAG Test")
    print("Testing the new ChatGPT-like responses\n")
    
    # Setup Azure Search client
    settings = get_settings()
    search_client = SearchClient(
        endpoint=settings.azure_search_endpoint,
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_api_key)
    )
    
    # Initialize Document QA service with new conversational RAG
    qa_service = DocumentQAService(search_client)
    
    # Test questions that should get comprehensive conversational answers
    test_questions = [
        {
            "question": "What's our wellness policy?",
            "expected": "Should provide detailed explanation of the policy content, not just a link"
        },
        {
            "question": "How do I report a safety incident?",
            "expected": "Should walk through the actual steps and procedures"
        },
        {
            "question": "What are the IT security requirements?",
            "expected": "Should list specific requirements and explain what employees need to do"
        },
        {
            "question": "Tell me about our project management procedures",
            "expected": "Should provide comprehensive overview of the process and requirements"
        }
    ]
    
    for i, test in enumerate(test_questions, 1):
        print(f"{'='*80}")
        print(f"TEST {i}: {test['question']}")
        print(f"Expected: {test['expected']}")
        print(f"{'='*80}")
        
        try:
            result = await qa_service.answer_question(test['question'])
            
            answer = result.get('answer', '')
            sources = result.get('sources', [])
            confidence = result.get('confidence', 'unknown')
            rag_type = result.get('rag_type', 'unknown')
            response_style = result.get('response_style', 'unknown')
            
            print(f"📝 ANSWER ({confidence} confidence):")
            print(answer)
            print()
            
            print(f"🔍 ANALYSIS:")
            print(f"  RAG Type: {rag_type}")
            print(f"  Response Style: {response_style}")
            print(f"  Documents Used: {len(sources)}")
            print(f"  Answer Length: {len(answer)} characters")
            
            # Analyze if this is a good conversational response
            if len(answer) > 200:
                print("  ✅ COMPREHENSIVE - Good length for detailed response")
            else:
                print("  ❌ TOO SHORT - May not be comprehensive enough")
            
            if "suitefiles" in answer.lower() and len(answer) > 300:
                print("  ✅ BALANCED - Includes links but also substantial content")
            elif "suitefiles" not in answer.lower():
                print("  ⚠️  NO LINKS - Missing document references")
            else:
                print("  ❌ LINK-HEAVY - May be too focused on links vs content")
            
            if any(word in answer.lower() for word in ['specifically', 'according to', 'the policy states', 'procedure', 'requirement']):
                print("  ✅ DETAILED - Contains specific information from documents")
            else:
                print("  ❌ VAGUE - May lack specific details from document content")
            
            print()
            print(f"📚 SOURCES ({len(sources)} documents):")
            for source in sources[:3]:  # Show first 3 sources
                print(f"  - {source.get('filename', 'Unknown')}")
            
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
        
        print("\n" + "="*80 + "\n")
    
    print("🎯 SUMMARY:")
    print("The new conversational RAG should provide:")
    print("✅ Detailed, comprehensive answers (not just links)")
    print("✅ ChatGPT-like conversational tone")
    print("✅ Specific information extracted from document content")
    print("✅ Well-structured responses with clear sections")
    print("✅ SuiteFiles links for reference at the end")


if __name__ == "__main__":
    asyncio.run(test_conversational_rag())
