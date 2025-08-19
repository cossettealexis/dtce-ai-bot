#!/usr/bin/env python3
"""
Test script to verify that the AI now provides intelligent responses for ALL question types,
not just specific classifications. This tests the fundamental fix to prevent template dumps.
"""

import asyncio
import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.services.document_qa import DocumentQAService
from dtce_ai_bot.integrations.azure_search import get_search_client

async def test_all_intelligent_responses():
    """Test that ALL question types get intelligent responses, not template dumps."""
    
    # Test diverse question types that previously got template dumps
    test_queries = [
        # Cost/Time questions
        "How long does PS1 preparation typically take?",
        "What's the typical cost for structural design of small projects?",
        
        # Technical questions  
        "What NZ code should I use for composite slabs as floor diaphragms?",
        "How do I design a retaining wall for seismic loads?",
        
        # Process questions
        "What's the workflow for building consent applications?",
        "How do I submit timesheet entries in WorkflowMax?",
        
        # Example-seeking questions
        "Show me examples of timber construction projects we've done",
        "Find past projects similar to multi-unit residential",
        
        # General professional questions
        "What are best practices for client communication?",
        "How should I approach foundation design for clay soils?"
    ]
    
    print("🧠 Testing Intelligent AI Responses for ALL Question Types")
    print("=" * 80)
    print("This verifies the AI understands intent and provides helpful answers,")
    print("NOT template dumps or document lists.")
    print("=" * 80)
    
    try:
        # Initialize the search client and QA service
        search_client = get_search_client()
        qa_service = DocumentQAService(search_client)
        
        passed_tests = 0
        total_tests = len(test_queries)
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n📋 Test {i}/{total_tests}:")
            print(f"Question: {query}")
            print("-" * 60)
            
            try:
                # Test the full response
                result = await qa_service.answer_question(query)
                
                answer = result['answer']
                search_type = result.get('search_type', 'unknown')
                
                print(f"🎯 Search Type: {search_type}")
                print(f"📊 Confidence: {result['confidence']}")
                print(f"📚 Documents: {result['documents_searched']}")
                
                # Check for intelligence vs template dumps
                answer_lower = answer.lower()
                
                # Bad indicators (template dump responses)
                bad_indicators = [
                    'project (', 'documents (', 'file type:', 'here are the', 
                    'available projects', 'found the following', 'document list',
                    'files found:', 'available documents'
                ]
                
                # Good indicators (intelligent responses)
                good_indicators = [
                    'typically', 'recommend', 'consider', 'approach', 'best practice',
                    'guideline', 'step', 'process', 'should', 'ensure', 'important',
                    'design', 'analysis', 'calculation', 'standard', 'requirement'
                ]
                
                bad_count = sum(1 for indicator in bad_indicators if indicator in answer_lower)
                good_count = sum(1 for indicator in good_indicators if indicator in answer_lower)
                
                # Quality assessment
                if bad_count > 0:
                    print(f"   ❌ TEMPLATE DUMP: Contains {bad_count} template indicators")
                    quality = "FAIL"
                elif good_count >= 2 and len(answer) > 100:
                    print(f"   ✅ INTELLIGENT: Contains {good_count} intelligence indicators")
                    quality = "PASS"
                    passed_tests += 1
                elif len(answer) < 50:
                    print(f"   ⚠️  TOO SHORT: Response too brief ({len(answer)} chars)")
                    quality = "PARTIAL"
                else:
                    print(f"   ⚠️  UNCLEAR: Some intelligence ({good_count} indicators)")
                    quality = "PARTIAL"
                    passed_tests += 0.5
                
                # Show response preview
                preview = answer[:200] + "..." if len(answer) > 200 else answer
                print(f"   💬 Response: {preview}")
                
                # Check if intent analysis was used
                if 'intent_analysis' in result:
                    intent = result['intent_analysis'].get('intent_category', 'unknown')
                    print(f"   🧠 Intent Detected: {intent}")
                
                print(f"   🎯 RESULT: {quality}")
                
            except Exception as e:
                print(f"❌ Error processing query: {e}")
                quality = "ERROR"
            
            print("\n" + "=" * 60)
        
        # Summary
        print(f"\n🎉 INTELLIGENCE TEST RESULTS:")
        print(f"   Passed: {int(passed_tests)}/{total_tests}")
        print(f"   Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if passed_tests >= total_tests * 0.8:  # 80% success rate
            print(f"   ✅ SUCCESS: AI is providing intelligent responses!")
            print(f"   🎯 Users should now get helpful answers instead of template dumps")
        elif passed_tests >= total_tests * 0.5:  # 50% success rate
            print(f"   ⚠️  PARTIAL: Some improvement but still needs work")
            print(f"   🔧 Need to refine intent detection and response generation")
        else:
            print(f"   ❌ FAILED: Still getting too many template dump responses")
            print(f"   🚨 Core routing or intent understanding issues remain")
        
        print(f"\n🎯 KEY BENEFITS IF WORKING:")
        print(f"   ✅ No more 'here are 50 projects' responses")
        print(f"   ✅ Direct answers to what users actually want") 
        print(f"   ✅ Professional guidance even without specific docs")
        print(f"   ✅ Intent-aware search and context preparation")
        print(f"   ✅ ChatGPT-level understanding of user questions")
    
    except Exception as e:
        print(f"❌ Failed to test intelligent responses: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_all_intelligent_responses())
