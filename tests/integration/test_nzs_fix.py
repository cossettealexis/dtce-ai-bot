#!/usr/bin/env python3
"""
Test the fix for NZ structural code query routing.
"""

import asyncio
import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.services.document_qa import DocumentQAService
from dtce_ai_bot.integrations.azure_search import get_search_client

async def test_nzs_fix():
    """Test that the NZ structural code query now routes correctly."""
    
    # The problematic query
    query = "tell me what particular nzs structural code to refer with if im designing a composite slab to make it as a floor diaphragm"
    
    print("🔧 Testing NZ Structural Code Query Fix")
    print("=" * 60)
    print(f"Query: {query}")
    print("=" * 60)
    
    try:
        # Initialize the search client and QA service
        search_client = get_search_client()
        qa_service = DocumentQAService(search_client)
        
        # Check routing logic AFTER the fix
        is_nz_standards_query = qa_service._is_nz_standards_query(query)
        is_keyword_query = qa_service._is_project_keyword_query(query)
        
        print(f"✅ Detected as NZ standards query: {is_nz_standards_query}")
        print(f"✅ Detected as keyword project query: {is_keyword_query}")
        print(f"🎯 Expected routing: NZ Standards (should be checked FIRST now)")
        
        # Test the actual response
        print(f"\n🤖 AI Response After Fix:")
        try:
            result = await qa_service.answer_question(query)
            
            print(f"Answer: {result['answer']}")
            print(f"Confidence: {result['confidence']}")
            print(f"Documents searched: {result['documents_searched']}")
            print(f"Sources found: {len(result['sources'])}")
            
            # Check if it's giving technical information vs project list
            if "Project" in result['answer'] and "documents (" in result['answer']:
                print("❌ STILL ROUTING TO PROJECT SEARCH!")
            elif "NZS" in result['answer'] or "standard" in result['answer'].lower():
                print("✅ SUCCESS! Now routing to NZ Standards handler")
            else:
                print("🤔 Different type of response...")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    except Exception as e:
        print(f"❌ Failed to test: {e}")

if __name__ == "__main__":
    asyncio.run(test_nzs_fix())
