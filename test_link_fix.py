#!/usr/bin/env python3
"""
Test script to verify that the link hallucination fix is working.
This tests that the bot no longer generates fake '[link]' text.
"""

import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.services.rag_handler import RAGHandler
from dtce_ai_bot.config.settings import Settings

async def test_link_hallucination_fix():
    """Test that the bot no longer generates fake '[link]' text"""
    print("🔧 Testing link hallucination fix...")
    
    # Initialize the RAG handler
    settings = Settings()
    rag_handler = RAGHandler(settings)
    
    # Test query that should return documents with links
    test_query = "what's our wellness policy"
    
    try:
        print(f"📝 Testing query: '{test_query}'")
        response = await rag_handler.handle_query(test_query)
        
        # Check if the response contains the problematic fake link text
        if "SuiteFiles Link: [link]" in response:
            print("❌ FAILED: Found fake '[link]' text in response!")
            print("Response contains the hallucinated link format.")
            return False
        
        # Check if response contains real links
        if "https://" in response and "dtcestorage.blob.core.windows.net" in response:
            print("✅ SUCCESS: Found real SuiteFiles links in response!")
            print("Link hallucination appears to be fixed.")
            return True
        elif "https://" in response:
            print("✅ SUCCESS: Found real links (not necessarily SuiteFiles)")
            print("No fake '[link]' text detected.")
            return True
        else:
            print("⚠️  WARNING: No links found in response, but no fake '[link]' text either")
            print("This might be expected if no documents were retrieved.")
            return True
            
    except Exception as e:
        print(f"❌ ERROR during test: {e}")
        return False

async def test_semantic_search_consistency():
    """Test that 'wellness policy' and 'what's our wellness policy' return consistent results"""
    print("\n🔧 Testing semantic search consistency...")
    
    settings = Settings()
    rag_handler = RAGHandler(settings)
    
    queries = [
        "wellness policy",
        "what's our wellness policy"
    ]
    
    responses = []
    
    for query in queries:
        try:
            print(f"📝 Testing query: '{query}'")
            response = await rag_handler.handle_query(query)
            responses.append(response)
            
            # Quick check for fake links
            if "SuiteFiles Link: [link]" in response:
                print(f"❌ Found fake '[link]' in response for '{query}'")
                
        except Exception as e:
            print(f"❌ Error with query '{query}': {e}")
            responses.append(f"ERROR: {e}")
    
    # Compare responses for consistency (basic check)
    if len(responses) == 2:
        # Check if both responses mention similar document names/content
        # This is a simple heuristic - both should find policy-related documents
        wellness_keywords = ["wellness", "policy", "health", "safety"]
        
        found_keywords_1 = sum(1 for keyword in wellness_keywords if keyword.lower() in responses[0].lower())
        found_keywords_2 = sum(1 for keyword in wellness_keywords if keyword.lower() in responses[1].lower())
        
        if found_keywords_1 > 0 and found_keywords_2 > 0:
            print("✅ Both queries returned wellness-related content - consistency improved!")
            return True
        else:
            print("⚠️  Responses may differ significantly in wellness-related content")
            return False
    
    return False

async def main():
    """Run all tests"""
    print("🚀 Running link hallucination and semantic search tests...\n")
    
    # Test 1: Link hallucination fix
    link_test_passed = await test_link_hallucination_fix()
    
    # Test 2: Semantic search consistency
    consistency_test_passed = await test_semantic_search_consistency()
    
    print(f"\n📊 Test Results:")
    print(f"Link Hallucination Fix: {'✅ PASSED' if link_test_passed else '❌ FAILED'}")
    print(f"Search Consistency: {'✅ PASSED' if consistency_test_passed else '❌ FAILED'}")
    
    if link_test_passed and consistency_test_passed:
        print("\n🎉 All tests passed! The fixes appear to be working correctly.")
        return 0
    else:
        print("\n⚠️  Some tests failed or showed warnings. Check the output above.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
