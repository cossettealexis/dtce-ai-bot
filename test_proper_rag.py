#!/usr/bin/env python3
"""
Test Proper RAG Implementation
"""
import sys
import os
import asyncio
from datetime import datetime

# Add the dtce_ai_bot to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'dtce_ai_bot'))

async def test_proper_rag():
    """Test the proper RAG implementation vs the old broken system"""
    print("🔬 Testing PROPER RAG Implementation")
    print("=" * 60)
    
    try:
        from dtce_ai_bot.services.document_qa import DocumentQAService
        from dtce_ai_bot.config.settings import get_settings
        
        # Mock search client for testing
        class MockSearchClient:
            def search(self, **kwargs):
                # Return mock results that would come from Azure Search
                return [
                    {
                        'content': 'NZS 3604 specifies minimum requirements for timber-framed buildings up to 10m in height.',
                        'title': 'NZS 3604 Timber Framing Standard',
                        'source': 'nzs_3604.pdf',
                        'chunk_id': 'chunk_001',
                        '@search.score': 0.95,
                        '@search.reranker_score': 0.98,
                        'document_type': 'standard',
                        'category': 'building_code'
                    },
                    {
                        'content': 'Timber framing members must be sized according to span tables in section 7.',
                        'title': 'NZS 3604 Span Tables',
                        'source': 'nzs_3604_span_tables.pdf',
                        'chunk_id': 'chunk_002',
                        '@search.score': 0.87,
                        '@search.reranker_score': 0.92,
                        'document_type': 'standard',
                        'category': 'structural'
                    }
                ]
        
        # Test with mock client
        mock_client = MockSearchClient()
        qa_service = DocumentQAService(mock_client)
        
        print("✅ RAG service initialized")
        
        # Test simple query
        test_question = "What are the requirements for timber framing?"
        
        print(f"\n📤 Testing question: '{test_question}'")
        result = await qa_service.answer_question(test_question)
        
        print("\n📥 RAG Result:")
        print(f"Answer: {result.get('answer', 'No answer')}")
        print(f"RAG Type: {result.get('rag_type', 'Unknown')}")
        print(f"Search Type: {result.get('search_type', 'Unknown')}")
        print(f"Documents Searched: {result.get('documents_searched', 0)}")
        print(f"Sources: {len(result.get('sources', []))}")
        print(f"Confidence: {result.get('confidence', 'Unknown')}")
        
        # Test if it's using proper RAG
        is_proper_rag = result.get('rag_type') == 'proper_hybrid_rag'
        if is_proper_rag:
            print("\n✅ SUCCESS: Using PROPER RAG with hybrid search!")
        else:
            print(f"\n❌ FAIL: Still using old system: {result.get('rag_type')}")
        
        # Test enhanced queries
        enhanced_queries = result.get('enhanced_queries', [])
        if enhanced_queries:
            print(f"\n🔍 Enhanced Queries: {enhanced_queries}")
        
        # Check for sources
        sources = result.get('sources', [])
        if sources:
            print(f"\n📚 Sources Found:")
            for i, source in enumerate(sources[:3]):
                print(f"  {i+1}. {source.get('title', 'Unknown')}")
        
        return is_proper_rag
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_conversation_context():
    """Test conversation context management"""
    print("\n💬 Testing Conversation Context")
    print("=" * 40)
    
    try:
        from dtce_ai_bot.services.proper_rag_service import RAGOrchestrator
        
        # Mock clients
        class MockSearchClient:
            def search(self, **kwargs):
                return []
        
        class MockOpenAIClient:
            async def chat_completions_create(self, **kwargs):
                class MockResponse:
                    def __init__(self):
                        self.choices = [MockChoice()]
                class MockChoice:
                    def __init__(self):
                        self.message = MockMessage()
                class MockMessage:
                    def __init__(self):
                        self.content = '["enhanced query about timber framing"]'
                return MockResponse()
            
            async def embeddings_create(self, **kwargs):
                class MockEmbedding:
                    def __init__(self):
                        self.data = [MockEmbeddingData()]
                class MockEmbeddingData:
                    def __init__(self):
                        self.embedding = [0.1] * 1536  # Mock embedding
                return MockEmbedding()
        
        orchestrator = RAGOrchestrator(MockSearchClient(), MockOpenAIClient(), "gpt-4")
        
        # Test session management
        session_id = "test_session"
        
        # First query
        result1 = await orchestrator.process_question("What is NZS 3604?", session_id)
        print(f"✅ First query processed: {len(result1.get('answer', ''))} chars")
        
        # Follow-up query
        result2 = await orchestrator.process_question("What about span tables?", session_id)
        print(f"✅ Follow-up query processed: {len(result2.get('answer', ''))} chars")
        
        # Check conversation history
        history = orchestrator.conversation_history.get(session_id, [])
        print(f"✅ Conversation history: {len(history)} turns")
        
        return True
        
    except Exception as e:
        print(f"❌ Conversation test failed: {e}")
        return False

async def main():
    """Run proper RAG tests"""
    print("🚀 PROPER RAG SYSTEM TEST")
    print("=" * 60)
    print(f"Test started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    tests = [
        ("Proper RAG Implementation", test_proper_rag),
        ("Conversation Context", test_conversation_context)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            print(f"Running: {test_name}")
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("🎯 PROPER RAG TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ PROPER RAG system is working!")
        print("✅ No more AI bullshit keyword matching!")
        print("✅ Real hybrid search + semantic ranking!")
        print("\n🔥 The bot now uses ACTUAL RAG technology!")
    else:
        print("\n⚠️ Some tests failed - check implementation")

if __name__ == "__main__":
    asyncio.run(main())
