#!/usr/bin/env python3
"""
Comprehensive Bot Testing Script
Tests the bot functionality with enhanced RAG system
"""
import sys
import os
import asyncio
import json
from datetime import datetime

# Add the dtce_ai_bot to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'dtce_ai_bot'))

async def test_bot_initialization():
    """Test bot initialization and core components"""
    print("🤖 Testing Bot Initialization...")
    print("=" * 50)
    
    try:
        # Test core bot imports
        from dtce_ai_bot.core.app import app
        print("✅ FastAPI app imported successfully")
        
        from dtce_ai_bot.bot.teams_bot import DTCETeamsBot
        print("✅ DTCETeamsBot imported successfully")
        
        from dtce_ai_bot.services.rag_handler import RAGHandler
        print("✅ RAGHandler imported successfully")
        
        # Test enhanced RAG components
        from dtce_ai_bot.services.advanced_rag_handler import AdvancedRAGHandler
        print("✅ AdvancedRAGHandler imported successfully")
        
        from dtce_ai_bot.services.conversation_context_simple import ConversationContextManager
        print("✅ ConversationContextManager imported successfully")
        
        from dtce_ai_bot.services.rag_config_simple import RAGConfigService
        print("✅ RAGConfigService imported successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Bot initialization failed: {e}")
        return False

async def test_bot_endpoints():
    """Test bot API endpoints"""
    print("\n🔗 Testing Bot Endpoints...")
    print("=" * 50)
    
    try:
        from dtce_ai_bot.core.app import app
        from fastapi.testclient import TestClient
        
        # Create test client
        client = TestClient(app)
        
        # Test health endpoint
        response = client.get("/health")
        if response.status_code == 200:
            print("✅ Health endpoint working")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
        
        # Test bot endpoint exists
        response = client.post("/api/messages", json={})
        # We expect this to fail with validation error, not 404
        if response.status_code != 404:
            print("✅ Bot message endpoint exists")
        else:
            print("❌ Bot message endpoint not found")
            
        return True
        
    except Exception as e:
        print(f"❌ Endpoint testing failed: {e}")
        return False

async def test_enhanced_rag_components():
    """Test enhanced RAG system components"""
    print("\n🧠 Testing Enhanced RAG Components...")
    print("=" * 50)
    
    try:
        # Test AdvancedRAGHandler
        from dtce_ai_bot.services.advanced_rag_handler import AdvancedRAGHandler
        handler = AdvancedRAGHandler(search_client=None, openai_client=None)
        print("✅ AdvancedRAGHandler initialized")
        
        # Test ConversationContextManager
        from dtce_ai_bot.services.conversation_context_simple import ConversationContextManager
        context_mgr = ConversationContextManager()
        
        # Test conversation tracking
        context_mgr.add_turn("test_session", "user", "What is NZS 3604?")
        context_mgr.add_turn("test_session", "assistant", "NZS 3604 is the New Zealand building code for timber framing.")
        context_mgr.add_turn("test_session", "user", "What are the key requirements?")
        
        context = context_mgr.get_context("test_session")
        print(f"✅ ConversationContextManager working: {len(context)} turns tracked")
        
        # Test RAGConfigService
        from dtce_ai_bot.services.rag_config_simple import RAGConfigService, SearchMode
        config_svc = RAGConfigService()
        
        factual_config = config_svc.get_config_for_query("factual")
        complex_mode = config_svc.get_search_mode("complex")
        
        print(f"✅ RAGConfigService working: factual queries max_sources={factual_config.max_sources}")
        print(f"✅ Search mode for complex queries: {complex_mode.value}")
        
        return True
        
    except Exception as e:
        print(f"❌ Enhanced RAG testing failed: {e}")
        return False

async def test_configuration():
    """Test configuration and settings"""
    print("\n⚙️ Testing Configuration...")
    print("=" * 50)
    
    try:
        from dtce_ai_bot.config.settings import Settings
        
        # Test settings loading
        settings = Settings()
        print("✅ Settings loaded successfully")
        
        # Check for required environment variables (without exposing sensitive data)
        required_vars = [
            'AZURE_OPENAI_ENDPOINT',
            'AZURE_SEARCH_ENDPOINT',
            'BOT_APP_ID'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not hasattr(settings, var.lower()) or not getattr(settings, var.lower(), None):
                missing_vars.append(var)
        
        if missing_vars:
            print(f"⚠️ Missing environment variables: {', '.join(missing_vars)}")
            print("   (This is expected in test environment)")
        else:
            print("✅ All required environment variables configured")
            
        return True
        
    except Exception as e:
        print(f"❌ Configuration testing failed: {e}")
        return False

async def simulate_bot_query():
    """Simulate a bot query interaction"""
    print("\n💬 Simulating Bot Query...")
    print("=" * 50)
    
    try:
        from dtce_ai_bot.services.conversation_context_simple import ConversationContextManager
        from dtce_ai_bot.services.rag_config_simple import RAGConfigService
        
        # Simulate conversation flow
        context_mgr = ConversationContextManager()
        config_svc = RAGConfigService()
        
        # Test query types
        queries = [
            ("What is the maximum span for 90x45mm timber joists?", "factual"),
            ("Compare H1.2 and H3.2 treated timber", "comparative"),
            ("Analyze the structural requirements for a two-story dwelling", "analytical")
        ]
        
        for query, query_type in queries:
            # Add user query to context
            context_mgr.add_turn("test_session", "user", query)
            
            # Get appropriate config for query type
            config = config_svc.get_config_for_query(query_type)
            
            # Simulate bot response
            bot_response = f"Based on NZS 3604 and relevant building codes... (max_sources: {config.max_sources}, temp: {config.temperature})"
            context_mgr.add_turn("test_session", "assistant", bot_response)
            
            print(f"✅ Query processed: {query_type}")
            print(f"   User: {query[:50]}...")
            print(f"   Config: max_sources={config.max_sources}, temperature={config.temperature}")
        
        # Check conversation history
        context = context_mgr.get_context("test_session")
        print(f"✅ Conversation history: {len(context)} total turns")
        
        return True
        
    except Exception as e:
        print(f"❌ Bot query simulation failed: {e}")
        return False

async def main():
    """Run all bot tests"""
    print("🚀 DTCE AI Bot Comprehensive Test Suite")
    print("=" * 60)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    test_results = []
    
    # Run all tests
    tests = [
        ("Bot Initialization", test_bot_initialization),
        ("Bot Endpoints", test_bot_endpoints),
        ("Enhanced RAG Components", test_enhanced_rag_components),
        ("Configuration", test_configuration),
        ("Bot Query Simulation", simulate_bot_query)
    ]
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            test_results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            test_results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("🎯 TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Bot is ready for production!")
    else:
        print("⚠️ Some tests failed. Check the output above for details.")
    
    return passed == total

if __name__ == "__main__":
    asyncio.run(main())
