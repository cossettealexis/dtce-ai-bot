#!/usr/bin/env python3
"""
Comprehensive test script for DTCE AI Bot
Tests all RAG patterns, edge cases, and functionality
"""

import asyncio
import httpx
import json
import time
from typing import List, Dict

# Test configuration
BASE_URL = "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net"
TEST_RESULTS_FILE = "test_results.json"

# Comprehensive test questions covering all RAG patterns
TEST_QUESTIONS = [
    # === NZ STANDARDS TESTS ===
    {
        "category": "NZ Standards",
        "questions": [
            "What are the NZ3604 requirements for wind loading?",
            "Show me NZS 1170.2 earthquake design standards",
            "What does AS/NZS say about concrete strength requirements?",
            "NZ building code requirements for timber construction",
            "What are the AS 3600 concrete design standards?",
        ]
    },
    
    # === PAST PROJECTS TESTS ===
    {
        "category": "Past Projects",
        "questions": [
            "Show me examples of retail building projects we've done",
            "What commercial buildings has DTCE designed?",
            "Examples of residential developments in Auckland",
            "Show me industrial warehouse projects",
            "What schools or educational buildings have we designed?",
            "Examples of mixed-use developments",
            "Show me heritage building strengthening projects",
        ]
    },
    
    # === PRODUCT SPECIFICATIONS TESTS ===
    {
        "category": "Product Specifications",
        "questions": [
            "What are the specifications for LVL beams?",
            "Show me Glulam beam product details",
            "What steel beam sizes are available?",
            "Concrete admixture specifications",
            "What timber treatment options do we have?",
            "Show me reinforcing steel bar specifications",
            "What precast concrete products are available?",
        ]
    },
    
    # === SCENARIO TECHNICAL TESTS ===
    {
        "category": "Scenario Technical",
        "questions": [
            "Show me examples of mid-rise timber frame buildings in high wind zones that we've designed",
            "Examples of seismic retrofitting for unreinforced masonry buildings",
            "How do you design foundations on soft soil conditions?",
            "Examples of long-span roof structures with timber beams",
            "Show me projects dealing with coastal exposure and salt corrosion",
            "Examples of buildings designed for alpine snow loads",
            "How to handle differential settlement in multi-story buildings",
        ]
    },
    
    # === LESSONS LEARNED TESTS ===
    {
        "category": "Lessons Learned",
        "questions": [
            "What lessons have we learned about timber moisture issues?",
            "Problems encountered with precast concrete connections",
            "Issues with steel beam deflection in long spans",
            "Lessons learned from foundation failures",
            "What went wrong with waterproofing in basement projects?",
            "Problems with thermal bridging in insulated panels",
            "Lessons from seismic retrofit challenges",
        ]
    },
    
    # === REGULATORY PRECEDENT TESTS ===
    {
        "category": "Regulatory Precedent",
        "questions": [
            "Council issues with building consent for timber high-rise",
            "How have we dealt with Auckland Council alternative solutions?",
            "Precedents for fire rating exemptions",
            "Council requirements for seismic strengthening approvals",
            "Examples of successful code compliance certificates",
            "How to handle building warrant of fitness issues",
            "Precedents for structural peer review requirements",
        ]
    },
    
    # === COST TIME INSIGHTS TESTS ===
    {
        "category": "Cost Time Insights",
        "questions": [
            "How long does structural design take for a 5-story building?",
            "What are typical costs for seismic assessment?",
            "Timeline for building consent documentation",
            "Cost comparison between steel and timber framing",
            "How long does foundation design take for commercial buildings?",
            "Typical fees for structural peer review",
            "Time required for detailed seismic evaluation",
        ]
    },
    
    # === BEST PRACTICES TESTS ===
    {
        "category": "Best Practices",
        "questions": [
            "What are DTCE's best practices for timber design?",
            "Best practices for foundation design in soft soils",
            "How do we approach seismic design methodology?",
            "Best practices for steel connection details",
            "DTCE standards for concrete mix design",
            "Best practices for building performance assessment",
            "How we handle peer review processes",
        ]
    },
    
    # === MATERIALS METHODS TESTS ===
    {
        "category": "Materials Methods",
        "questions": [
            "When do we choose steel vs timber for framing?",
            "Comparison between precast and cast-in-place concrete",
            "When to use post-tensioned vs conventional reinforcement?",
            "Steel vs concrete for multi-story construction",
            "When to specify engineered timber vs traditional framing?",
            "Comparison of foundation types for different soil conditions",
            "When to use base isolation vs conventional seismic design?",
        ]
    },
    
    # === INTERNAL KNOWLEDGE TESTS ===
    {
        "category": "Internal Knowledge",
        "questions": [
            "Who are our experts in timber engineering?",
            "Which engineers specialize in seismic design?",
            "Who handles heritage building assessments?",
            "What's our team's experience with high-rise design?",
            "Who are our concrete design specialists?",
            "Which engineers work on industrial projects?",
            "Who handles building code compliance issues?",
        ]
    },
    
    # === TEMPLATES FORMS TESTS ===
    {
        "category": "Templates Forms",
        "questions": [
            "Show me the structural calculation template",
            "What forms do we use for seismic assessments?",
            "Template for building consent applications",
            "Show me the project report template",
            "What checklists do we have for peer reviews?",
            "Template for structural drawings",
            "Forms for client project briefings",
        ]
    },
    
    # === EDGE CASES AND SPECIAL TESTS ===
    {
        "category": "Edge Cases",
        "questions": [
            "What about underwater foundations?",  # Should trigger external reference
            "How do space structures work?",  # Should trigger external reference
            "Tell me about nuclear power plant design",  # Should trigger external reference
            "What's the weather like today?",  # Should trigger intelligent fallback
            "How do I cook pasta?",  # Should trigger intelligent fallback
            "What are the latest AI developments?",  # Should trigger external reference
            "",  # Empty question
            "project 219",  # Specific project query
            "show me job 220271",  # Specific job query
            "what files are in engineering folder?",  # Folder query
        ]
    },
    
    # === CONVERSATIONAL TESTS ===
    {
        "category": "Conversational",
        "questions": [
            "Hi, can you help me with structural design?",
            "Thanks for that information, what about seismic design?",
            "Can you show me more examples?",
            "That's helpful, do you have any cost information?",
            "What would you recommend for this project?",
            "How confident are you in this answer?",
            "Can you provide more details on that?",
        ]
    },
    
    # === LINK AND URL TESTS ===
    {
        "category": "Link Tests",
        "questions": [
            "Show me the wind load calculation document and provide the link",
            "I need the LVL beam specification sheet with a direct link",
            "Can you show me project 219380 documents with links?",
            "Show me timber design examples and provide document links",
            "I need seismic design guidelines with downloadable links",
        ]
    }
]

