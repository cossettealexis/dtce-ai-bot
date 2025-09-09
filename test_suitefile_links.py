#!/usr/bin/env python3
"""Test to verify SuiteFiles links are now appearing in responses."""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dtce_ai_bot.services.rag_handler import RAGHandler
from dtce_ai_bot.config.settings import Settings


async def test_suitefile_link_generation():
    """Test that AI responses now include SuiteFiles links."""
    print("🧪 Testing SuiteFiles link generation in AI responses...")
    
    settings = Settings()
    rag_handler = RAGHandler(settings)
    
    # Test questions that should return SuiteFiles links
    test_questions = [
        "What are the safety requirements for construction projects?",
        "What documents are required for building permits?",
        "Can you tell me about noise regulations in construction?"
    ]
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n--- Test {i}: {question} ---")
        
        try:
            response = await rag_handler.process_question(question)
            
            # Check for SuiteFiles links
            has_suitefile_link = "SuiteFiles" in response and "https://" in response
            print(f"✅ Has SuiteFiles link: {has_suitefile_link}")
            
            if has_suitefile_link:
                # Extract and show the link
                lines = response.split('\n')
                for line in lines:
                    if "SuiteFiles" in line and "https://" in line:
                        print(f"🔗 Found link: {line.strip()}")
                        break
            else:
                print("❌ No SuiteFiles link found in response")
                print(f"Response preview: {response[:200]}...")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n🔍 Testing complete!")


if __name__ == "__main__":
    asyncio.run(test_suitefile_link_generation())
