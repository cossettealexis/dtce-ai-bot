#!/usr/bin/env python3
"""
Simple test for enhanced RAG components
"""
import sys
import os

# Add the dtce_ai_bot to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'dtce_ai_bot'))

def test_imports():
    """Test if we can import the enhanced components"""
    try:
        from dtce_ai_bot.services.advanced_rag_handler import AdvancedRAGHandler
        print("✅ AdvancedRAGHandler imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import AdvancedRAGHandler: {e}")

    try:
        from dtce_ai_bot.services.conversation_context import ConversationContextManager
        print("✅ ConversationContextManager imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import ConversationContextManager: {e}")

    try:
        from dtce_ai_bot.services.rag_config import RAGConfigService
        print("✅ RAGConfigService imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import RAGConfigService: {e}")

def test_basic_initialization():
    """Test basic initialization of components"""
    try:
        from dtce_ai_bot.services.advanced_rag_handler import AdvancedRAGHandler
        handler = AdvancedRAGHandler(search_client=None, openai_client=None)
        print("✅ AdvancedRAGHandler initialized")
    except Exception as e:
        print(f"❌ Failed to initialize AdvancedRAGHandler: {e}")

    try:
        from dtce_ai_bot.services.conversation_context import ConversationContextManager
        context_mgr = ConversationContextManager()
        print("✅ ConversationContextManager initialized")
    except Exception as e:
        print(f"❌ Failed to initialize ConversationContextManager: {e}")

    try:
        from dtce_ai_bot.services.rag_config import RAGConfigService
        config_svc = RAGConfigService()
        print("✅ RAGConfigService initialized")
    except Exception as e:
        print(f"❌ Failed to initialize RAGConfigService: {e}")

if __name__ == "__main__":
    print("Testing Enhanced RAG System Components...")
    print("=" * 50)
    
    print("\n1. Testing Imports...")
    test_imports()
    
    print("\n2. Testing Basic Initialization...")
    test_basic_initialization()
    
    print("\n✅ Enhanced RAG system test completed!")
