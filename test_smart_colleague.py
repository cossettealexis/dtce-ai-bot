#!/usr/bin/env python3
"""
Quick test of the smart DTCE colleague system
"""
import asyncio
import sys
sys.path.append('/Users/cossettealexisgabuya/Documents/Projects/dtce-ai-bot')

from dtce_ai_bot.services.rag_handler import RAGHandler
from dtce_ai_bot.config.config import get_config

async def test_smart_colleague():
    """Test the smart DTCE colleague responses"""
    config = get_config()
    rag_handler = RAGHandler(config)
    
    # Test questions
    questions = [
        "How do you design a concrete beam?",  # Should be general_engineering
        "What is DTCE's safety policy?",       # Should be dtce_specific
        "Tell me about wellness policy"        # Should search SuiteFiles
    ]
    
    for question in questions:
        print(f"\n🤖 Testing: {question}")
        print("-" * 50)
        
        try:
            # Test the question type analysis
            question_type = await rag_handler._analyze_question_intent(question)
            print(f"📋 Question Type: {question_type}")
            
            # Test the full response
            result = await rag_handler.universal_ai_assistant(question)
            print(f"🎯 Response Type: {result.get('rag_type', 'unknown')}")
            print(f"📄 Documents Found: {result.get('documents_searched', 0)}")
            print(f"💬 Answer Preview: {result.get('answer', 'No answer')[:200]}...")
            
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_smart_colleague())
