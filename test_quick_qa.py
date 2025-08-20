#!/usr/bin/env python3
"""
Quick test script for DTCE AI Bot - Essential tests only
"""

import asyncio
import httpx
import time

# Quick test configuration
BASE_URL = "https://dtceai-backend-cyashrb8hnc2ayhp.newzealandnorth-01.azurewebsites.net"

# Essential test questions to verify key functionality
QUICK_TESTS = [
    # Test static template elimination
    {
        "question": "Show me examples of mid-rise timber frame buildings in high wind zones that we've designed",
        "expect": "Should NOT contain 'Here are examples from DTCE projects matching your scenario'"
    },
    
    # Test link functionality
    {
        "question": "Show me the wind load calculation document and provide the link",
        "expect": "Should contain working SuiteFiles links, not Azure blob URLs"
    },
    
    # Test specific project lookup
    {
        "question": "project 219",
        "expect": "Should provide project details without hallucinating fake numbers"
    },
    
    # Test external reference handling
    {
        "question": "How do space structures work?",
        "expect": "Should recognize as external reference and provide appropriate response"
    },
    
    # Test intelligent fallback
    {
        "question": "What's the weather like today?",
        "expect": "Should use intelligent fallback to redirect to engineering topics"
    },
    
    # Test natural language generation
    {
        "question": "What are DTCE's best practices for timber design?",
        "expect": "Should provide natural GPT response, not static template"
    },
    
    # Test conversational input
    {
        "question": "Hi, can you help me with structural design for a commercial building?",
        "expect": "Should handle conversational style naturally"
    },
    
    # Test document search with links
    {
        "question": "I need the LVL beam specification sheet with a direct link",
        "expect": "Should provide document with working SuiteFiles file link"
    }
]

async def quick_test():
    """Run quick essential tests"""
    print("🚀 DTCE AI Bot - Quick Essential Tests")
    print("=" * 50)
    
    async with httpx.AsyncClient() as client:
        for i, test in enumerate(QUICK_TESTS, 1):
            question = test["question"]
            expect = test["expect"]
            
            print(f"\n{i}. Testing: {question}")
            print(f"   Expected: {expect}")
            print("-" * 50)
            
            start_time = time.time()
            
            try:
                response = await client.post(
                    f"{BASE_URL}/api/qa",
                    json={
                        "question": question,
                        "conversation_history": []
                    },
                    timeout=30.0
                )
                
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    result = response.json()
                    answer = result.get('answer', '')
                    confidence = result.get('confidence', 'unknown')
                    rag_type = result.get('rag_type', 'unknown')
                    
                    print(f"✅ Response received: {response_time:.2f}s | {confidence} | {rag_type}")
                    
                    # Check for specific issues
                    if "Here are examples from DTCE projects matching your scenario" in answer:
                        print("❌ STATIC TEMPLATE DETECTED!")
                    
                    if "[" in answer and "](" in answer:
                        print("🔗 Contains links")
                    
                    if "https://dtceaistorage.blob.core.windows.net" in answer:
                        print("❌ AZURE BLOB URL DETECTED! Should be SuiteFiles URL")
                    
                    if "https://donthomson.sharepoint.com" in answer:
                        print("✅ SuiteFiles URL detected")
                    
                    # Show first part of answer
                    print(f"Answer preview: {answer[:200]}...")
                    
                else:
                    print(f"❌ HTTP Error: {response.status_code}")
                    
            except Exception as e:
                print(f"💥 Exception: {str(e)}")
            
            print()
    
    print("🏁 Quick tests completed!")

if __name__ == "__main__":
    asyncio.run(quick_test())
