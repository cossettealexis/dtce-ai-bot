#!/usr/bin/env python3
"""
Simple test of template identification and external link provision.
"""

import asyncio
import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.services.document_qa import DocumentQAService
from dtce_ai_bot.integrations.azure_search import get_search_client

async def test_template_functionality():
    """Test template identification and external links."""
    
    print("🧪 Simple Template Search Test")
    print("=" * 50)
    
    try:
        # Initialize the search client and QA service
        search_client = get_search_client()
        qa_service = DocumentQAService(search_client)
        
        # Test template type identification
        test_cases = [
            ("PS1 template please", "PS1"),
            ("I need a PS3 form", "PS3"),
            ("timber beam design spreadsheet", "TIMBER_BEAM_DESIGN"),
            ("concrete design calculator", "CONCRETE_DESIGN"),
            ("general template", "GENERAL_TEMPLATE")
        ]
        
        print("🔍 Template Type Identification:")
        for query, expected in test_cases:
            identified = qa_service._identify_template_type(query)
            status = "✅" if identified == expected else "❌"
            print(f"   {status} '{query}' → {identified} (expected: {expected})")
        
        # Test external links for PS3 (likely not in SuiteFiles)
        print(f"\n🌐 Testing External Links for PS3:")
        ps3_result = await qa_service._provide_external_template_links(
            "PS3 template", "PS3"
        )
        
        print(f"   Answer Preview: {ps3_result['answer'][:150]}...")
        print(f"   Confidence: {ps3_result['confidence']}")
        print(f"   Search Type: {ps3_result.get('search_type')}")
        
        # Test smart routing
        print(f"\n🧠 Testing Smart Routing:")
        query = "I need the PS1 template we use"
        handler, classification = await qa_service.smart_router.route_query(query)
        
        print(f"   Query: {query}")
        print(f"   Intent: {classification.get('primary_intent')}")
        print(f"   Handler: {handler}")
        print(f"   Confidence: {classification.get('confidence'):.2f}")
        
        if handler == "template_search":
            print("   ✅ Correctly routed to template search!")
        else:
            print(f"   ❌ Unexpected routing to {handler}")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_template_functionality())
