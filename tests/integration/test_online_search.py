#!/usr/bin/env python3
"""
Test script to analyze how the AI bot handles online/web search queries.
"""

import asyncio
import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.services.document_qa import DocumentQAService
from dtce_ai_bot.integrations.azure_search import get_search_client

async def test_online_search_queries():
    """Test how the AI bot handles queries requiring online/web search."""
    
    # Test queries requiring online/external resources
    test_queries = [
        "Look for online threads or references about structural design procedures or current design discussions accessible to the public (especially NZ references / forums)",
        "I am currently designing a composite beam but need to make it haunched/tapered. Please provide related references or online threads mentioning the keyword 'tapered composite beam', preferably from anonymous structural engineers.",
        "Please provide design guidelines for a reinforced concrete column to withstand both seismic and gravity actions. If possible, include a legitimate link that gives direct access to the specific design guidelines."
    ]
    
    expected_output = "AI to search for and provide links to relevant public online discussions, technical forums, or reference articles that match the keywords. Where possible, AI should prioritize reputable engineering communities and professional sources."
    
    print("🌐 Testing Online/Web Search Query Capabilities")
    print("=" * 60)
    print(f"Expected Output: {expected_output}")
    print("=" * 60)
    
    try:
        # Initialize the search client and QA service
        search_client = get_search_client()
        qa_service = DocumentQAService(search_client)
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n📋 Test Query {i}:")
            print(f"Question: {query}")
            print("-" * 50)
            
            # Check routing
            is_keyword_query = qa_service._is_project_keyword_query(query)
            is_nz_standards_query = qa_service._is_nz_standards_query(query)
            
            print(f"Detected as keyword project query: {is_keyword_query}")
            print(f"Detected as NZ standards query: {is_nz_standards_query}")
            
            # Extract keywords
            keywords = qa_service._extract_keywords_from_question(query)
            print(f"Extracted keywords: {keywords}")
            
            # Get the answer
            try:
                result = await qa_service.answer_question(query)
                
                print(f"\n🤖 AI Response:")
                print(f"Answer: {result['answer'][:300]}{'...' if len(result['answer']) > 300 else ''}")
                print(f"Confidence: {result['confidence']}")
                print(f"Documents searched: {result['documents_searched']}")
                print(f"Sources found: {len(result['sources'])}")
                
                # Analyze the response type
                print(f"\n📊 Response Analysis:")
                if "http" in result['answer'] or "www." in result['answer']:
                    print("   ✅ Contains web links")
                else:
                    print("   ❌ No web links found")
                    
                if "forum" in result['answer'].lower() or "thread" in result['answer'].lower():
                    print("   ✅ Mentions forums/threads")
                else:
                    print("   ❌ No forum/thread references")
                    
                if "online" in result['answer'].lower() or "public" in result['answer'].lower():
                    print("   ✅ Addresses online/public resources")
                else:
                    print("   ❌ No online/public resource focus")
                
                # Check if it's giving internal documents vs external resources
                if any("Project" in source.get('filename', '') for source in result['sources']):
                    print("   ⚠️  Providing internal DTCE documents (not external resources)")
                else:
                    print("   ✅ Not limited to internal documents")
                
            except Exception as e:
                print(f"❌ Error processing query: {e}")
            
            print("\n" + "=" * 60)
            
        print(f"\n🔍 Current Capability Assessment:")
        print(f"   The current AI bot searches internal DTCE documents only")
        print(f"   It does NOT have web search capabilities")
        print(f"   To fulfill these queries, we would need to add:")
        print(f"   • Web search integration (Google, Bing, etc.)")
        print(f"   • Engineering forum search (Reddit, StackExchange, etc.)")
        print(f"   • Technical publication databases")
        print(f"   • External link validation and filtering")
    
    except Exception as e:
        print(f"❌ Failed to test: {e}")

if __name__ == "__main__":
    asyncio.run(test_online_search_queries())