async def test_question(client: httpx.AsyncClient, question: str, category: str) -> Dict:
    """Test a single question and return results"""
    print(f"\n🔍 Testing [{category}]: {question[:80]}...")
    
    start_time = time.time()
    
    try:
        response = await client.post(
            f"{BASE_URL}/api/qa",
            json={
                "question": question,
                "conversation_history": []
            },
            timeout=60.0  # 60 second timeout
        )
        
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            answer = result.get('answer', '')
            confidence = result.get('confidence', 'unknown')
            rag_type = result.get('rag_type', 'unknown')
            sources_count = len(result.get('sources', []))
            
            # Check for common issues
            has_links = '[' in answer and '](' in answer
            has_static_patterns = any(pattern in answer for pattern in [
                "Here are examples from DTCE projects matching your scenario",
                "Here are lessons learned from DTCE projects",
                "Here are regulatory precedents",
                "Here are cost and time insights",
                "Here are DTCE's best practices",
                "Here are materials and methods",
                "Here's DTCE's internal expertise"
            ])
            
            print(f"  ✅ Success: {response_time:.2f}s | {confidence} | {rag_type} | {sources_count} sources")
            if has_links:
                print(f"  🔗 Contains links")
            if has_static_patterns:
                print(f"  ⚠️ WARNING: Contains static patterns!")
            
            return {
                "question": question,
                "category": category,
                "status": "success",
                "response_time": response_time,
                "answer": answer[:500] + "..." if len(answer) > 500 else answer,
                "confidence": confidence,
                "rag_type": rag_type,
                "sources_count": sources_count,
                "has_links": has_links,
                "has_static_patterns": has_static_patterns,
                "answer_length": len(answer)
            }
        else:
            print(f"  ❌ HTTP Error: {response.status_code}")
            return {
                "question": question,
                "category": category,
                "status": "http_error",
                "status_code": response.status_code,
                "response_time": response_time
            }
            
    except Exception as e:
        response_time = time.time() - start_time
        print(f"  💥 Exception: {str(e)}")
        return {
            "question": question,
            "category": category,
            "status": "exception",
            "error": str(e),
            "response_time": response_time
        }

