#!/usr/bin/env python3
"""
Test the full RAG pipeline to see where it's failing
"""
import sys
import os
import asyncio
sys.path.append('/Users/cossettealexisgabuya/Documents/Projects/dtce-ai-bot')

# Mock the dependencies that need API keys
class MockOpenAI:
    async def chat_completions_create(self, **kwargs):
        class MockResponse:
            def __init__(self):
                self.choices = [MockChoice()]
        class MockChoice:
            def __init__(self):
                self.message = MockMessage()
        class MockMessage:
            def __init__(self):
                self.content = '{"category": "client_info", "confidence": 0.9, "reasoning": "User asking for contact info", "search_keywords": ["contact", "project", "224"]}'
        return MockResponse()

class MockSearchClient:
    def search(self, **kwargs):
        return [{"filename": "test.pdf", "content": "Contact: John Smith, Engineer"}]

async def test_intent_classification():
    """Test the intent classification directly"""
    
    # Import the intent classifier
    from dtce_ai_bot.services.intent_classifier import IntentClassifier
    
    # Create mock client
    mock_client = MockOpenAI()
    classifier = IntentClassifier(mock_client, "gpt-4")
    
    test_question = "Who is the contact for project 224?"
    
    print("Testing Intent Classification")
    print("=" * 40)
    print(f"Question: {test_question}")
    
    try:
        # Test intent classification
        result = await classifier.classify_intent(test_question)
        print(f"Classification result: {result}")
        
        if result.get('category') == 'client_info':
            print("✅ Correctly classified as client_info")
        else:
            print(f"❌ Wrong classification: {result.get('category')}")
            
    except Exception as e:
        print(f"❌ Intent classification failed: {e}")
        # Test fallback
        fallback = classifier._get_fallback_classification(test_question)
        print(f"Fallback classification: {fallback}")

if __name__ == "__main__":
    asyncio.run(test_intent_classification())
