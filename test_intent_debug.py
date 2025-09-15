#!/usr/bin/env python3
"""
Test script to debug intent classification
"""
import asyncio
import json
import sys
import os

# Add the project root to the path
sys.path.append('/Users/cossettealexisgabuya/Documents/Projects/dtce-ai-bot')

from dtce_ai_bot.services.intent_classifier import IntentClassifier
from openai import AsyncAzureOpenAI

async def test_intent_classification():
    # Initialize Azure OpenAI client
    client = AsyncAzureOpenAI(
        api_key=os.getenv('AZURE_OPENAI_API_KEY', 'test-key'),
        api_version="2024-02-15-preview",
        azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    )
    
    # Initialize classifier
    classifier = IntentClassifier(client, "gpt-4")
    
    # Test the specific question
    test_question = "Who is the contact for project 225001?"
    
    print(f"Testing question: {test_question}")
    print("=" * 50)
    
    try:
        result = await classifier.classify_intent(test_question)
        print("Classification Result:")
        print(json.dumps(result, indent=2))
        
        # Check if it's classified as client_info
        if result.get('category') == 'client_info':
            print("\n✅ Correctly classified as 'client_info'")
        else:
            print(f"\n❌ Incorrectly classified as '{result.get('category')}' instead of 'client_info'")
            
    except Exception as e:
        print(f"❌ Error during classification: {e}")

if __name__ == "__main__":
    asyncio.run(test_intent_classification())
