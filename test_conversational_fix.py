#!/usr/bin/env python3
"""
Test script to verify conversational inputs are handled properly
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dtce_ai_bot.services.document_qa import DocumentQAService
from dtce_ai_bot.config.settings import settings

async def test_conversational_inputs():
    """Test that basic conversational inputs don't trigger document search"""
    
    print("🧪 Testing conversational input handling...")
    
    # Initialize the service
    qa_service = DocumentQAService(settings)
    
    # Test cases that should NOT trigger document search
    test_cases = [
        "hi",
        "hello", 
        "help",
        "really",
        "really?",
        "ok",
        "thanks",
        "yes",
        "no",
        "wow",
        "cool",
        "es",
        "hmm"
    ]
    
    print(f"\n🔍 Testing {len(test_cases)} conversational inputs...")
    
    for i, question in enumerate(test_cases, 1):
        print(f"\n--- Test {i}/{len(test_cases)}: '{question}' ---")
        
        try:
            response = await qa_service.answer_question(question)
            
            # Check that it didn't search documents
            documents_searched = response.get('documents_searched', 0)
            search_type = response.get('search_type', '')
            answer = response.get('answer', '')
            
            print(f"📊 Documents searched: {documents_searched}")
            print(f"🏷️  Search type: {search_type}")
            print(f"💬 Answer preview: {answer[:100]}...")
            
            # Verify it's handled as conversational, not engineering query
            if documents_searched == 0 and search_type in ['greeting', 'help', 'conversational', 'clarification']:
                print("✅ PASS: Handled as conversational input")
            else:
                print("❌ FAIL: Incorrectly treated as engineering query")
                
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
    
    print(f"\n🏁 Conversational input testing complete!")

if __name__ == "__main__":
    asyncio.run(test_conversational_inputs())
