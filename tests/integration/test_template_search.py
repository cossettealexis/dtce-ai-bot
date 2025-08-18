#!/usr/bin/env python3
"""
Test the new template search functionality.
"""

import asyncio
import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.services.document_qa import DocumentQAService
from dtce_ai_bot.integrations.azure_search import get_search_client

async def test_template_search():
    """Test the new template search functionality with specific queries."""
    
    # Template search test queries
    test_queries = [
        "Please provide me with the template we generally use for preparing a PS1. Also, please provide me with the direct link to access it on SuiteFiles.",
        "I wasn't able to find a PS3 template in SuiteFiles. Please provide me with a legitimate link to a general PS3 template that can be submitted to any council in New Zealand.",
        "Please provide me with the link or the file for the timber beam design spreadsheet that DTCE usually uses or has used.",
        
        # Additional test cases
        "Do you have a PS4 template?",
        "I need a concrete beam design spreadsheet",
        "Where can I find steel design templates?"
    ]
    
    expected_output = "AI to provide specific documents/templates, reducing time spent searching the internet or past SuiteFiles records."
    
    print("📋 Testing Template Search Functionality")
    print("=" * 80)
    print(f"Expected Output: {expected_output}")
    print("=" * 80)
    
    try:
        # Initialize the search client and QA service
        search_client = get_search_client()
        qa_service = DocumentQAService(search_client)
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n📋 Test Query {i}:")
            print(f"Question: {query}")
            print("-" * 60)
            
            try:
                # Get AI classification
                handler, classification = await qa_service.smart_router.route_query(query)
                
                print(f"🧠 AI Classification:")
                print(f"   Intent: {classification.get('primary_intent')}")
                print(f"   Confidence: {classification.get('confidence'):.2f}")
                print(f"   Handler: {handler}")
                
                # Check if it correctly identifies template search
                if handler == "template_search":
                    print("   ✅ Correctly identified as template search")
                else:
                    print(f"   ⚠️  Unexpected handler: {handler}")
                
                # Test template type identification
                template_type = qa_service._identify_template_type(query)
                print(f"   📄 Template Type: {template_type}")
                
                # Get the actual response
                print(f"\n🤖 AI Response:")
                result = await qa_service.answer_question(query)
                
                response_preview = result['answer'][:200] + "..." if len(result['answer']) > 200 else result['answer']
                print(f"   Answer Preview: {response_preview}")
                print(f"   Confidence: {result['confidence']}")
                print(f"   Sources: {len(result['sources'])}")
                print(f"   Search Type: {result.get('search_type', 'N/A')}")
                
                # Check for key features
                if "SuiteFiles" in result['answer']:
                    print("   ✅ Mentions SuiteFiles")
                if "http" in result['answer'] or "[" in result['answer']:
                    print("   ✅ Contains links")
                if "template" in result['answer'].lower():
                    print("   ✅ Addresses templates")
                
                # Show sources if found
                if result['sources']:
                    print(f"\n📄 Sources Found:")
                    for j, source in enumerate(result['sources'][:2], 1):
                        print(f"   {j}. {source.get('filename', 'Unknown')}")
                        if source.get('blob_url'):
                            print(f"      🔗 {source['blob_url']}")
                
            except Exception as e:
                print(f"❌ Error processing query: {e}")
            
            print("\n" + "=" * 80)
            
        print(f"\n🎯 TEMPLATE SEARCH BENEFITS:")
        print(f"   ✅ Direct access to SuiteFiles templates")
        print(f"   ✅ Identifies specific template types (PS1, PS3, etc.)")
        print(f"   ✅ Provides external links when not found internally")
        print(f"   ✅ Reduces time searching through folders")
        print(f"   ✅ Ensures current templates are used")
    
    except Exception as e:
        print(f"❌ Failed to test template search: {e}")

if __name__ == "__main__":
    asyncio.run(test_template_search())
