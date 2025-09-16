#!/usr/bin/env python3
"""
Comprehensive test for all types of DTCE AI bot queries.
Tests intent classification and response routing for different query categories.
"""

import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.services.rag_handler import RAGHandler
from dtce_ai_bot.config.settings import get_settings
from openai import AsyncOpenAI

async def test_comprehensive_queries():
    """Test all different types of queries the DTCE AI bot should handle."""
    
    settings = get_settings()
    
    # Initialize OpenAI client
    openai_client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        timeout=60.0
    )
    
    rag_handler = RAGHandler(settings, openai_client, "gpt-4")
    
    # Test categories with example queries
    test_queries = {
        "Policy Questions": [
            "What is our wellness policy?",
            "What's our wellness policy and what does it say?",
            "wellness policy",
            "wellbeing policy"
        ],
        
        "Contact/Client Info": [
            "Does anyone work with Aaron from TGCS?",
            "Who is the contact for project 224?",
            "Can you find any companies and contact details that constructed a design for us in the past 3 years?",
            "Find builders that we've worked with before for steel structure retrofit"
        ],
        
        "Project Search": [
            "What is project 225",
            "WHAT IS project 221 INCLUDE SUPERSEDED FOLDERS?",
            "Show me project 220 details"
        ],
        
        "Problem Projects": [
            "Can you give me sample projects where clients don't like",
            "Show me all emails or meeting notes for project 219 where the client raised concerns",
            "Were there any client complaints or rework requests for project 222?"
        ],
        
        "Technical Engineering": [
            "What were the main design considerations mentioned in the final report for project 224?",
            "What stormwater management approach was used in project 223?",
            "Tell me minimum clear cover requirements as per NZS code",
            "I am designing a precast panel, please tell me all past projects about precast"
        ],
        
        "Templates & Resources": [
            "Please provide me with the template we generally use for preparing a PS1",
            "Show me timber beam design spreadsheet that DTCE usually uses",
            "What calculation templates do we have for multi-storey timber buildings?"
        ],
        
        "Advisory Questions": [
            "Should I reuse the stormwater report from project 225 for our next job?",
            "What should I be aware of when using these older calculation methods?",
            "Summarize mistakes made during internal review stages across past projects"
        ]
    }
    
    print("🧪 COMPREHENSIVE DTCE AI BOT QUERY TEST")
    print("=" * 60)
    
    total_tests = 0
    passed_tests = 0
    
    for category, queries in test_queries.items():
        print(f"\n📋 TESTING: {category}")
        print("-" * 40)
        
        for query in queries:
            total_tests += 1
            print(f"\n🔍 Query: {query}")
            
            try:
                # Test intent classification first
                intent_classification = await rag_handler._classify_user_intent(query)
                classified_category = intent_classification.get('category', 'unknown')
                confidence = intent_classification.get('confidence', 0)
                
                print(f"   Intent: {classified_category} (confidence: {confidence:.2f})")
                
                # Test full response generation
                result = await rag_handler.process_query(query, [])
                answer = result.get('answer', 'No answer generated')
                
                # Check if response is appropriate
                is_good_response = True
                response_issues = []
                
                # Check for bad patterns
                bad_patterns = [
                    "project details, scope, outcomes, design approaches",
                    "comprehensive project insights they can apply",
                    "Give them comprehensive project insights",
                    "extract and explain the actual project information"
                ]
                
                answer_lower = answer.lower()
                for pattern in bad_patterns:
                    if pattern.lower() in answer_lower:
                        is_good_response = False
                        response_issues.append(f"Contains bad pattern: '{pattern}'")
                
                # Check for appropriate responses based on query type
                if "contact" in query.lower() or "aaron" in query.lower():
                    if "couldn't find contact information" in answer:
                        print("   ✅ Appropriate 'contact not found' response")
                    elif any(bad in answer_lower for bad in ["design approaches", "project scope", "technical specifications"]):
                        is_good_response = False
                        response_issues.append("Contact query got technical project response")
                    else:
                        print("   ✅ Contact-appropriate response")
                
                elif "wellness" in query.lower() or "wellbeing" in query.lower():
                    if classified_category == "policy":
                        print("   ✅ Correctly classified as policy")
                    else:
                        response_issues.append(f"Policy query classified as {classified_category}")
                
                elif "project" in query.lower() and any(num in query for num in ["220", "221", "224", "225"]):
                    if classified_category in ["project_search", "project_reference"]:
                        print("   ✅ Correctly classified as project query")
                    else:
                        response_issues.append(f"Project query classified as {classified_category}")
                
                # Show response quality
                if is_good_response and not response_issues:
                    print("   ✅ PASS - Good response")
                    passed_tests += 1
                else:
                    print("   ❌ FAIL - Response issues:")
                    for issue in response_issues:
                        print(f"      - {issue}")
                    print(f"   Response preview: {answer[:200]}...")
                
            except Exception as e:
                print(f"   ❌ ERROR: {str(e)}")
                
    print(f"\n" + "=" * 60)
    print(f"🏁 TEST SUMMARY")
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("🚨 SOME TESTS FAILED - Review issues above")

if __name__ == "__main__":
    asyncio.run(test_comprehensive_queries())
