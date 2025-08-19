#!/usr/bin/env python3
"""
Test script to analyze why PS1 timing questions are not being routed properly.
"""

import asyncio
import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.services.document_qa import DocumentQAService
from dtce_ai_bot.integrations.azure_search import get_search_client

async def test_ps1_routing():
    """Test that PS1 timing questions route to cost/time insights correctly."""
    
    # Your specific query
    query = "How long does PS1 preparation typically take?"
    
    print("🎯 Testing PS1 Timing Query Routing")
    print("=" * 60)
    print(f"Query: {query}")
    print("=" * 60)
    
    try:
        # Initialize the search client and QA service
        search_client = get_search_client()
        qa_service = DocumentQAService(search_client)
        
        # Step 1: Test AI classification
        print(f"🧠 AI Classification Test:")
        classification = await qa_service.classification_service.classify_query_intent(query)
        
        print(f"   Primary Intent: {classification.get('primary_intent')}")
        print(f"   Confidence: {classification.get('confidence', 0):.2f}")
        print(f"   Reasoning: {classification.get('reasoning', 'No reasoning provided')}")
        print(f"   Keywords: {classification.get('keywords', [])}")
        
        # Check if it's correctly identifying as COST_TIME_INSIGHTS
        expected_intent = "COST_TIME_INSIGHTS"
        actual_intent = classification.get('primary_intent')
        
        if actual_intent == expected_intent:
            print(f"   ✅ CORRECT: Classified as {expected_intent}")
        else:
            print(f"   ❌ WRONG: Expected {expected_intent}, got {actual_intent}")
        
        # Step 2: Test smart routing
        print(f"\n🎯 Smart Routing Test:")
        handler, routing_details = await qa_service.smart_router.route_query(query)
        print(f"   Handler: {handler}")
        print(f"   Details: {routing_details.get('primary_intent')}")
        
        if handler == "cost_time_insights":
            print(f"   ✅ CORRECT: Routed to cost_time_insights handler")
        else:
            print(f"   ❌ WRONG: Expected cost_time_insights, got {handler}")
        
        # Step 3: Test the actual response
        print(f"\n🤖 Testing Full Response:")
        result = await qa_service.answer_question(query)
        
        print(f"   Answer preview: {result['answer'][:200]}...")
        print(f"   Confidence: {result['confidence']}")
        print(f"   Documents searched: {result['documents_searched']}")
        print(f"   Search type: {result.get('search_type', 'not specified')}")
        
        # Check response quality
        answer_lower = result['answer'].lower()
        
        # Good indicators for PS1 timing response
        good_indicators = [
            'ps1', 'preparation', 'typically', 'duration', 'time', 'weeks', 'months', 
            'phase', 'design', 'timeline', 'project'
        ]
        
        # Bad indicators (template dump responses)
        bad_indicators = [
            'project (', 'documents (', 'file type:', 'here are the', 'available projects'
        ]
        
        good_count = sum(1 for indicator in good_indicators if indicator in answer_lower)
        bad_count = sum(1 for indicator in bad_indicators if indicator in answer_lower)
        
        print(f"   Good indicators found: {good_count}")
        print(f"   Bad indicators found: {bad_count}")
        
        if bad_count > 0:
            print(f"   ❌ PROBLEM: Response looks like template dump, not PS1 timing info")
        elif good_count >= 3:
            print(f"   ✅ SUCCESS: Response appears to address PS1 timing")
        else:
            print(f"   ⚠️  UNCLEAR: Response quality uncertain")
        
        # Step 4: Test cost/time handler directly
        print(f"\n🔧 Testing Cost/Time Handler Directly:")
        try:
            direct_result = await qa_service._handle_cost_time_insights_query(query)
            print(f"   Direct handler answer: {direct_result['answer'][:150]}...")
            print(f"   Direct handler confidence: {direct_result['confidence']}")
            print(f"   Cost/time components: {direct_result.get('cost_time_components', {}).get('summary', 'None')}")
            
            if "ps1" in direct_result['answer'].lower():
                print(f"   ✅ Direct handler understands PS1 context")
            else:
                print(f"   ❌ Direct handler doesn't mention PS1")
                
        except Exception as e:
            print(f"   ❌ Direct handler error: {e}")
        
        print(f"\n🎉 SUMMARY:")
        print(f"   Classification: {'✅' if actual_intent == expected_intent else '❌'}")
        print(f"   Routing: {'✅' if handler == 'cost_time_insights' else '❌'}")
        print(f"   Response Quality: {'✅' if bad_count == 0 and good_count >= 3 else '❌'}")
        
    except Exception as e:
        print(f"❌ Failed to test PS1 routing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_ps1_routing())
