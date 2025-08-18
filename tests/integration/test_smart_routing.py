#!/usr/bin/env python3
"""
Test the new AI-powered smart routing system.
"""

import asyncio
import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.services.document_qa import DocumentQAService
from dtce_ai_bot.integrations.azure_search import get_search_client

async def test_smart_routing():
    """Test the new AI-powered smart routing with your specific queries."""
    
    # Your test queries
    test_queries = [
        # Web search queries
        "Look for online threads or references about structural design procedures or current design discussions accessible to the public (especially NZ references / forums)",
        "I am currently designing a composite beam but need to make it haunched/tapered. Please provide related references or online threads mentioning the keyword 'tapered composite beam', preferably from anonymous structural engineers.",
        "Please provide design guidelines for a reinforced concrete column to withstand both seismic and gravity actions. If possible, include a legitimate link that gives direct access to the specific design guidelines.",
        
        # Contractor/builder query
        "My client is asking about builders that we've worked with before. Can you find any companies and or contact details that constructed a design for us in the past 3 years and didn't seem to have too many issues during construction. the design job I'm dealing with now is a steel structure retrofit of an old brick building.",
        
        # Various other natural questions
        "What NZ code should I use for designing a composite slab?",
        "Show me past DTCE projects with timber construction",
        "How do I calculate beam deflection?",
        "What's the seismic design requirements?"
    ]
    
    print("🧠 Testing AI-Powered Smart Query Routing")
    print("=" * 80)
    print("This shows how AI understands intent and routes naturally phrased questions")
    print("=" * 80)
    
    try:
        # Initialize the search client and QA service
        search_client = get_search_client()
        qa_service = DocumentQAService(search_client)
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n📋 Query {i}:")
            print(f"Question: {query}")
            print("-" * 60)
            
            try:
                # Get AI classification
                handler, classification = await qa_service.smart_router.route_query(query)
                
                print(f"🧠 AI Intent Classification:")
                print(f"   Primary Intent: {classification.get('primary_intent')}")
                print(f"   Confidence: {classification.get('confidence'):.2f}")
                print(f"   Reasoning: {classification.get('reasoning')}")
                print(f"   Keywords: {classification.get('keywords')}")
                print(f"🎯 Routed to: {handler}")
                
                # Test the actual response (just get a preview)
                print(f"\n🤖 Testing Response...")
                result = await qa_service.answer_question(query)
                
                response_preview = result['answer'][:150] + "..." if len(result['answer']) > 150 else result['answer']
                print(f"   Response Preview: {response_preview}")
                print(f"   Confidence: {result['confidence']}")
                print(f"   Sources: {len(result['sources'])}")
                
                # Check if routing worked correctly
                if handler == "web_search" and "external" in result.get('search_type', ''):
                    print("   ✅ Correctly routed to web search")
                elif handler == "contractor_search" and ("contractor" in result['answer'].lower() or "builder" in result['answer'].lower()):
                    print("   ✅ Correctly routed to contractor search")
                elif handler == "nz_standards" and ("nzs" in result['answer'].lower() or "standard" in result['answer'].lower()):
                    print("   ✅ Correctly routed to NZ standards")
                elif handler == "project_search" and "Project" in result['answer']:
                    print("   ✅ Correctly routed to project search")
                else:
                    print(f"   ⚠️  Response type unclear for {handler}")
                
            except Exception as e:
                print(f"❌ Error processing query: {e}")
            
            print("\n" + "=" * 80)
            
        print(f"\n🎉 BENEFITS OF AI ROUTING:")
        print(f"   ✅ Users can ask questions naturally")
        print(f"   ✅ No need to remember specific keywords")
        print(f"   ✅ AI understands intent and context")
        print(f"   ✅ Handles complex, multi-part questions")
        print(f"   ✅ Adapts to different phrasing styles")
    
    except Exception as e:
        print(f"❌ Failed to test smart routing: {e}")

if __name__ == "__main__":
    asyncio.run(test_smart_routing())