async def run_comprehensive_tests():
    """Run all comprehensive tests"""
    print("🚀 Starting Comprehensive DTCE AI Bot Tests")
    print("=" * 60)
    
    all_results = []
    total_questions = sum(len(cat["questions"]) for cat in TEST_QUESTIONS)
    current_question = 0
    
    async with httpx.AsyncClient() as client:
        for test_category in TEST_QUESTIONS:
            category = test_category["category"]
            questions = test_category["questions"]
            
            print(f"\n📋 Testing Category: {category}")
            print("-" * 40)
            
            for question in questions:
                current_question += 1
                progress = (current_question / total_questions) * 100
                
                print(f"Progress: {progress:.1f}% ({current_question}/{total_questions})")
                
                result = await test_question(client, question, category)
                all_results.append(result)
                
                # Small delay to avoid overwhelming the server
                await asyncio.sleep(0.5)
    
    # Generate summary report
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY REPORT")
    print("=" * 60)
    
    # Overall statistics
    total_tests = len(all_results)
    successful_tests = len([r for r in all_results if r["status"] == "success"])
    failed_tests = total_tests - successful_tests
    
    print(f"Total Tests: {total_tests}")
    print(f"Successful: {successful_tests} ({successful_tests/total_tests*100:.1f}%)")
    print(f"Failed: {failed_tests} ({failed_tests/total_tests*100:.1f}%)")
    
    # Response time statistics
    successful_results = [r for r in all_results if r["status"] == "success"]
    if successful_results:
        response_times = [r["response_time"] for r in successful_results]
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        min_response_time = min(response_times)
        
        print(f"\nResponse Times:")
        print(f"  Average: {avg_response_time:.2f}s")
        print(f"  Min: {min_response_time:.2f}s")
        print(f"  Max: {max_response_time:.2f}s")
    
    # RAG type distribution
    rag_types = {}
    for result in successful_results:
        rag_type = result.get("rag_type", "unknown")
        rag_types[rag_type] = rag_types.get(rag_type, 0) + 1
    
    print(f"\nRAG Pattern Distribution:")
    for rag_type, count in sorted(rag_types.items()):
        print(f"  {rag_type}: {count}")
    
    # Check for issues
    static_pattern_issues = [r for r in successful_results if r.get("has_static_patterns", False)]
    if static_pattern_issues:
        print(f"\n⚠️ WARNING: {len(static_pattern_issues)} responses contain static patterns!")
        for issue in static_pattern_issues[:5]:  # Show first 5
            print(f"  - [{issue['category']}] {issue['question'][:60]}...")
    
    # Link analysis
    responses_with_links = [r for r in successful_results if r.get("has_links", False)]
    print(f"\n🔗 Responses with links: {len(responses_with_links)} ({len(responses_with_links)/len(successful_results)*100:.1f}%)")
    
    # Category performance
    print(f"\nCategory Performance:")
    for test_category in TEST_QUESTIONS:
        category = test_category["category"]
        category_results = [r for r in all_results if r["category"] == category]
        category_success = [r for r in category_results if r["status"] == "success"]
        success_rate = len(category_success) / len(category_results) * 100 if category_results else 0
        
        print(f"  {category}: {len(category_success)}/{len(category_results)} ({success_rate:.1f}%)")
    
    # Save detailed results
    with open(TEST_RESULTS_FILE, 'w') as f:
        json.dump({
            "summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "failed_tests": failed_tests,
                "success_rate": successful_tests/total_tests*100,
                "avg_response_time": avg_response_time if successful_results else 0,
                "rag_type_distribution": rag_types,
                "static_pattern_issues": len(static_pattern_issues),
                "responses_with_links": len(responses_with_links)
            },
            "detailed_results": all_results
        }, f, indent=2)
    
    print(f"\n💾 Detailed results saved to: {TEST_RESULTS_FILE}")
    print("\n🏁 Comprehensive testing completed!")

if __name__ == "__main__":
    asyncio.run(run_comprehensive_tests())
