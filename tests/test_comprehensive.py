#!/usr/bin/env python3

"""
Comprehensive functional test for DTCE AI Bot using ALL questions from QUESTIONS.TXT
Tests the deployed API to ensure real functionality with engineering questions.
"""

import asyncio
import aiohttp
import time
import json

# API Configuration
API_BASE_URL = "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net"

def load_all_questions_from_file():
    """Load ALL questions from QUESTIONS.TXT file."""
    questions_file = "/Users/cossettealexisgabuya/Documents/Projects/dtce-ai-bot/QUESTIONS.TXT"
    
    try:
        with open(questions_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract all questions - look for lines that start with quotes
        questions = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            # Look for lines that start with quotes and contain question-like content
            if line.startswith('"') and line.endswith('"') and len(line) > 10:
                # Remove the surrounding quotes
                question = line[1:-1]
                questions.append(question)
        
        # Also add some basic test questions for help functionality
        basic_questions = [
            "help",
            "How do I use this system?",
            "What can you help me with?"
        ]
        
        all_questions = basic_questions + questions
        print(f"📋 Loaded {len(all_questions)} questions ({len(questions)} from QUESTIONS.TXT + {len(basic_questions)} basic)")
        return all_questions
        
    except FileNotFoundError:
        print("❌ QUESTIONS.TXT file not found!")
        return [
            "help",
            "What projects do we have?",
            "Show me structural calculations", 
            "Find bridge drawings"
        ]

async def test_api_health():
    """Test if the API is running."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE_URL}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ API Health: {data}")
                    return True
                else:
                    print(f"❌ API Health failed: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ API Health check failed: {e}")
        return False

async def test_question_api(question):
    """Test a question via the API."""
    try:
        async with aiohttp.ClientSession() as session:
            # Use query parameters as expected by FastAPI endpoint
            url = f"{API_BASE_URL}/documents/ask"
            params = {"question": question}
            
            start_time = time.time()
            async with session.post(url, params=params) as response:
                end_time = time.time()
                duration = end_time - start_time
                
                if response.status == 200:
                    data = await response.json()
                    answer = data.get('answer', 'No answer')
                    sources = data.get('sources', [])
                    confidence = data.get('confidence', 'unknown')
                    
                    print(f"✅ SUCCESS ({duration:.2f}s)")
                    print(f"   Answer: {answer[:150]}{'...' if len(answer) > 150 else ''}")
                    print(f"   Sources: {len(sources)} found")
                    print(f"   Confidence: {confidence}")
                    
                    # Check if it's a real answer or error message
                    error_indicators = [
                        "I encountered an error",
                        "Please try again",
                        "error processing",
                        "something went wrong",
                        "no specific question provided",
                        "clarify or provide the question"
                    ]
                    
                    has_error = any(indicator.lower() in answer.lower() for indicator in error_indicators)
                    
                    # Special check for help questions - they should provide actual help
                    is_help_question = question.lower() in ['help', 'how do i use this system?', 'what can you help me with?']
                    if is_help_question and has_error:
                        print(f"   ⚠️  Help question not answered properly")
                    
                    return {
                        'status': 'ERROR' if has_error else 'SUCCESS',
                        'question': question,
                        'answer': answer,
                        'sources': len(sources),
                        'confidence': confidence,
                        'duration': duration,
                        'has_error': has_error,
                        'is_help_question': is_help_question
                    }
                else:
                    print(f"❌ API Error: {response.status}")
                    text = await response.text()
                    return {
                        'status': 'API_ERROR',
                        'question': question,
                        'error': f"HTTP {response.status}: {text}",
                        'duration': duration
                    }
                    
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return {
            'status': 'EXCEPTION',
            'question': question,
            'error': str(e),
            'duration': 0
        }

async def main():
    """Main test function."""
    print("🚀 DTCE AI Bot - COMPREHENSIVE Functional Testing")
    print("=" * 80)
    print(f"Testing deployed API: {API_BASE_URL}")
    print("Testing ALL questions from QUESTIONS.TXT + help functionality")
    print("=" * 80)
    
    print("\n📡 Testing API Health...")
    health_ok = await test_api_health()
    
    if not health_ok:
        print("❌ API is not healthy. Aborting tests.")
        return
        
    print("\n🧠 Testing Question Answering...")
    print("=" * 60)
    
    # Get all questions from QUESTIONS.TXT
    test_questions = load_all_questions_from_file()
    
    results = []
    successful = 0
    error_responses = 0
    help_issues = 0
    
    for i, question in enumerate(test_questions, 1):
        print(f"\nTest {i}/{len(test_questions)}: '{question}'")
        print("-" * 50)
        
        result = await test_question_api(question)
        results.append(result)
        
        if result['status'] == 'SUCCESS':
            if result.get('has_error', False):
                error_responses += 1
                if result.get('is_help_question', False):
                    help_issues += 1
            else:
                successful += 1
        
        # Add small delay to avoid overwhelming the API
        await asyncio.sleep(0.5)
    
    # Print summary
    print("\n" + "=" * 80)
    print("🏁 COMPREHENSIVE FUNCTIONAL TEST RESULTS")
    print("=" * 80)
    print(f"Total tests: {len(test_questions)}")
    print(f"✅ Successful answers: {successful}")
    print(f"⚠️  Error responses: {error_responses}")
    print(f"🆘 Help questions with issues: {help_issues}")
    print(f"❌ API failures: {len(test_questions) - successful - error_responses}")
    print(f"Success rate: {(successful/len(test_questions)*100):.1f}%")
    
    # Performance stats
    successful_results = [r for r in results if r['status'] == 'SUCCESS']
    if successful_results:
        avg_time = sum(r.get('duration', 0) for r in successful_results) / len(successful_results)
        avg_sources = sum(r.get('sources', 0) for r in successful_results) / len(successful_results)
        print(f"\n📊 Performance:")
        print(f"  Average response time: {avg_time:.2f}s")
        print(f"  Average sources found: {avg_sources:.1f}")
    
    # Show issues
    issues = [r for r in results if r['status'] != 'SUCCESS' or r.get('has_error', False)]
    if issues:
        print(f"\n❌ Issues found:")
        for issue in issues[:15]:  # Show first 15 issues
            question = issue['question']
            if len(question) > 40:
                question = question[:40] + "..."
            if issue['status'] == 'SUCCESS' and issue.get('has_error'):
                issue_type = "Help issue" if issue.get('is_help_question') else "Error response"
                print(f"  - {question} → {issue_type}")
            else:
                error_msg = issue.get('error', 'Unknown error')
                if len(error_msg) > 100:
                    error_msg = error_msg[:100] + "..."
                print(f"  - {question} → {error_msg}")
    
    print("=" * 80)
    if successful == len(test_questions):
        print("🎉 All tests passed! System is fully functional!")
    elif successful > len(test_questions) * 0.8:
        print("🎉 System is mostly working but has some issues to address!")
    else:
        print("⚠️  System has significant issues that need to be fixed.")
    
    if help_issues > 0:
        print(f"⚠️  Help functionality needs improvement ({help_issues} help questions failed)")

if __name__ == "__main__":
    asyncio.run(main())
