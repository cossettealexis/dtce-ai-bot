#!/usr/bin/env python3
"""
Real functional test that actually calls the deployed API to test if it answers questions.
This tests the actual deployed system, not just code structure.
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime

# Azure API endpoint
API_BASE_URL = "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net"

# Test questions from QUESTIONS.TXT - starting with basic ones
TEST_QUESTIONS = [
    # Basic functionality tests
    "hi",
    "hello", 
    "help",
    "really",
    
    # Simple engineering questions
    "What projects do we have?",
    "Show me structural calculations",
    "Find bridge drawings",
    
    # From QUESTIONS.TXT - easier ones first
    "Please tell me that minimum clear cover requirements as per NZS code in designing a concrete element",
    "What's our standard approach to designing steel portal frames for industrial buildings?",
    "I am designing a precast panel, please tell me all past project that has a scope about precast panels",
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
        print(f"❌ API Health error: {e}")
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
                        "something went wrong"
                    ]
                    
                    has_error = any(indicator.lower() in answer.lower() for indicator in error_indicators)
                    
                    return {
                        'status': 'ERROR' if has_error else 'SUCCESS',
                        'question': question,
                        'answer': answer,
                        'sources': len(sources),
                        'confidence': confidence,
                        'duration': duration,
                        'has_error': has_error
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

async def run_functional_tests():
    """Run functional tests on the deployed system."""
    print("🚀 DTCE AI Bot - Real Functional Testing")
    print("=" * 80)
    print(f"Testing deployed API: {API_BASE_URL}")
    print("=" * 80)
    
    # Test 1: API Health
    print("\n📡 Testing API Health...")
    health_ok = await test_api_health()
    
    if not health_ok:
        print("❌ API is not responding. Cannot run functional tests.")
        return False
    
    # Test 2: Question answering
    print("\n🧠 Testing Question Answering...")
    print("=" * 60)
    
    results = []
    successful = 0
    failed = 0
    errors = 0
    
    for i, question in enumerate(TEST_QUESTIONS, 1):
        print(f"\nTest {i}/{len(TEST_QUESTIONS)}: '{question}'")
        print("-" * 50)
        
        result = await test_question_api(question)
        results.append(result)
        
        if result['status'] == 'SUCCESS':
            successful += 1
        elif result['status'] == 'ERROR':
            errors += 1
        else:
            failed += 1
    
    # Summary
    print("\n" + "=" * 80)
    print("🏁 FUNCTIONAL TEST RESULTS")
    print("=" * 80)
    
    print(f"Total tests: {len(TEST_QUESTIONS)}")
    print(f"✅ Successful answers: {successful}")
    print(f"⚠️  Error responses: {errors}")
    print(f"❌ API failures: {failed}")
    print(f"Success rate: {(successful/len(TEST_QUESTIONS)*100):.1f}%")
    
    if successful > 0:
        successful_results = [r for r in results if r['status'] == 'SUCCESS']
        avg_duration = sum(r['duration'] for r in successful_results) / len(successful_results)
        avg_sources = sum(r['sources'] for r in successful_results) / len(successful_results)
        print(f"\n📊 Performance:")
        print(f"  Average response time: {avg_duration:.2f}s")
        print(f"  Average sources found: {avg_sources:.1f}")
    
    if errors > 0 or failed > 0:
        print(f"\n❌ Issues found:")
        for result in results:
            if result['status'] != 'SUCCESS':
                print(f"  - {result['question'][:40]}... → {result.get('error', 'Error response')}")
    
    print("\n" + "=" * 80)
    
    # Return true if most tests passed
    return (successful + errors) > failed and successful > 0

if __name__ == "__main__":
    success = asyncio.run(run_functional_tests())
    if success:
        print("🎉 System is working and answering questions!")
    else:
        print("⚠️  System has issues that need to be fixed.")
    exit(0 if success else 1)
