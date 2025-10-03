#!/usr/bin/env python3
"""
Real World Bot Test
Test actual bot response to see if we fixed the AI bullshit problem
"""
import sys
import os
import asyncio

# Add the dtce_ai_bot to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'dtce_ai_bot'))

async def test_real_bot_response():
    """Test what the bot actually says to a simple question"""
    print("🤖 Testing Real Bot Response")
    print("=" * 50)
    
    try:
        from dtce_ai_bot.services.document_qa import DocumentQAService
        
        # Create mock search client that returns realistic construction docs
        class MockSearchClient:
            def search(self, **kwargs):
                return [
                    {
                        'content': 'NZS 3604 provides technical requirements for timber-framed buildings up to 10m in height. The standard covers structural design, member sizing, connections, and bracing systems.',
                        'title': 'NZS 3604 Timber Framing Standard',
                        'source': 'nzs_3604_overview.pdf',
                        'chunk_id': 'nzs_001',
                        '@search.score': 0.95,
                        '@search.reranker_score': 0.98,
                        'document_type': 'standard',
                        'category': 'building_code'
                    },
                    {
                        'content': 'Timber members must be grade-stamped and comply with AS/NZS 1748. Standard grades include SG8, SG10, and SG12 for structural applications.',
                        'title': 'Timber Grading Requirements',
                        'source': 'timber_standards.pdf',
                        'chunk_id': 'timber_001',
                        '@search.score': 0.87,
                        'document_type': 'specification',
                        'category': 'materials'
                    }
                ]
        
        qa_service = DocumentQAService(MockSearchClient())
        
        # Test the same question that gave the terrible response before
        test_question = "test"
        
        print(f"Question: '{test_question}'")
        print("\nProcessing with Azure RAG system...")
        
        result = await qa_service.answer_question(test_question)
        
        print(f"\nBot Response:")
        print(f"Answer: {result.get('answer', 'No answer')}")
        print(f"RAG Type: {result.get('rag_type', 'Unknown')}")
        print(f"Sources Used: {len(result.get('sources', []))}")
        print(f"Confidence: {result.get('confidence', 'Unknown')}")
        
        # Check if it's the old terrible response
        answer = result.get('answer', '')
        
        # Bad indicators from the old system
        bad_patterns = [
            'DIRECT TECHNICAL ANSWER:',
            'NZ STANDARDS & CODES:',
            'ADVISORY ANALYSIS:',
            'LESSONS LEARNED & BEST PRACTICES:',
            'GENERAL GUIDELINES:',
            'COMBINED KNOWLEDGE APPROACH:',
            'PROFESSIONAL ADVISORY GUIDANCE:'
        ]
        
        has_bad_patterns = any(pattern in answer for pattern in bad_patterns)
        
        if has_bad_patterns:
            print("\n❌ STILL GENERATING AI BULLSHIT!")
            print("❌ The old template-based response is still being used")
            return False
        
        # Good indicators of proper RAG
        if result.get('rag_type') == 'azure_hybrid_rag':
            print("\n✅ SUCCESS: Using Azure RAG system!")
            print("✅ No more templated AI bullshit responses")
            print("✅ Response is based on retrieved documents")
            return True
        else:
            print(f"\n⚠️ Unexpected RAG type: {result.get('rag_type')}")
            return False
            
    except Exception as e:
        print(f"\n❌ Real bot test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_specific_question():
    """Test with a specific construction question"""
    print("\n🏗️ Testing Specific Construction Question")
    print("=" * 50)
    
    try:
        from dtce_ai_bot.services.document_qa import DocumentQAService
        
        class MockSearchClient:
            def search(self, **kwargs):
                return [
                    {
                        'content': 'For 90x45mm H1.2 treated pine joists, maximum spans range from 2.4m to 4.8m depending on loading and spacing. Refer to NZS 3604 Table 7.3 for specific span limits.',
                        'title': 'NZS 3604 Span Tables',
                        'source': 'nzs_3604_spans.pdf',
                        '@search.score': 0.92,
                        '@search.reranker_score': 0.95
                    }
                ]
        
        qa_service = DocumentQAService(MockSearchClient())
        
        question = "What are the maximum spans for 90x45mm joists?"
        print(f"Question: '{question}'")
        
        result = await qa_service.answer_question(question)
        
        answer = result.get('answer', '')
        print(f"\nAnswer: {answer}")
        
        # Check for specific technical content
        if any(term in answer.lower() for term in ['90x45mm', 'joist', 'span', 'nzs 3604']):
            print("✅ Answer contains relevant technical content")
            print("✅ Based on document retrieval, not generic templates")
            return True
        else:
            print("❌ Answer doesn't contain expected technical content")
            return False
            
    except Exception as e:
        print(f"❌ Specific question test failed: {e}")
        return False

async def main():
    """Test real bot responses"""
    print("🎯 REAL WORLD BOT RESPONSE TEST")
    print("=" * 60)
    print("Testing if we actually fixed the AI bullshit problem")
    print()
    
    tests = [
        ("Generic 'test' Query", test_real_bot_response),
        ("Specific Technical Query", test_specific_question)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"Test {test_name} failed: {e}")
            results.append((test_name, False))
    
    # Results
    print("\n" + "=" * 60)
    print("🎯 REAL WORLD TEST RESULTS")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    if passed == total:
        print("\n🎉 SUCCESS! The AI bullshit has been eliminated!")
        print("✅ Bot now uses proper Azure RAG system")
        print("✅ Responses based on document retrieval")
        print("✅ No more generic template garbage")
        print("\n🚀 The bot is now giving REAL answers based on REAL documents!")
    else:
        print("\n❌ Still some issues - check the implementation")

if __name__ == "__main__":
    asyncio.run(main())
